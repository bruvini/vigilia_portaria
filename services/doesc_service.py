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
            # ── 1. Clique em 'Buscar Edições' ────────────────────────────
            page.goto(URL_BASE, wait_until="domcontentloaded")
            _wait_angular(page)

            page.wait_for_selector("a:has-text('Buscar Edições')")
            page.click("a:has-text('Buscar Edições')")
            _wait_angular(page)

            # ── 2. Clique no botão 'Filtros' ──────────────────────────────
            page.wait_for_selector("button:has-text('Filtros'), button:has(.pi-filter)")
            btn_filtro = page.locator("button:has-text('Filtros'), button:has(.pi-filter)").first
            btn_filtro.click()

            # ── 3. Modal 1 (Filtro de Data) ────────────────────────────────
            page.wait_for_selector("p-dialog:has(p-calendar) .p-dialog", state="visible")

            _preencher_calendar(page, "p-dialog:has(p-calendar) .p-dialog p-calendar:first-of-type input", data_fmt)
            page.wait_for_timeout(500)

            _preencher_calendar(page, "p-dialog:has(p-calendar) .p-dialog p-calendar:last-of-type input", data_fmt)
            page.wait_for_timeout(500)

            btn_aplicar = page.locator("p-dialog:has(p-calendar) .p-dialog button:has-text('Aplicar')")
            btn_aplicar.click()

            # Aguarde o modal sumir e a lista carregar
            page.wait_for_selector("p-dialog:has(p-calendar) .p-dialog", state="hidden")
            page.wait_for_selector("button:has-text('Abrir')", state="visible")
            _wait_angular(page)

            # ── 4. Lista de Edições ───────────────────────────────────────
            # Clique no botão 'Abrir' do primeiro resultado da listagem.
            first_abrir = page.locator("button:has-text('Abrir')").first
            first_abrir.click()
            _wait_angular(page)

            # ── 5. Modal 2 (Formato da Edição) ────────────────────────────
            # Um novo modal aparecerá perguntando o formato.
            # Clique EXATAMENTE no botão com texto 'EXTRATO DE PUBLICAÇÃO CERTIFICADA'.
            page.wait_for_selector("button:has-text('EXTRATO DE PUBLICAÇÃO CERTIFICADA')", state="visible")
            page.click("button:has-text('EXTRATO DE PUBLICAÇÃO CERTIFICADA')")

            # Aguarde a nova página carregar (verificando a visibilidade da categoria)
            page.wait_for_selector(
                "span:has-text('Selecione uma categoria'), p-dropdown:has-text('Selecione uma categoria'), .p-placeholder:has-text('Selecione uma categoria')",
                state="visible"
            )
            _wait_angular(page)

            # ── 6 e 7. Filtros de Categoria e Assunto / Iteração ───────────
            for categoria in CATEGORIAS_ALVO:
                novos = _extrair_por_categoria(page, categoria, palavras_chave)
                todos.extend(novos)

        except Exception as e:
            # Silencia ou loga internamente para depuração se necessário
            import traceback
            traceback.print_exc()
        finally:
            browser.close()

    if not todos:
        return pd.DataFrame(columns=COLUNAS)

    return pd.DataFrame(todos, columns=COLUNAS)


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
        assuntos_portaria = [a for a in assuntos if a.strip().upper().startswith("PORTARIA")]

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
            page.wait_for_selector("section.grid.border-bottom-1, .p-dataview-emptymessage", timeout=WAIT_MD)
        except PlaywrightTimeoutError:
            return resultados

        # Conta quantos cards/atos existem (apenas visíveis)
        sections = page.query_selector_all("section.grid.border-bottom-1")
        visible_sections = [s for s in sections if s.is_visible()]
        n_sections = len(visible_sections)

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
        sections = page.query_selector_all("section.grid.border-bottom-1")
        visible_sections = [s for s in sections if s.is_visible()]
        if idx >= len(visible_sections):
            return None

        section = visible_sections[idx]

        # Extrai metadados do card
        metadados = section.evaluate("el => el.innerText").strip()
        titulo = _extrair_titulo_do_card(metadados, assunto)

        # Clica em "Saiba mais" para o detalhe
        link_detalhe = section.query_selector("a:has-text('Saiba mais')")
        if not link_detalhe:
            link_detalhe = section.query_selector("a.mr-2, a:has-text('Ver')")

        if not link_detalhe:
            # Sem link de detalhe — usa apenas os metadados do card
            texto_completo = metadados
        else:
            link_detalhe.click()
            _wait_angular(page)

            # Aguarde a tela de detalhe carregar
            page.wait_for_selector("button[label='Voltar']", timeout=WAIT_MD)

            texto_completo = _extrair_texto_detalhe(page)

            # Clique no botão 'Voltar' (<button ... label="Voltar">)
            page.click("button[label='Voltar']")
            _wait_angular(page)

            # Restaura os filtros se foram resetados ao voltar
            _restaurar_filtros(page, categoria, assunto)

        # Filtra por palavras-chave
        if palavras_chave:
            padrao = "|".join(re.escape(p.lower()) for p in palavras_chave if p.strip())
            if padrao and not re.search(padrao, texto_completo.lower()):
                return None

        # Filtro estrito do DOE-SC: manter apenas se contiver a string exata "Município: Joinville" (com variações)
        if not re.search(r"(?i)munic[íi]pio:\s*joinville", texto_completo):
            return None

        return {
            "origem":    "DOE-SC",
            "hierarquia": f"DOE-SC › {categoria} › {assunto}",
            "titulo":    titulo,
            "link":      "",
            "descricao": texto_completo,
        }

    except Exception:
        try:
            # Se deu erro e estamos na tela de detalhe, tenta voltar
            btn_voltar = page.query_selector("button[label='Voltar']")
            if btn_voltar and btn_voltar.is_visible():
                btn_voltar.click()
                _wait_angular(page)
            _restaurar_filtros(page, categoria, assunto)
        except Exception:
            pass
        return None


def _restaurar_filtros(page: Page, categoria: str, assunto: str) -> None:
    """Garante que a categoria e o assunto continuem selecionados após voltar do detalhe."""
    try:
        selector_cat = 'p-dropdown[placeholder*="Selecione uma categoria" i], p-dropdown:has(span:has-text("Selecione uma categoria"))'
        cat_dropdown = page.locator(selector_cat).first
        if cat_dropdown.is_visible():
            label = cat_dropdown.inner_text().strip()
            if "Selecione uma categoria" in label:
                _primeng_select(page, "Selecione uma categoria", categoria)
                _wait_angular(page)

        selector_ass = 'p-dropdown[placeholder*="Selecione um assunto" i], p-dropdown:has(span:has-text("Selecione um assunto"))'
        sub_dropdown = page.locator(selector_ass).first
        if sub_dropdown.is_visible():
            label = sub_dropdown.inner_text().strip()
            if "Selecione um assunto" in label:
                _primeng_select(page, "Selecione um assunto", assunto)
                _wait_angular(page)
    except Exception:
        pass


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
        dropdown = page.locator(f'p-dropdown[placeholder*="{placeholder}" i], p-dropdown:has(span:has-text("{placeholder}"))').first
        if not dropdown.is_visible():
            return False
        dropdown.click()
        page.wait_for_timeout(500)
        
        # Localiza o item visível na lista
        option = page.locator(".p-dropdown-panel:visible .p-dropdown-item, .p-listbox-panel:visible .p-listbox-item").filter(has_text=texto_alvo).first
        if option.is_visible():
            option.click()
            page.wait_for_timeout(500)
            return True
        return False
    except Exception:
        return False


def _primeng_list_options(page: Page, placeholder: str) -> list[str]:
    """Abre um p-dropdown e retorna todas as opções disponíveis."""
    opcoes: list[str] = []
    try:
        dropdown = page.locator(f'p-dropdown[placeholder*="{placeholder}" i], p-dropdown:has(span:has-text("{placeholder}"))').first
        if not dropdown.is_visible():
            return opcoes
        dropdown.click()
        page.wait_for_timeout(500)
        
        # Localiza os itens visíveis no painel
        items = page.locator(".p-dropdown-panel:visible .p-dropdown-item, .p-listbox-panel:visible .p-listbox-item")
        opcoes = [text.strip() for text in items.all_inner_texts() if text.strip()]
        
        # Fecha o dropdown
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)
    except Exception:
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass
    return opcoes


def _primeng_clear(page: Page, placeholder: str) -> None:
    """Limpa a seleção de um p-dropdown tentando clicar no ícone de clear."""
    try:
        dropdown = page.locator(f'p-dropdown[placeholder*="{placeholder}" i], p-dropdown:has(span:has-text("{placeholder}"))').first
        clear_btn = dropdown.locator(".p-dropdown-clear-icon")
        if clear_btn.is_visible():
            clear_btn.click()
            page.wait_for_timeout(500)
    except Exception:
        pass
