"""
Serviço de raspagem de dados do Diário Oficial da União (DOU).

Utiliza Playwright para navegar dinamicamente pela plataforma
de Leitura do Jornal (https://www.in.gov.br/leiturajornal),
selecionar filtros e extrair publicações do dia.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Optional

import pandas as pd
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

URL_BASE = "https://www.in.gov.br/leiturajornal"
TIMEOUT_MS = 30_000          # tempo limite para operações de rede
WAIT_RESULTS_MS = 10_000     # tempo máximo para resultados aparecerem


# ---------------------------------------------------------------------------
# Função principal pública
# ---------------------------------------------------------------------------

def buscar_dou(
    data_publicacao: date,
    palavras_chave: list[str],
    secao: str = "do1",
    orgao: Optional[str] = "Ministério da Saúde",
    tipo_ato: Optional[str] = "Portaria",
) -> pd.DataFrame:
    """Realiza a busca no DOU e retorna um DataFrame filtrado por palavras-chave.

    Args:
        data_publicacao: Data da edição a consultar.
        palavras_chave:  Lista de termos para filtrar os resultados.
        secao:           Seção do DOU ('do1', 'do2', 'do3').
        orgao:           Texto parcial para selecionar no filtro de órgãos.
        tipo_ato:        Texto parcial para selecionar no filtro de tipo de ato.

    Returns:
        DataFrame com colunas: hierarquia, titulo, link, descricao.
        Se não houver resultados, retorna DataFrame vazio com as mesmas colunas.
    """

    data_fmt = data_publicacao.strftime("%d-%m-%Y")
    url = f"{URL_BASE}?data={data_fmt}&secao={secao}"

    resultados_brutos: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="pt-BR",
        )
        page = context.new_page()
        page.set_default_timeout(TIMEOUT_MS)

        try:
            page.goto(url, wait_until="domcontentloaded")
            _aguardar_pagina(page)

            # -- Aplicar filtro de Órgão ----------------------------------
            if orgao:
                _selecionar_opcao_por_texto(page, "#slcOrgs", orgao)
                _aguardar_resultados(page)

            # -- Aplicar filtro de Tipo de Ato ----------------------------
            if tipo_ato:
                _selecionar_opcao_por_texto(page, "#slcTipo", tipo_ato)
                _aguardar_resultados(page)

            # -- Extrair todas as páginas de resultados -------------------
            resultados_brutos = _extrair_todos_resultados(page)

        except PlaywrightTimeoutError:
            pass
        finally:
            browser.close()

    return _filtrar_por_palavras_chave(resultados_brutos, palavras_chave)


# ---------------------------------------------------------------------------
# Funções auxiliares internas
# ---------------------------------------------------------------------------

def _aguardar_pagina(page) -> None:
    """Aguarda que os elementos de filtro estejam disponíveis."""
    try:
        page.wait_for_selector("#slcOrgs", timeout=TIMEOUT_MS)
    except PlaywrightTimeoutError:
        pass


def _selecionar_opcao_por_texto(page, seletor_css: str, texto_alvo: str) -> None:
    """Seleciona no <select> a opção cujo texto contenha `texto_alvo`."""
    try:
        elemento = page.query_selector(seletor_css)
        if not elemento:
            return

        # Obtém o valor (value) da opção correspondente ao texto
        valor = page.evaluate(
            """([sel, texto]) => {
                const select = document.querySelector(sel);
                if (!select) return null;
                for (const opt of select.options) {
                    if (opt.text.toLowerCase().includes(texto.toLowerCase())) {
                        return opt.value;
                    }
                }
                return null;
            }""",
            [seletor_css, texto_alvo],
        )

        if valor:
            page.select_option(seletor_css, value=valor)
    except Exception:
        pass


def _aguardar_resultados(page) -> None:
    """Aguarda o carregamento dinâmico dos resultados após aplicar filtro."""
    try:
        # Tenta aguardar o aparecimento de pelo menos um resultado
        page.wait_for_selector(".resultado", timeout=WAIT_RESULTS_MS)
    except PlaywrightTimeoutError:
        pass


def _extrair_todos_resultados(page) -> list[dict]:
    """Varre todas as páginas e extrai os dados de cada card de resultado."""
    resultados: list[dict] = []
    pagina_num = 1

    while True:
        # Extrai os resultados da página atual via JavaScript
        novos = page.evaluate("""() => {
            const cards = document.querySelectorAll('.resultado');
            const dados = [];
            cards.forEach(card => {
                // --- Hierarquia ---
                const breadcrumbs = card.querySelectorAll('ol.dou-hierarquia li, ol.breadcrumb li');
                const hierarquia = Array.from(breadcrumbs).map(li => li.innerText.trim()).join(' › ');

                // --- Título e Link ---
                const titleTag = card.querySelector('h5.title-marker a, h5.title-marker');
                const titulo = titleTag ? titleTag.innerText.trim() : '';
                const href = titleTag && titleTag.tagName === 'A' ? titleTag.getAttribute('href') : 
                             (card.querySelector('h5.title-marker a') ? card.querySelector('h5.title-marker a').getAttribute('href') : '');

                // --- Descrição ---
                const descTag = card.querySelector('p.abstract-marker');
                const descricao = descTag ? descTag.innerText.trim() : '';

                if (titulo) {
                    dados.push({ hierarquia, titulo, link: href, descricao });
                }
            });
            return dados;
        }""")

        if not novos:
            break

        resultados.extend(novos)

        # Verifica se existe botão de próxima página
        proximo = page.query_selector("a.next-page, li.next > a, .pagination .next a")
        if not proximo:
            break

        try:
            proximo.click()
            page.wait_for_load_state("networkidle", timeout=WAIT_RESULTS_MS)
            pagina_num += 1
        except Exception:
            break

    return resultados


def _filtrar_por_palavras_chave(
    resultados: list[dict],
    palavras_chave: list[str],
) -> pd.DataFrame:
    """Retorna um DataFrame com os resultados que contém alguma palavra-chave."""

    COLUNAS = ["hierarquia", "titulo", "link", "descricao"]

    if not resultados:
        return pd.DataFrame(columns=COLUNAS)

    df = pd.DataFrame(resultados, columns=COLUNAS)

    # Se não foram fornecidas palavras-chave, retorna tudo
    palavras_limpas = [p.strip().lower() for p in palavras_chave if p.strip()]
    if not palavras_limpas:
        return df

    # Constrói máscara: qualquer palavra-chave presente no título OU na descrição
    padrao = "|".join(re.escape(p) for p in palavras_limpas)
    mascara = (
        df["titulo"].str.lower().str.contains(padrao, na=False)
        | df["descricao"].str.lower().str.contains(padrao, na=False)
    )
    return df[mascara].reset_index(drop=True)
