"""
Serviço de raspagem de dados do Diário Oficial do Estado de Santa Catarina (DOE-SC).

Portal: https://portal.doe.sea.sc.gov.br/v2.43.01/#/portal
Framework: Angular + PrimeNG

Fluxo validado por mapeamento DOM real:
  1. Acessa o portal e clica em "Buscar Edições"
  2. Abre o modal de Filtros (botão com ícone pi-filter)
  3. Preenche Data Início e Data Fim com a data fornecida
  4. Clica em "Aplicar" para filtrar edições
  5. Para cada edição encontrada (tipo Ordinária e Extra):
     a. Clica em "Abrir" na edição
     b. No modal de escolha de formato, clica em "EXTRATO DE PUBLICAÇÃO CERTIFICADA"
     c. Aplica filtros de Categoria e Assunto dentro do visualizador
     d. Extrai o conteúdo textual dos atos encontrados
  6. Filtra os resultados pelas palavras-chave do usuário
"""

from __future__ import annotations

import re
from datetime import date

import pandas as pd
from playwright.sync_api import (
    Page,
    sync_playwright,
    TimeoutError as PlaywrightTimeoutError,
)


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

URL_BASE  = "https://portal.doe.sea.sc.gov.br/v2.43.01/#/portal"
TIMEOUT   = 30_000
WAIT_SM   = 2_000
WAIT_MD   = 6_000
WAIT_LG   = 12_000

# Categorias que serão pesquisadas (textos parciais para match flexível)
CATEGORIAS_ALVO = [
    "Saúde",         # captura "Secretaria de Estado / Saúde"
    "Joinville",     # captura "Prefeituras Municipais / Joinville"
]

COLUNAS = ["origem", "hierarquia", "titulo", "link", "descricao"]


# ---------------------------------------------------------------------------
# Função principal pública
# ---------------------------------------------------------------------------

def buscar_doesc(
    data_publicacao: date,
    palavras_chave: list[str],
) -> pd.DataFrame:
    """Realiza a busca no DOE-SC e retorna DataFrame filtrado por palavras-chave.

    Args:
        data_publicacao: Data da edição a consultar.
        palavras_chave:  Lista de termos para filtrar os resultados.

    Returns:
        DataFrame com colunas: origem, hierarquia, titulo, link, descricao.
    """

    data_fmt = data_publicacao.strftime("%d/%m/%Y")
    todos: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="pt-BR",
            viewport={"width": 1440, "height": 900},
        )
        page = ctx.new_page()
        page.set_default_timeout(TIMEOUT)

        try:
            # ── 1. Navegar até a listagem de edições ──────────────────────
            page.goto(URL_BASE, wait_until="domcontentloaded")
            _wait_angular(page)

            page.click("a:has-text('Buscar Edições')")
            _wait_angular(page)

            # ── 2. Aplicar filtro de data ─────────────────────────────────
            _aplicar_filtro_data(page, data_fmt)

            # ── 3. Coletar edições disponíveis (Ordinária + Extra) ────────
            edicoes = _listar_edicoes(page)

            # ── 4. Processar cada edição ──────────────────────────────────
            for idx, edicao in enumerate(edicoes[:3]):   # limita às 3 primeiras
                resultados_edicao = _processar_edicao(
                    page, idx, edicao, palavras_chave
                )
                todos.extend(resultados_edicao)

        except Exception:
            pass
        finally:
            browser.close()

    if not todos:
        return pd.DataFrame(columns=COLUNAS)

    return pd.DataFrame(todos, columns=COLUNAS)


# ---------------------------------------------------------------------------
# ETAPA 2 – Filtro de data no modal
# ---------------------------------------------------------------------------

def _aplicar_filtro_data(page: Page, data_fmt: str) -> None:
    """Abre o modal de filtros, preenche as datas e clica em Aplicar."""
    try:
        # Abre o modal de filtros — botão com ícone .pi-filter
        btn_filtro = page.query_selector("button:has(.pi-filter)")
        if not btn_filtro:
            btn_filtro = page.query_selector("button:has-text('Filtros')")
        if btn_filtro:
            btn_filtro.click()
            page.wait_for_timeout(WAIT_SM)

        # Aguarda o p-dialog ficar visível
        try:
            page.wait_for_selector("p-dialog input, .p-dialog input", timeout=WAIT_MD)
        except PlaywrightTimeoutError:
            return

        # Preenche Data Início (primeiro p-calendar do dialog)
        _preencher_calendar(page, "p-dialog p-calendar:first-of-type input", data_fmt)
        page.wait_for_timeout(500)

        # Preenche Data Fim (último p-calendar do dialog)
        _preencher_calendar(page, "p-dialog p-calendar:last-of-type input", data_fmt)
        page.wait_for_timeout(500)

        # Clica em Aplicar (último botão do footer do dialog)
        _clicar_aplicar(page)
        _wait_angular(page)

    except Exception:
        pass


def _preencher_calendar(page: Page, seletor: str, data_fmt: str) -> None:
    """Preenche um campo de data PrimeNG com a data fornecida."""
    try:
        inp = page.query_selector(seletor)
        if not inp:
            # Fallback — qualquer input de data visível
            inputs = page.query_selector_all("p-dialog input, .p-dialog-content input")
            inp = next((i for i in inputs if i.is_visible()), None)
        if inp:
            inp.triple_click()
            inp.fill(data_fmt)
            page.keyboard.press("Tab")
    except Exception:
        pass


def _clicar_aplicar(page: Page) -> None:
    """Clica no botão Aplicar dentro do modal de filtros."""
    seletores = [
        ".p-dialog-footer button:last-of-type",
        "p-dialog button:has-text('Aplicar')",
        ".p-dialog button:has-text('Aplicar')",
        "button .p-button-label:has-text('Aplicar')",
    ]
    for sel in seletores:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.click()
                return
        except Exception:
            continue

    # Fallback via JavaScript
    page.evaluate("""() => {
        const btns = document.querySelectorAll('.p-dialog-footer button, p-dialog button');
        for (const b of btns) {
            if (b.textContent.trim() === 'Aplicar') { b.click(); return; }
        }
    }""")


# ---------------------------------------------------------------------------
# ETAPA 3 – Listar edições na página
# ---------------------------------------------------------------------------

def _listar_edicoes(page: Page) -> list[dict]:
    """Retorna metadados das edições listadas na página de resultados."""
    try:
        page.wait_for_selector(
            "button:has-text('Abrir'), .p-dataview-content",
            timeout=WAIT_LG,
        )
    except PlaywrightTimeoutError:
        return []

    edicoes = page.evaluate("""() => {
        const results = [];
        // Tenta capturar cards de edição
        const cards = document.querySelectorAll('.p-dataview-content .col-12, .card.card-content');
        cards.forEach((card, i) => {
            const texto = card.innerText.trim();
            const abrir = card.querySelector('button');
            results.push({
                index: i,
                texto: texto,
                temBotao: !!abrir
            });
        });
        return results;
    }""")

    return [e for e in edicoes if e.get("temBotao")]


# ---------------------------------------------------------------------------
# ETAPA 4 – Processar uma edição
# ---------------------------------------------------------------------------

def _processar_edicao(
    page: Page,
    idx: int,
    edicao_info: dict,
    palavras_chave: list[str],
) -> list[dict]:
    """Abre uma edição, navega no visualizador e extrai publicações."""
    resultados: list[dict] = []

    try:
        # Relocaliza e clica no botão "Abrir" do card correto
        botoes_abrir = page.query_selector_all("button:has-text('Abrir')")
        if idx >= len(botoes_abrir):
            return resultados

        botoes_abrir[idx].click()
        _wait_angular(page)

        # Modal de escolha de formato — clica em "EXTRATO DE PUBLICAÇÃO CERTIFICADA"
        _selecionar_extrato(page)
        _wait_angular(page)

        # Dentro do visualizador: itera pelas categorias-alvo
        for categoria in CATEGORIAS_ALVO:
            novos = _extrair_por_categoria(page, categoria, palavras_chave)
            resultados.extend(novos)

        # Retorna à lista de edições
        _voltar_lista(page)
        _wait_angular(page)

    except Exception:
        try:
            _voltar_lista(page)
        except Exception:
            pass

    return resultados


def _selecionar_extrato(page: Page) -> None:
    """Seleciona o formato 'EXTRATO DE PUBLICAÇÃO CERTIFICADA' no modal."""
    seletores = [
        "button.btn-extrato",
        "button:has-text('EXTRATO DE PUBLICAÇÃO CERTIFICADA')",
        "button:has-text('Extrato')",
        ".btn-extrato",
    ]
    for sel in seletores:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.click()
                return
        except Exception:
            continue


def _voltar_lista(page: Page) -> None:
    """Retorna à lista de edições."""
    seletores = [
        "button[label='Voltar']",
        "button:has-text('Voltar')",
        "a:has-text('Voltar')",
    ]
    for sel in seletores:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.click()
                return
        except Exception:
            continue

    # Fallback: navega para a URL de busca
    page.go_back()


# ---------------------------------------------------------------------------
# ETAPA 4c – Extração por categoria dentro do visualizador
# ---------------------------------------------------------------------------

def _extrair_por_categoria(
    page: Page,
    texto_categoria: str,
    palavras_chave: list[str],
) -> list[dict]:
    """Seleciona uma categoria no visualizador e extrai os atos filtrados."""
    resultados: list[dict] = []

    try:
        # Seleciona a categoria
        if not _primeng_select(page, "Selecione uma categoria", texto_categoria):
            return resultados
        _wait_angular(page)

        # Lista assuntos de PORTARIA disponíveis
        assuntos = _primeng_list_options(page, "Selecione um assunto")
        assuntos_portaria = [a for a in assuntos if "PORTARIA" in a.upper()]

        for assunto in assuntos_portaria:
            _primeng_select(page, "Selecione um assunto", assunto)
            _wait_angular(page)

            # Extrai os atos da lista de resultados atual
            atos = _extrair_atos_lista(page, texto_categoria, assunto, palavras_chave)
            resultados.extend(atos)

            # Limpa o assunto (volta ao placeholder)
            _primeng_clear(page, "Selecione um assunto")
            _wait_angular(page)

        # Limpa a categoria
        _primeng_clear(page, "Selecione uma categoria")
        _wait_angular(page)

    except Exception:
        pass

    return resultados


def _extrair_atos_lista(
    page: Page,
    categoria: str,
    assunto: str,
    palavras_chave: list[str],
) -> list[dict]:
    """Extrai atos visíveis na lista, abre cada detalhe e filtra por palavras-chave."""
    resultados: list[dict] = []

    try:
        # Aguarda resultado ou mensagem de vazio
        try:
            page.wait_for_selector("section, .p-dataview-emptymessage", timeout=WAIT_MD)
        except PlaywrightTimeoutError:
            return resultados

        # Conta quantos cards/atos existem
        n_sections = page.evaluate(
            "() => document.querySelectorAll('section').length"
        )

        for i in range(n_sections):
            resultado = _processar_ato(page, i, categoria, assunto, palavras_chave)
            if resultado:
                resultados.append(resultado)

    except Exception:
        pass

    return resultados


def _processar_ato(
    page: Page,
    idx: int,
    categoria: str,
    assunto: str,
    palavras_chave: list[str],
) -> dict | None:
    """Abre o detalhe de um ato, extrai o texto e verifica palavras-chave."""
    try:
        sections = page.query_selector_all("section")
        if idx >= len(sections):
            return None

        section = sections[idx]

        # Extrai metadados do card
        metadados = section.evaluate("el => el.innerText").strip()
        titulo = _extrair_titulo_do_card(metadados, assunto)

        # Clica em "Saiba mais" para o detalhe
        link_detalhe = section.query_selector("a.mr-2, a:has-text('Saiba mais'), a:has-text('Ver')")
        if not link_detalhe:
            # Sem link de detalhe — usa apenas os metadados
            texto_completo = metadados
        else:
            link_detalhe.click()
            _wait_angular(page)

            texto_completo = _extrair_texto_detalhe(page)

            # Volta para a lista
            _voltar_lista(page)
            _wait_angular(page)

        # Filtra por palavras-chave
        if palavras_chave:
            padrao = "|".join(re.escape(p.lower()) for p in palavras_chave if p.strip())
            if padrao and not re.search(padrao, texto_completo.lower()):
                return None

        return {
            "origem":    "DOE-SC",
            "hierarquia": f"DOE-SC › {categoria} › {assunto}",
            "titulo":    titulo,
            "link":      "",
            "descricao": texto_completo[:1500],
        }

    except Exception:
        try:
            _voltar_lista(page)
        except Exception:
            pass
        return None


def _extrair_titulo_do_card(metadados: str, fallback: str) -> str:
    """Tenta extrair título do ato dos metadados do card."""
    match = re.search(r"(PORTARIA[^\n]+)", metadados, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    linhas = [l.strip() for l in metadados.splitlines() if l.strip()]
    return linhas[0] if linhas else fallback


def _extrair_texto_detalhe(page: Page) -> str:
    """Extrai o texto integral da página de detalhe do ato."""
    seletores = [
        "p.line-height-3.text-justify.text-lg.text-700.mb-4.white-space-pre-wrap",
        "p.white-space-pre-wrap",
        "p.text-justify.text-lg",
        "p.text-justify",
        ".conteudo-publicacao",
        "article",
    ]
    for sel in seletores:
        try:
            el = page.query_selector(sel)
            if el:
                texto = el.inner_text().strip()
                if texto:
                    return texto
        except Exception:
            continue

    # Fallback: todos os parágrafos com mais de 80 caracteres
    return page.evaluate("""() => {
        return Array.from(document.querySelectorAll('p'))
            .map(p => p.innerText.trim())
            .filter(t => t.length > 80)
            .join('\\n\\n');
    }""") or ""


# ---------------------------------------------------------------------------
# Helpers PrimeNG
# ---------------------------------------------------------------------------

def _wait_angular(page: Page) -> None:
    """Aguarda estabilização do Angular (networkidle + buffer)."""
    try:
        page.wait_for_load_state("networkidle", timeout=WAIT_MD)
    except PlaywrightTimeoutError:
        pass
    page.wait_for_timeout(800)


def _primeng_select(page: Page, placeholder: str, texto_alvo: str) -> bool:
    """Abre um p-dropdown e seleciona a opção que contém o texto-alvo."""
    try:
        # Clica no dropdown pelo span com o placeholder
        clicado = page.evaluate(
            """([ph]) => {
                const spans = document.querySelectorAll('.p-dropdown-label, .p-placeholder');
                for (const s of spans) {
                    if (s.textContent.trim().toLowerCase().includes(ph.toLowerCase())) {
                        s.closest('.p-dropdown, p-dropdown').click();
                        return true;
                    }
                }
                return false;
            }""",
            [placeholder],
        )

        if not clicado:
            page.click(f"span:has-text('{placeholder}')")

        page.wait_for_timeout(800)

        # Aguarda o painel abrir
        try:
            page.wait_for_selector(".p-dropdown-item, .p-listbox-item", timeout=WAIT_SM)
        except PlaywrightTimeoutError:
            return False

        # Clica na opção correta
        encontrado = page.evaluate(
            """([texto]) => {
                const items = document.querySelectorAll('.p-dropdown-item, .p-listbox-item');
                for (const item of items) {
                    if (item.textContent.trim().toLowerCase().includes(texto.toLowerCase())) {
                        item.click();
                        return true;
                    }
                }
                return false;
            }""",
            [texto_alvo],
        )
        return bool(encontrado)

    except Exception:
        return False


def _primeng_list_options(page: Page, placeholder: str) -> list[str]:
    """Abre um p-dropdown e retorna todas as opções disponíveis."""
    opcoes: list[str] = []
    try:
        page.evaluate(
            """([ph]) => {
                const spans = document.querySelectorAll('.p-dropdown-label, .p-placeholder');
                for (const s of spans) {
                    if (s.textContent.trim().toLowerCase().includes(ph.toLowerCase())) {
                        s.closest('.p-dropdown, p-dropdown').click();
                        return;
                    }
                }
            }""",
            [placeholder],
        )
        page.wait_for_timeout(800)
        page.wait_for_selector(".p-dropdown-item", timeout=WAIT_SM)

        opcoes = page.evaluate("""() =>
            Array.from(document.querySelectorAll('.p-dropdown-item'))
                .map(i => i.textContent.trim())
                .filter(t => t.length > 0)
        """)
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)

    except Exception:
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass

    return opcoes


def _primeng_clear(page: Page, placeholder: str) -> None:
    """Limpa a seleção de um p-dropdown tentando clicar no ícone de clear."""
    try:
        limpo = page.evaluate(
            """([ph]) => {
                // Tenta pelo ícone de limpar
                const clears = document.querySelectorAll('.p-dropdown-clear-icon');
                for (const c of clears) {
                    const dd = c.closest('.p-dropdown, p-dropdown');
                    if (dd) {
                        const label = dd.querySelector('.p-dropdown-label');
                        if (label && !label.classList.contains('p-placeholder')) {
                            c.click();
                            return true;
                        }
                    }
                }
                return false;
            }""",
            [placeholder],
        )

        if not limpo:
            # Fallback: seleciona o primeiro item (placeholder)
            _primeng_select(page, placeholder, "")

    except Exception:
        pass
