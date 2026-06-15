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

logger = logging.getLogger("vigilia.ia")

MODELO_PADRAO = "gemini-2.5-flash"

# Limita o volume enviado ao modelo (controle de custo/latência).
MAX_PUBLICACOES_NO_PROMPT = 60
MAX_CHARS_POR_PUBLICACAO = 600


def resumo_disponivel() -> bool:
    """True somente se houver API key configurada (secret GEMINI_API_KEY)."""
    return bool(os.environ.get("GEMINI_API_KEY", "").strip())


SYSTEM_INSTRUCTION = (
    "Você é analista sênior de inteligência regulatória da Secretaria Municipal "
    "da Saúde de Joinville (SC), na Unidade de Convênios e Parcerias. Sua função "
    "é ler as publicações dos diários oficiais e produzir uma síntese executiva "
    "diária para gestores — objetiva, confiável e acionável.\n\n"
    "PRINCÍPIOS:\n"
    "- Escreva em português formal, claro e direto, sem jargão de IA.\n"
    "- NUNCA invente fatos, números, prazos ou nomes que não estejam nas "
    "publicações fornecidas. Fidelidade absoluta à fonte.\n"
    "- Priorize o que afeta a gestão municipal de saúde de Joinville: repasses e "
    "incentivos financeiros, habilitações de serviços/leitos, convênios e "
    "parcerias, credenciamentos, prazos e chamamentos, e portarias que citem "
    "diretamente Joinville ou Santa Catarina.\n"
    "- Quantifique quando possível (valores, nº de portarias, prazos).\n"
    "- Se nada for materialmente relevante para Joinville, diga isso em uma "
    "frase, sem floreio."
)


def _montar_prompt(resultados: list[dict], data_br: str, palavras: list[str]) -> str:
    linhas = []
    for i, r in enumerate(resultados[:MAX_PUBLICACOES_NO_PROMPT], 1):
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
        "TAREFA: produza a síntese executiva do dia para quem está vendo este "
        "resultado (no painel do site ou no e-mail). Use EXATAMENTE estes rótulos "
        "em MAIÚSCULAS, cada um em sua própria linha, seguido do texto; omita uma "
        "seção apenas se realmente não houver nada para ela:\n\n"
        f"PANORAMA: comece dizendo, em números, quantas publicações foram "
        f"encontradas ({total}) e dê a leitura geral do dia em 1 a 2 frases — se o "
        "volume é alto ou baixo e se há algo que exige atenção imediata.\n"
        "DESTAQUES PARA JOINVILLE: 2 a 4 itens em tópicos (use '• '). Em cada um, "
        "explique com clareza, em linguagem simples, O QUE a publicação diz e POR "
        "QUE isso importa para quem acompanha a saúde de Joinville (cite o tipo do "
        "ato e, quando houver, valor, prazo ou serviço afetado). Se nada citar "
        "Joinville diretamente, traga o que mais se aproxima do interesse municipal "
        "e diga isso.\n"
        "RECOMENDAÇÃO: 1 frase com a próxima ação sugerida (ex.: verificar adesão, "
        "observar prazo, encaminhar à área responsável). Omita se não houver ação "
        "cabível.\n\n"
        "Seja claro e direto, no máximo ~190 palavras no total. Não invente nada "
        "que não esteja nas publicações.\n\n"
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

        cliente = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        prompt = _montar_prompt(resultados, data_br, palavras)
        resposta = cliente.models.generate_content(
            model=modelo or MODELO_PADRAO,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=0.3,          # baixa: factual e estável
                max_output_tokens=1200,
                # Os modelos 2.5 "pensam" antes de responder, consumindo o
                # orçamento de tokens. Para um resumo estruturado isso é
                # desnecessário e trunca a saída — desligamos o thinking.
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        texto = (getattr(resposta, "text", "") or "").strip()
        return texto or None
    except ImportError:
        logger.warning(
            "Pacote 'google-genai' não instalado — adicione-o em "
            "functions/requirements.txt para habilitar o resumo por IA."
        )
        return None
    except Exception:
        logger.exception("Falha ao gerar resumo por IA — relatório segue sem o bloco.")
        return None
