"""
Cloud Functions do Vigília (Firebase, Python 3.12, 2ª geração).

Funções publicadas:

  api               HTTPS — backend da SPA hospedada em vigiliasms.web.app.
                    Roteada via rewrite do Firebase Hosting (/api/** → api).
                    Endpoints:
                      GET  /api/health           → disponibilidade
                      GET  /api/config           → configuração (com seed)
                      POST /api/config           → salva configuração
                      POST /api/buscar           → varredura DOU + DOE-SC
                      POST /api/sintese          → síntese por IA dos resultados
                      POST /api/fhir             → FHIR Message Bundle
                      POST /api/relatorio/testar → envia o relatório do dia AGORA

  relatorio_diario  Agendada (07:00 America/Sao_Paulo, seg-sex) — varre a edição
                    do dia com a config salva e envia o relatório por e-mail (SMTP).
                    DESATIVADA por padrão: só roda quando config/relatorio.ativo
                    == true no Firestore e houver destinatários.

Segredos (Firebase Secrets — ver README):
  VIGILIA_SMTP_HOST, VIGILIA_SMTP_PORT, VIGILIA_SMTP_USER, VIGILIA_SMTP_PASS,
  VIGILIA_SMTP_FROM  → envio de e-mail.
  GEMINI_API_KEY     → resumo por IA (futuro; comentado abaixo).

Requisitos de plano: rede externa, e-mail e agendamento exigem o plano Blaze.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from firebase_admin import firestore, initialize_app
from firebase_functions import https_fn, options, scheduler_fn
from firebase_functions.params import SecretParam

from vigilia_core import config_padrao, ia
from vigilia_core.datas import dia_util_anterior
from vigilia_core.dou import buscar_dou_completo
from vigilia_core.doesc import buscar_doesc
from vigilia_core.email_sender import (
    EmailNaoConfigurado,
    enviar_email,
    remetente_formatado,
)
from vigilia_core.fhir import montar_bundle
from vigilia_core.filtros import limpar_palavras, normalizar_operador
from vigilia_core.relatorio import gerar_relatorio_html

initialize_app()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vigilia.functions")

REGIAO = "southamerica-east1"

# Segredos de SMTP (injetados como variáveis de ambiente nas funções).
SMTP_HOST = SecretParam("VIGILIA_SMTP_HOST")
SMTP_PORT = SecretParam("VIGILIA_SMTP_PORT")
SMTP_USER = SecretParam("VIGILIA_SMTP_USER")
SMTP_PASS = SecretParam("VIGILIA_SMTP_PASS")
SMTP_FROM = SecretParam("VIGILIA_SMTP_FROM")

# Síntese por IA (Google AI Studio / Gemini)
GEMINI_API_KEY = SecretParam("GEMINI_API_KEY")

# Lista única de secrets injetados nas funções (SMTP + IA).
SECRETS = [SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM, GEMINI_API_KEY]

_CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Max-Age": "3600",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _json_response(payload: dict, status: int = 200) -> https_fn.Response:
    return https_fn.Response(
        json.dumps(payload, ensure_ascii=False),
        status=status,
        headers={**_CORS_HEADERS, "Content-Type": "application/json; charset=utf-8"},
    )


def _erro(mensagem: str, status: int = 400) -> https_fn.Response:
    return _json_response({"erro": mensagem}, status=status)


def _db():
    return firestore.client()


def _carregar_config(db) -> dict:
    """Lê a configuração do Firestore, criando os padrões na primeira leitura."""
    ref_v = db.collection("config").document("varredura")
    ref_r = db.collection("config").document("relatorio")

    doc_v = ref_v.get()
    if doc_v.exists:
        varredura = doc_v.to_dict()
    else:
        varredura = {
            "palavras_chave": config_padrao.PALAVRAS_PADRAO,
            "operador": config_padrao.OPERADOR_PADRAO,
            "fontes": config_padrao.FONTES_PADRAO,
            "atualizado_em": datetime.now(timezone.utc).isoformat(),
        }
        ref_v.set(varredura)

    doc_r = ref_r.get()
    if doc_r.exists:
        relatorio = doc_r.to_dict()
    else:
        relatorio = dict(config_padrao.RELATORIO_PADRAO)
        ref_r.set(relatorio)

    return {"varredura": varredura, "relatorio": relatorio}


def _executar_varredura(data_publicacao: date, palavras, operador, fontes) -> dict:
    resultados: list[dict] = []
    erros: list[str] = []

    if fontes.get("dou", True):
        try:
            resultados.extend(buscar_dou_completo(data_publicacao, palavras, operador))
        except Exception as e:
            logger.exception("Falha na varredura do DOU")
            erros.append(f"DOU: {e}")

    if fontes.get("doesc", True):
        try:
            resultados.extend(buscar_doesc(data_publicacao, palavras, operador))
        except Exception as e:
            logger.exception("Falha na varredura do DOE-SC")
            erros.append(f"DOE-SC: {e}")

    por_origem: dict[str, int] = {}
    for r in resultados:
        por_origem[r["origem"]] = por_origem.get(r["origem"], 0) + 1

    return {
        "resultados": resultados,
        "total": len(resultados),
        "por_origem": por_origem,
        "erros": erros,
        "executado_em": datetime.now(timezone.utc).isoformat(),
    }


def _montar_e_enviar_relatorio(
    db, destinatarios: list[str], data_pub: date,
    palavras, operador, fontes, usar_ia: bool = False,
) -> dict:
    """Varre, opcionalmente resume com IA, envia o e-mail e registra o histórico."""
    resultado = _executar_varredura(data_pub, palavras, operador, fontes)

    resumo_ia = None
    if usar_ia:
        resumo_ia = ia.gerar_resumo(
            resultado["resultados"], data_pub.strftime("%d/%m/%Y"), palavras
        )

    assunto, html_corpo = gerar_relatorio_html(
        resultado["resultados"], data_pub, palavras, operador, resumo_ia=resumo_ia
    )
    envio = enviar_email(destinatarios, assunto, html_corpo)

    db.collection("relatorios").document(data_pub.isoformat()).set({
        "data": data_pub.isoformat(),
        "total": resultado["total"],
        "por_origem": resultado["por_origem"],
        "erros": resultado["erros"],
        "destinatarios": envio["destinatarios"],
        "resumo_ia": bool(resumo_ia),
        "gerado_em": datetime.now(timezone.utc).isoformat(),
    })
    return {"total": resultado["total"], "por_origem": resultado["por_origem"], **envio}


# ---------------------------------------------------------------------------
# Função HTTPS: API da SPA
# ---------------------------------------------------------------------------

@https_fn.on_request(
    region=REGIAO,
    memory=options.MemoryOption.MB_512,
    timeout_sec=300,
    max_instances=5,
    secrets=SECRETS,
)
def api(req: https_fn.Request) -> https_fn.Response:
    if req.method == "OPTIONS":
        return https_fn.Response("", status=204, headers=_CORS_HEADERS)

    rota = req.path.removeprefix("/api").rstrip("/") or "/"

    try:
        if req.method == "GET" and rota == "/health":
            return _json_response({
                "status": "ok",
                "servico": "vigilia-api",
                "remetente_email": remetente_formatado(),
            })

        if rota == "/config":
            db = _db()
            if req.method == "GET":
                return _json_response(_carregar_config(db))
            if req.method == "POST":
                return _salvar_config(db, req.get_json(silent=True) or {})

        if req.method == "POST" and rota == "/buscar":
            return _rota_buscar(req.get_json(silent=True) or {})

        if req.method == "POST" and rota == "/fhir":
            corpo = req.get_json(silent=True) or {}
            registros = corpo.get("resultados", [])
            if not isinstance(registros, list):
                return _erro("Campo 'resultados' deve ser uma lista.")
            return _json_response({"bundle": montar_bundle(registros)})

        if req.method == "POST" and rota == "/sintese":
            return _rota_sintese(req.get_json(silent=True) or {})

        if req.method == "POST" and rota == "/relatorio/testar":
            return _rota_testar_relatorio(req.get_json(silent=True) or {})

        return _erro(f"Rota não encontrada: {req.method} {rota}", status=404)

    except Exception:
        logger.exception("Erro não tratado na API")
        return _erro("Erro interno na API do Vigília.", status=500)


def _salvar_config(db, corpo: dict) -> https_fn.Response:
    agora = datetime.now(timezone.utc).isoformat()

    if "varredura" in corpo:
        v = corpo["varredura"] or {}
        db.collection("config").document("varredura").set({
            "palavras_chave": limpar_palavras(v.get("palavras_chave", [])),
            "operador": normalizar_operador(v.get("operador", "OU")),
            "fontes": {
                "dou": bool((v.get("fontes") or {}).get("dou", True)),
                "doesc": bool((v.get("fontes") or {}).get("doesc", True)),
            },
            "atualizado_em": agora,
        })

    if "relatorio" in corpo:
        r = corpo["relatorio"] or {}
        destinatarios = [
            d.strip() for d in r.get("destinatarios", [])
            if isinstance(d, str) and "@" in d
        ]
        db.collection("config").document("relatorio").set({
            "ativo": bool(r.get("ativo", False)),
            "destinatarios": destinatarios,
            "horario": str(r.get("horario", "07:00")),
            "resumo_ia": bool(r.get("resumo_ia", False)),
            "atualizado_em": agora,
        })

    return _json_response(_carregar_config(db))


def _rota_buscar(corpo: dict) -> https_fn.Response:
    data_str = str(corpo.get("data", ""))
    try:
        data_publicacao = date.fromisoformat(data_str)
    except ValueError:
        return _erro(f"Data inválida: {data_str!r}. Use o formato AAAA-MM-DD.")

    palavras = limpar_palavras(corpo.get("palavras", []))
    operador = normalizar_operador(corpo.get("operador", "OU"))
    fontes = corpo.get("fontes") or {"dou": True, "doesc": True}

    if not fontes.get("dou") and not fontes.get("doesc"):
        return _erro("Selecione pelo menos uma fonte (dou e/ou doesc).")

    resultado = _executar_varredura(data_publicacao, palavras, operador, fontes)
    resultado["parametros"] = {
        "data": data_str, "palavras": palavras,
        "operador": operador, "fontes": fontes,
    }
    return _json_response(resultado)


def _rota_sintese(corpo: dict) -> https_fn.Response:
    """
    Gera a síntese por IA dos resultados já exibidos no painel (não-bloqueante:
    o site mostra os cards na hora e busca a síntese em seguida).

    Cacheia por assinatura da busca (data + termos + operador + fontes) na
    coleção `sinteses`, evitando custo repetido na mesma consulta.
    """
    if not ia.resumo_disponivel():
        return _json_response({"sintese": None, "motivo": "ia_indisponivel"})

    resultados = corpo.get("resultados", [])
    if not isinstance(resultados, list) or not resultados:
        return _json_response({"sintese": None, "motivo": "sem_resultados"})

    data_str = str(corpo.get("data", "")).strip()
    try:
        data_pub = date.fromisoformat(data_str)
    except ValueError:
        return _erro(f"Data inválida: {data_str!r}. Use AAAA-MM-DD.")

    palavras = limpar_palavras(corpo.get("palavras", []))
    operador = normalizar_operador(corpo.get("operador", "OU"))
    fontes = corpo.get("fontes") or {}

    import hashlib
    assinatura = json.dumps(
        {"data": data_str, "palavras": sorted(palavras),
         "operador": operador, "fontes": fontes},
        sort_keys=True, ensure_ascii=False,
    )
    chave = hashlib.sha1(assinatura.encode("utf-8")).hexdigest()

    modelo = corpo.get("modelo") or None  # override opcional (diagnóstico)

    db = _db()
    ref = db.collection("sinteses").document(chave)
    if not modelo:  # cache só vale para o modelo padrão
        doc = ref.get()
        if doc.exists and doc.to_dict().get("texto"):
            return _json_response({"sintese": doc.to_dict()["texto"], "cache": True})

    texto = ia.gerar_resumo(resultados, data_pub.strftime("%d/%m/%Y"), palavras, modelo=modelo)
    if texto and not modelo:
        ref.set({
            "texto": texto,
            "total": len(resultados),
            "gerado_em": datetime.now(timezone.utc).isoformat(),
        })
    return _json_response({"sintese": texto})


def _rota_testar_relatorio(corpo: dict) -> https_fn.Response:
    """Envia o relatório da data informada (ou de hoje) imediatamente."""
    db = _db()
    config = _carregar_config(db)
    cfg_v = config["varredura"]
    cfg_r = config["relatorio"]

    destinatarios = corpo.get("destinatarios") or cfg_r.get("destinatarios") or []
    destinatarios = [d for d in destinatarios if isinstance(d, str) and "@" in d]
    if not destinatarios:
        return _erro("Informe ao menos um destinatário (ou salve um na configuração).")

    # Sem data explícita, espelha o agendamento real: dia útil anterior.
    data_str = str(corpo.get("data", "")).strip()
    if not data_str:
        data_pub = dia_util_anterior(datetime.now(ZoneInfo("America/Sao_Paulo")).date())
    else:
        try:
            data_pub = date.fromisoformat(data_str)
        except ValueError:
            return _erro(f"Data inválida: {data_str!r}. Use AAAA-MM-DD.")

    # IA: respeita o toggle salvo, mas permite override no corpo do teste.
    usar_ia = bool(corpo.get("resumo_ia", cfg_r.get("resumo_ia", False)))

    try:
        resumo = _montar_e_enviar_relatorio(
            db, destinatarios, data_pub,
            cfg_v.get("palavras_chave", config_padrao.PALAVRAS_PADRAO),
            cfg_v.get("operador", config_padrao.OPERADOR_PADRAO),
            cfg_v.get("fontes", config_padrao.FONTES_PADRAO),
            usar_ia=usar_ia,
        )
        return _json_response({
            "enviado": True,
            "mensagem": f"Relatório de {data_pub.strftime('%d/%m/%Y')} enviado para "
                        f"{len(resumo['destinatarios'])} destinatário(s).",
            **resumo,
        })
    except EmailNaoConfigurado as e:
        return _erro(
            f"E-mail não configurado: {e} "
            "Defina os secrets SMTP no Firebase (ver README).",
            status=503,
        )
    except Exception as e:
        logger.exception("Falha ao enviar relatório de teste")
        return _erro(f"Falha ao enviar o e-mail: {e}", status=502)


# ---------------------------------------------------------------------------
# Função agendada: relatório diário por e-mail
# ---------------------------------------------------------------------------

@scheduler_fn.on_schedule(
    schedule="0 7 * * 1-5",
    timezone=scheduler_fn.Timezone("America/Sao_Paulo"),
    region=REGIAO,
    memory=options.MemoryOption.MB_512,
    timeout_sec=540,
    secrets=SECRETS,
)
def relatorio_diario(event: scheduler_fn.ScheduledEvent) -> None:
    db = _db()
    config = _carregar_config(db)
    cfg_r = config["relatorio"]
    cfg_v = config["varredura"]

    if not cfg_r.get("ativo"):
        logger.info("Relatório diário desativado (config/relatorio.ativo=false).")
        return

    destinatarios = cfg_r.get("destinatarios") or []
    if not destinatarios:
        logger.warning("Relatório ativo, mas sem destinatários. Abortando.")
        return

    # Às 07h a edição do próprio dia ainda não foi publicada — usa o dia útil
    # anterior (pula fins de semana e feriados fixos).
    hoje_sp = datetime.now(ZoneInfo("America/Sao_Paulo")).date()
    data_ref = dia_util_anterior(hoje_sp)
    try:
        resumo = _montar_e_enviar_relatorio(
            db, destinatarios, data_ref,
            cfg_v.get("palavras_chave", config_padrao.PALAVRAS_PADRAO),
            cfg_v.get("operador", config_padrao.OPERADOR_PADRAO),
            cfg_v.get("fontes", config_padrao.FONTES_PADRAO),
            usar_ia=bool(cfg_r.get("resumo_ia", False)),
        )
        logger.info(
            "Relatório da edição de %s enviado: %d publicações para %d destinatário(s).",
            data_ref.isoformat(), resumo["total"], len(resumo["destinatarios"]),
        )
    except EmailNaoConfigurado:
        logger.error("Relatório ativo mas SMTP não configurado — defina os secrets.")
    except Exception:
        logger.exception("Falha no envio do relatório diário.")
