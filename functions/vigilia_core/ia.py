"""
Síntese por IA dos resultados da varredura (Google AI Studio / Gemini).

PREPARADO PARA USO FUTURO — desativado por padrão.

Quando ativado, gera um resumo executivo em linguagem natural das publicações
encontradas, para destacar no topo do relatório por e-mail. Não há nenhuma
chamada de rede enquanto `resumo_disponivel()` for False (ausência de API key).

Ativação futura (sem alterar o restante do sistema):
  1. Crie uma API key no Google AI Studio: https://aistudio.google.com/apikey
  2. Defina o secret no projeto:
        firebase functions:secrets:set GEMINI_API_KEY
  3. Inclua GEMINI_API_KEY na lista `secrets=[...]` das funções que usam IA
     em functions/main.py (já comentado lá) e adicione
        google-genai>=1.0.0
     em functions/requirements.txt.
  4. Ative no Firestore (config/relatorio.resumo_ia = true) ou pela SPA.

O modelo padrão é o Gemini Flash (rápido e econômico); ajuste em MODELO_PADRAO.
"""

from __future__ import annotations

import logging
import os
import time

logger = logging.getLogger("vigilia.ia")

MODELO_PADRAO = "gemini-2.5-flash"

# Limita o volume enviado ao modelo (controle de custo/latência).
# Como agora enviamos o TEXTO COMPLETO do DOU (e não a prévia de ~400 chars),
# elevamos o limite por publicação para o modelo "ler" o ato inteiro.
MAX_PUBLICACOES_NO_PROMPT = 150
MAX_CHARS_POR_PUBLICACAO = 3000


def resumo_disponivel() -> bool:
    """True somente se houver API key configurada (secret GEMINI_API_KEY)."""
    return bool(os.environ.get("GEMINI_API_KEY", "").strip())


def _amostra_balanceada(resultados: list[dict], limite: int) -> list[dict]:
    """
    Seleciona até `limite` publicações intercalando as fontes (round-robin por
    'origem'), para que DOU e DOE-SC fiquem ambos representados mesmo quando há
    muito mais de uma fonte (antes o corte simples pegava só as primeiras, que
    eram todas do DOU).
    """
    if len(resultados) <= limite:
        return resultados

    por_origem: dict[str, list[dict]] = {}
    for r in resultados:
        por_origem.setdefault(r.get("origem", "?"), []).append(r)

    amostra: list[dict] = []
    filas = list(por_origem.values())
    i = 0
    while len(amostra) < limite and any(filas):
        fila = filas[i % len(filas)]
        if fila:
            amostra.append(fila.pop(0))
        i += 1
        if i % len(filas) == 0:
            filas = [f for f in filas if f]
            if not filas:
                break
    return amostra


SYSTEM_INSTRUCTION = (
    'Você é o motor de Inteligência Artificial do "Vigília", um analista '
    "especialista do Setor de Convênios e Parcerias da Saúde de Joinville. Você "
    "RACIOCINA sobre cada publicação — lê o texto completo, entende a natureza do "
    "ato e decide se importa para o setor. NÃO preencha um template mecanicamente: "
    "pense criticamente e descarte o que não for relevante.\n\n"
    "DIRETRIZ 1 — TRIAGEM E DESCARTE (filtro de contexto).\n"
    "Mesmo que o texto contenha as palavras-chave configuradas (Joinville, "
    "portaria, sigtap etc.), aplique uma SEGUNDA camada de filtragem e IGNORE/"
    "REJEITE sumariamente:\n"
    "a) Atos de Recursos Humanos / Pessoal: nomeações, exonerações, concessões de "
    "férias, licenças, dispensas, designações ou gratificações de servidores "
    "(inclusive da própria Saúde, ou de Secretarias de Justiça/Segurança).\n"
    "b) Contratos de OUTRAS secretarias: licitações, dispensas ou inexigibilidades "
    "de Educação, Assistência Social ou Administração — mesmo que usem tabelas da "
    "saúde como referência de preço (ex.: contratação de creches pela SIGTAP).\n"
    "c) Atos meramente administrativos/conselhos: designação de membros de "
    "comissões, câmaras técnicas, grupos de trabalho ou conselhos que NÃO criem "
    "obrigação contratual nem prazo de adesão a programa.\n"
    "d) Falsos positivos geográficos: menções a outros municípios homônimos, a "
    "menos que Joinville seja explicitamente a beneficiária do ato.\n\n"
    "DIRETRIZ 2 — CRITÉRIOS DE INCLUSÃO (só processe estes).\n"
    "Apenas gere blocos para atos que se enquadrem em UMA das três categorias:\n"
    "1. FINANCEIRO E ORÇAMENTÁRIO: repasses financeiros, habilitação de leitos/"
    "serviços, tetos financeiros, emendas parlamentares, acréscimos temporários/"
    "permanentes de custeio para a saúde de Joinville.\n"
    "2. CHAMAMENTOS E EDITAIS: prazos abertos para o município aderir a programas "
    "federais/estaduais, ou editais do município para contratar entidades "
    "filantrópicas/OSCs (MROSC, Lei 13.019/14).\n"
    "3. REGULAÇÃO DE CONTRATOS/TABELAS: alterações na tabela SIGTAP que mudem o "
    "faturamento direto de hospitais conveniados ao município (ex.: Hospital "
    "Municipal São José, Hospital Bethesda).\n\n"
    "DIRETRIZ 3 — CONSOLIDAÇÃO. Se vários atos tratarem do MESMO programa/assunto "
    "(ex.: dezenas de habilitações do \"Agora Tem Especialistas\"), agrupe todos "
    "em UM único bloco, liste os números das portarias em sequência e sintetize o "
    "impacto coletivo — nunca repita um bloco por ato.\n\n"
    "ESTILO: emojis semânticos (não decorativos); valores financeiros em negrito "
    "(ex.: **R$ 1.500.000,00**); seja direto, sem jargão repetitivo; destaque "
    "prazos.\n\n"
    "FORMATO DO OUTPUT (Markdown):\n\n"
    "✦ **Vigília IA · Análise de Impacto**\n\n"
    "## 📊 Panorama do Dia\n"
    "* [🟢 Baixo | 🟡 Moderado | 🔴 Crítico] **Volume:** [N] atos relevantes "
    "(de [T] publicações varridas).\n"
    "* **Foco Principal:** [frase única com o acontecimento mais importante].\n\n"
    "## 🎯 Atos Relevantes para Convênios & Parcerias\n"
    "[Para CADA ato (ou grupo consolidado) aprovado na triagem, use o bloco "
    "abaixo. Ordene por impacto financeiro/urgência. A CATEGORIA é uma das três "
    "da Diretriz 2.]\n\n"
    "### 📑 [CATEGORIA] [Nome do Programa ou Recurso]\n"
    "* **Identificação do(s) ato(s):** [Tipo, Número/Ano e Órgão emissor — liste "
    "todos os números se consolidado].\n"
    "* **Entidade-alvo em Joinville:** [SMS, Hospital Municipal São José, Hospital "
    "Bethesda, rede municipal etc.].\n"
    "* **Resumo prático:** [impacto para o gestor: \"Libera recurso para…\", "
    "\"Altera o valor do procedimento X no SUS…\"].\n"
    "* 💰 **Impacto financeiro:** [valor em destaque; se estiver em anexo, escreva "
    "\"Valor sob consulta nos anexos do ato\"].\n"
    "* ⏳ **Prazos e providências do setor:** [ação que o setor precisa tomar e "
    "prazo-limite; se for execução contínua, \"Fluxo contínuo\"].\n\n"
    "## ⚡ Próximos Passos Recomendados\n"
    "* ▢ **[Setor, ex: Financeiro/Contratos]:** [ação verbal clara] - "
    "*Motivo: [risco/oportunidade].*\n\n"
    "REGRAS ABSOLUTAS\n"
    "- Se, após a triagem, NENHUM ato se enquadrar nos critérios de inclusão, o "
    "output deve ser ESTRITAMENTE: \"✦ **Vigília IA:** Nenhuma publicação de alto "
    "impacto ou com potencial de repasse financeiro foi identificada nesta edição "
    "para os termos monitorados.\"\n"
    "- Nunca invente valores. Sem valor explícito, escreva: \"Valor sob consulta "
    "nos anexos do ato\"."
)


def _montar_prompt(
    resultados: list[dict],
    data_br: str,
    palavras: list[str],
    avisos: list[str] | None = None,
) -> str:
    amostra = _amostra_balanceada(resultados, MAX_PUBLICACOES_NO_PROMPT)
    linhas = []
    for i, r in enumerate(amostra, 1):
        corpo = (r.get("resumo") or r.get("descricao") or "")[:MAX_CHARS_POR_PUBLICACAO]
        origem = r.get("origem", "")
        link = r.get("link", "")
        linhas.append(
            f"[{i}] ({origem}) {r.get('titulo', '')}\n"
            f"     {corpo.strip()}\n"
            f"     fonte: {link}"
        )
    termos = ", ".join(palavras) if palavras else "(sem filtro — todas as publicações do dia)"
    corpo_lista = "\n\n".join(linhas) if linhas else "(nenhuma publicação)"
    total = len(resultados)

    nota_amostra = (
        f" (a lista abaixo traz as {MAX_PUBLICACOES_NO_PROMPT} primeiras para análise)"
        if total > MAX_PUBLICACOES_NO_PROMPT else ""
    )
    nota_parcial = ""
    if avisos:
        nota_parcial = (
            "\n\nATENÇÃO — DADOS PARCIAIS: " + " ".join(avisos) +
            " Avise isso ao final do Panorama."
        )

    return (
        f"DATA DA EDIÇÃO: {data_br}\n"
        f"TERMOS MONITORADOS: {termos}\n"
        f"TOTAL DE PUBLICAÇÕES VARRIDAS: {total}{nota_amostra}{nota_parcial}\n\n"
        "TAREFA: aplique a triagem das suas instruções (descarte RH, contratos de "
        "outras pastas, atos administrativos e falsos positivos) e produza a "
        "síntese SÓ com os atos que se enquadram nos critérios de inclusão, "
        "seguindo EXATAMENTE o template Markdown. No campo Volume, informe quantos "
        f"atos relevantes você aprovou, de um total de {total} varridos.\n\n"
        f"PUBLICAÇÕES:\n{corpo_lista}"
    )


def gerar_resumo(
    resultados: list[dict],
    data_br: str,
    palavras: list[str],
    modelo: str | None = None,
    avisos: list[str] | None = None,
) -> str | None:
    """
    Gera um resumo executivo das publicações via Gemini.

    Retorna o texto do resumo, ou None se a IA não estiver configurada
    (sem API key) ou se a chamada falhar — nesses casos o relatório é enviado
    normalmente, apenas sem o bloco de síntese.
    """
    if not resumo_disponivel():
        logger.info("Resumo por IA ignorado: GEMINI_API_KEY não configurada.")
        return None
    if not resultados:
        return None

    try:
        # Import tardio: a dependência só é necessária quando a IA está ativa.
        from google import genai  # type: ignore
        from google.genai import types  # type: ignore
        from google.genai import errors as genai_errors  # type: ignore
    except ImportError:
        logger.warning(
            "Pacote 'google-genai' não instalado — adicione-o em "
            "functions/requirements.txt para habilitar o resumo por IA."
        )
        return None

    cliente = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    prompt = _montar_prompt(resultados, data_br, palavras, avisos=avisos)
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        temperature=0.3,          # baixa: factual e estável
        max_output_tokens=4096,   # resposta + raciocínio
        # Triagem/descarte e consolidação exigem RACIOCÍNIO — habilitamos o
        # "thinking" dinâmico do 2.5 (o modelo decide quanto pensar). O
        # max_output_tokens generoso evita truncar a resposta final.
        thinking_config=types.ThinkingConfig(thinking_budget=-1),
    )

    # O Gemini retorna 503 (sobrecarga) e 429 (limite/minuto) de forma
    # transitória. Tentamos algumas vezes com backoff antes de desistir; se
    # nada der certo, retornamos None e o relatório segue sem o bloco de IA.
    transitorios = {429, 500, 502, 503, 504}
    ultima_excecao = None
    for tentativa in range(3):
        try:
            resposta = cliente.models.generate_content(
                model=modelo or MODELO_PADRAO,
                contents=prompt,
                config=config,
            )
            return (getattr(resposta, "text", "") or "").strip() or None
        except genai_errors.APIError as e:
            ultima_excecao = e
            if getattr(e, "code", None) in transitorios and tentativa < 2:
                espera = 2 * (tentativa + 1)
                logger.warning(
                    "Gemini %s (tentativa %d/3) — repetindo em %ds.",
                    getattr(e, "code", "?"), tentativa + 1, espera,
                )
                time.sleep(espera)
                continue
            break
        except Exception as e:
            ultima_excecao = e
            break

    logger.warning(
        "Falha ao gerar resumo por IA (%s) — relatório segue sem o bloco.",
        ultima_excecao,
    )
    return None
