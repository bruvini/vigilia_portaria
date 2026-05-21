"""
Serviço de busca do Diário Oficial de Santa Catarina (DOE-SC).

Integração direta com o endpoint oficial do portal DOE-SC:
    POST https://portal.doe.sea.sc.gov.br/apis/busca-materia

Descoberto via inspeção de tráfego de rede (21/05/2026).
Payload confirmado:
    {
        "busca": "",            # palavra-chave vazia = todas as publicações do dia
        "dtIni": "YYYY-MM-DD",
        "dtFim": "YYYY-MM-DD",
        "tipoBusca": 2,
        "pagination": {"from": 0, "size": 1000},
        "resumo": false,
        "aCdAssunto": [],
        "aCdCategoria": []
    }

Características:
  - Sem CKAN, sem CSV, sem dados.sc.gov.br
  - Sem cache local, sem fallback por ano
  - Paginação automática: extrai todas as publicações em loop
  - Filtragem local por palavras-chave (case/acento insensitive)
  - Retorna DataFrame padronizado com as colunas do frontend
"""

from __future__ import annotations

import logging
import re
import unicodedata
from datetime import date

import pandas as pd
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="[DOE-SC DIRETO] %(levelname)s: %(message)s")

# ---------------------------------------------------------------------------
# Configurações e Constantes
# ---------------------------------------------------------------------------

ENDPOINT = "https://portal.doe.sea.sc.gov.br/apis/busca-materia"

HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}

# Tamanho máximo da página confirmado nos testes (retornou 480 registros em 1 requisição)
PAGE_SIZE = 1000

COLUNAS = [
    "origem",
    "hierarquia",
    "titulo",
    "link",
    "link_certificado",
    "descricao",
    "resumo",
    "tipo",
    "orgao",
    "pagina",
    "palavra_encontrada",
]


# ---------------------------------------------------------------------------
# Helpers de Texto
# ---------------------------------------------------------------------------

def _remover_acentos(texto: str) -> str:
    """Remove acentos e normaliza para minúsculas."""
    if not isinstance(texto, str):
        return ""
    return (
        unicodedata.normalize("NFKD", texto)
        .encode("ascii", "ignore")
        .decode("utf-8")
        .lower()
    )


def _extrair_tipo(titulo: str, assunto: str) -> str:
    """Extrai o tipo do ato a partir do início do título ou assunto."""
    for texto in [titulo, assunto]:
        m = re.search(
            r"\b(PORTARIA|DECRETO|RESOLUÇÃO|EDITAL|EXTRATO|AVISO|ATA|LEI|INSTRUÇÃO)\b",
            texto,
            re.IGNORECASE,
        )
        if m:
            return m.group(1).upper()
    return "ATO"


# ---------------------------------------------------------------------------
# Função Principal de Busca
# ---------------------------------------------------------------------------

def buscar_doesc_direto(
    data_publicacao: date,
    palavras_chave: list[str],
    operador: str = "OU",
) -> pd.DataFrame:
    """
    Busca publicações no DOE-SC via endpoint oficial em tempo real.

    Parâmetros:
        data_publicacao: data de publicação a consultar.
        palavras_chave: lista de termos para filtrar localmente.

    Parâmetros:
        operador: "OU" (any — retorna se qualquer termo bater) ou
                  "E"  (all — retorna somente se TODOS os termos baterem).

    Retorna:
        pd.DataFrame com as colunas padronizadas do frontend Vigília.
        Retorna DataFrame vazio estruturado em caso de falha ou sem resultados.

    Fluxo:
        1. Faz POST paginado para /apis/busca-materia (dtIni=dtFim=data)
        2. Coleta TODAS as publicações do dia em memória
        3. Filtra localmente com operador AND/OR (acento/case insensitive)
        4. Mapeia os campos do JSON para as colunas do DataFrame
    """
    dt_str = data_publicacao.strftime("%Y-%m-%d")
    dt_br = data_publicacao.strftime("%d/%m/%Y")
    logger.info(f"Consultando DOE-SC para {dt_br}")

    session = requests.Session()
    session.headers.update(HEADERS)

    # ------------------------------------------------------------------
    # Passo 1: Coletar todas as publicações do dia (paginação automática)
    # ------------------------------------------------------------------
    all_materias: list[dict] = []
    from_idx = 0
    pagina = 1

    while True:
        payload = {
            "busca": "",            # busca vazia = sem filtro de texto no servidor
            "dtIni": dt_str,
            "dtFim": dt_str,
            "tipoBusca": 2,
            "pagination": {"from": from_idx, "size": PAGE_SIZE},
            "resumo": False,
            "aCdAssunto": [],
            "aCdCategoria": [],
        }

        try:
            r = session.post(ENDPOINT, json=payload, timeout=25)
        except requests.exceptions.Timeout:
            logger.error(f"Timeout na requisição para o endpoint DOE-SC (página {pagina})")
            break
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Erro de conexão ao endpoint DOE-SC: {e}")
            break
        except Exception as e:
            logger.error(f"Erro inesperado na requisição DOE-SC: {e}")
            break

        if r.status_code != 200:
            logger.error(
                f"Endpoint retornou status {r.status_code}. "
                f"Resposta: {r.text[:200]}"
            )
            break

        try:
            data_json = r.json()
        except ValueError:
            logger.error(f"Resposta não-JSON do endpoint DOE-SC: {r.text[:200]}")
            break

        logger.info("Endpoint oficial respondeu com sucesso")

        materias = data_json.get("materias", [])
        if not materias:
            logger.info(f"Página {pagina}: sem registros. Encerrando paginação.")
            break

        all_materias.extend(materias)
        total_servidor = data_json.get("total", 0)
        logger.info(f"Página {pagina} carregada com {len(materias)} registros")

        if len(all_materias) >= total_servidor or len(materias) < PAGE_SIZE:
            break

        from_idx += PAGE_SIZE
        pagina += 1

    logger.info(f"Total consolidado: {len(all_materias)} publicações")

    if not all_materias:
        logger.info(f"Nenhuma publicação encontrada para {dt_br}")
        return pd.DataFrame(columns=COLUNAS)

    # ------------------------------------------------------------------
    # Passo 2: Filtro local por palavras-chave (AND/OR, acento/case insensitive)
    # ------------------------------------------------------------------
    palavras_limpas = [_remover_acentos(p.strip()) for p in palavras_chave if p.strip()]
    modo_and = operador.strip().upper() == "E"
    logger.info(f"Modo de busca: {'E (AND)' if modo_and else 'OU (OR)'}")

    # ------------------------------------------------------------------
    # Passo 3: Mapear para DataFrame padronizado
    # ------------------------------------------------------------------
    resultados: list[dict] = []

    for mat in all_materias:
        resumo_texto = mat.get("resumo") or ""
        assunto = mat.get("assunto") or ""
        categoria = mat.get("categoria") or ""

        # Normalização para busca local
        resumo_norm = _remover_acentos(resumo_texto)
        assunto_norm = _remover_acentos(assunto)
        categoria_norm = _remover_acentos(categoria)

        # Texto consolidado para matching
        texto_completo = " ".join([resumo_norm, assunto_norm, categoria_norm])

        # Filtro por palavras-chave com suporte a AND/OR
        matched_keyword = ""
        if palavras_limpas:
            resultados_match = [clean_k in texto_completo for clean_k in palavras_limpas]

            if modo_and:
                matched = all(resultados_match)
            else:
                matched = any(resultados_match)

            if not matched:
                continue

            # Listar todos os termos que deram match (útil especialmente no modo E)
            encontrados = [
                orig
                for orig, limpa in zip(palavras_chave, palavras_limpas)
                if limpa in texto_completo
            ]
            matched_keyword = ", ".join(encontrados)

        # Extrair título a partir do resumo (primeira linha não-vazia)
        linhas = [l.strip() for l in resumo_texto.split("\n") if l.strip()]
        titulo_extraido = linhas[0] if linhas else assunto
        if len(titulo_extraido) > 200:
            titulo_extraido = titulo_extraido[:197] + "..."

        # Link para a publicação (campo extrato já contém a URL oficial)
        link_url = mat.get("extrato") or ""
        if not link_url:
            cd_jornal = mat.get("cdJornal")
            mat_id = mat.get("id")
            if cd_jornal and mat_id:
                link_url = (
                    f"https://portal.doe.sea.sc.gov.br"
                    f"/#/portal/edicao/{cd_jornal}/materia/{mat_id}"
                )

        tipo = _extrair_tipo(titulo_extraido, assunto)

        resultados.append({
            "origem": "DOE-SC",
            "hierarquia": f"DOE-SC › {categoria} › {assunto}",
            "titulo": titulo_extraido,
            "link": link_url,
            "link_certificado": link_url,
            "descricao": resumo_texto,
            "resumo": resumo_texto,
            "tipo": tipo,
            "orgao": categoria if categoria else "Estado de Santa Catarina",
            "pagina": "",
            "palavra_encontrada": matched_keyword,
        })

    df_final = pd.DataFrame(resultados, columns=COLUNAS)
    logger.info(f"{len(df_final)} publicações compatíveis com os filtros")
    return df_final


# ---------------------------------------------------------------------------
# Alias de compatibilidade (mantém imports antigos funcionando)
# ---------------------------------------------------------------------------
def buscar_doesc(
    data_publicacao: date,
    palavras_chave: list[str],
    operador: str = "OU",
) -> pd.DataFrame:
    """Alias para buscar_doesc_direto — mantém compatibilidade com imports legados."""
    return buscar_doesc_direto(
        data_publicacao=data_publicacao,
        palavras_chave=palavras_chave,
        operador=operador,
    )
