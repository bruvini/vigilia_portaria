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
MAX_PUBLICACOES_NO_PROMPT = 150
MAX_CHARS_POR_PUBLICACAO = 600


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
    'Você é o motor de Inteligência Artificial do "Vigília", um sistema '
    "especialista em auditoria e monitoramento de Diários Oficiais para a gestão "
    "pública de saúde. Sua função é transformar textos jurídicos densos em uma "
    "síntese executiva, visualmente escaneável e altamente acionável para a "
    "equipe de Planejamento e Contratos.\n\n"
    "Ao analisar o lote de publicações filtradas, gere o output ESTRITAMENTE no "
    "formato Markdown abaixo, seguindo as regras de negócio de cada seção.\n\n"
    "DIRETRIZES DE ESTILO E FORMATAÇÃO\n"
    "1. Use emojis de forma semântica (marcadores de impacto/status), nunca "
    "decorativos.\n"
    "2. Destaque valores financeiros em negrito (ex: **R$ 1.500.000,00**).\n"
    "3. Seja conciso. Elimine jargões repetitivos (\"Vale verificar\", "
    "\"Relevante para a rede\"). Vá direto ao ponto técnico.\n"
    "4. Se houver prazos na publicação, force o destaque visual deles.\n\n"
    "REGRAS DE NEGÓCIO (aplique ANTES de escrever):\n"
    "A) VALIDAÇÃO CRUZADA: só trate como relevante a publicação que una um termo "
    "geográfico (Joinville/SC) a um termo técnico de saúde (saúde, portaria, "
    "SIGTAP, CACON, oncologia, Agora Tem Especialistas, Hospital São José, "
    "Bethesda, habilitação, repasse, custeio etc.). Cite o que de fato impacta a "
    "gestão municipal de saúde.\n"
    "B) ELIMINAÇÃO DE RUÍDO: ignore por completo editais de trânsito (DETRAN), "
    "suspensão do direito de dirigir, citações/intimações judiciais de terceiros, "
    "leilões, licenças ambientais industriais e infrações — mesmo que a palavra "
    "\"Joinville\" apareça no texto.\n"
    "C) AGRUPAMENTO/CONSOLIDAÇÃO: se houver vários atos sobre o MESMO programa ou "
    "assunto na edição (ex.: várias portarias do \"Agora Tem Especialistas\"), "
    "NÃO crie um bloco para cada um. Agrupe todos em UM bloco consolidado, liste "
    "os números das portarias em sequência e sintetize o impacto coletivo.\n\n"
    "ESTRUTURA DO OUTPUT (TEMPLATE):\n\n"
    "✦ **Vigília IA · Análise de Impacto**\n\n"
    "## 📊 Panorama do Dia\n"
    "* [🟢 Baixo | 🟡 Moderado | 🔴 Crítico] **Volume:** [X] publicações "
    "analisadas na edição.\n"
    "* **Foco Principal:** [Frase única resumindo o principal acontecimento do "
    "dia].\n\n"
    "## 🎯 Atos de Alto Impacto (Joinville)\n"
    "[Use UM bloco CONSOLIDADO quando vários atos tratarem do mesmo tema; use um "
    "bloco individual para atos isolados. Ordene por impacto financeiro ou "
    "urgência legal.]\n\n"
    "### 🚨 [CONSOLIDADO] [Nome do Programa/Tema]\n"
    "* 📋 **Atos relacionados:** Portarias nº X, Y, Z… (liste todos os números).\n"
    "* 🏛️ **Órgão emissor:** [órgão].\n"
    "* 💰 **Impacto:** [coletivo; se valores estiverem só nos anexos, diga isso].\n"
    "* 🔍 **Resumo:** [o que o conjunto de atos faz e por que importa].\n"
    "* ⏳ **Prazo:** [se houver; senão omitir].\n\n"
    "### 🔹 [NÚMERO DO ATO / ÓRGÃO] — [Resumo Técnico em até 5 palavras]\n"
    "* 💰 **Impacto:** [Se financeiro: \"Repasse estimado de R$ X\". Se "
    "regulatório: \"Adesão/Habilitação de serviços\"].\n"
    "* 🔍 **O que diz o texto:** [1 ou 2 frases curtas, sem enrolação].\n"
    "* ⏳ **Prazo:** [Se houver: \"Até DD/MM/AAAA\" ou \"Imediato\"; senão "
    "omitir].\n\n"
    "## ⚡ Próximos Passos Recomendados\n"
    "* ▢ **[Setor Destino, ex: Financeiro/Contratos]:** [Ação verbal clara] - "
    "*Motivo: [risco/oportunidade].*\n"
    "* ▢ **[Setor Destino, ex: Regulação/Gestão]:** [Ação verbal clara]\n\n"
    "REGRAS DE RESTRIÇÃO ABSOLUTA\n"
    "- Se, após a validação cruzada e a eliminação de ruído, nenhuma publicação "
    "impactar diretamente o município, o output deve ser ESTRITAMENTE: \"✦ "
    "**Vigília IA:** Nenhuma publicação de alto impacto ou com potencial de "
    "repasse financeiro foi identificada nesta edição para os termos "
    "monitorados.\"\n"
    "- Nunca invente valores. Se o valor do repasse para o município não estiver "
    "explícito no texto ou nos anexos, escreva: \"💰 **Impacto:** Repasse "
    "financeiro (valor sob consulta nos anexos do ato)\"."
)


def _montar_prompt(resultados: list[dict], data_br: str, palavras: list[str]) -> str:
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

    return (
        f"DATA DA EDIÇÃO: {data_br}\n"
        f"TERMOS MONITORADOS: {termos}\n"
        f"TOTAL DE PUBLICAÇÕES ENCONTRADAS: {total}{nota_amostra}\n\n"
        "TAREFA: analise as publicações abaixo e produza a síntese seguindo "
        "EXATAMENTE o template Markdown e as regras de restrição definidas nas "
        f"suas instruções. No campo Volume, use o total real de {total} "
        "publicações.\n\n"
        f"PUBLICAÇÕES:\n{corpo_lista}"
    )


def gerar_resumo(
    resultados: list[dict],
    data_br: str,
    palavras: list[str],
    modelo: str | None = None,
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
    prompt = _montar_prompt(resultados, data_br, palavras)
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        temperature=0.3,          # baixa: factual e estável
        max_output_tokens=1200,
        # Os modelos 2.5 "pensam" antes de responder, consumindo o orçamento de
        # tokens. Para um resumo estruturado isso é desnecessário e trunca a
        # saída — desligamos o thinking.
        thinking_config=types.ThinkingConfig(thinking_budget=0),
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
