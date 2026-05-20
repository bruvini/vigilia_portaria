"""
Serviço de raspagem de dados do Diário Oficial do Estado de Santa Catarina (DOE-SC).

Portal: https://portal.doe.sea.sc.gov.br/v2.43.01/#/portal
Framework: Angular + PrimeNG

Arquitetura do pipeline:
  1. Playwright navega até o visualizador de atos (Extrato de Publicação Certificada)
  2. O serviço aplica filtros de Categoria e Assunto nos dropdowns PrimeNG
  3. Para cada ato encontrado, extrai o texto integral da tela de detalhe
  4. O texto é normalizado (espaços, quebras, etc.)
  5. Busca textual robusta por palavras-chave (case-insensitive, sem regex estrita)
  6. Filtragem permanente: só retorna atos que mencionam "Joinville" em qualquer forma
  7. Retorna DataFrame estruturado com contexto de cada ocorrência

FILTRO PERMANENTE (hardcoded):
  Apenas publicações cujo texto contenha a string "joinville" (qualquer capitalização)
  são retornadas. Este serviço é exclusivo para monitorar o município de Joinville.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from datetime import date
from typing import Optional

import pandas as pd
from playwright.sync_api import (
    Page,
    sync_playwright,
    TimeoutError as PlaywrightTimeoutError,
)


# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="[DOE-SC] %(levelname)s: %(message)s",
)


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

URL_BASE  = "https://portal.doe.sea.sc.gov.br/v2.43.01/#/portal"
TIMEOUT   = 30_000
WAIT_SM   = 2_000
WAIT_MD   = 6_000
WAIT_LG   = 12_000

# Categorias que serão pesquisadas (textos parciais para match flexível no dropdown)
CATEGORIAS_ALVO = [
    "Saúde",      # captura "Secretaria de Estado de Saúde" e "Secretarias de Estado / Saúde"
    "Joinville",  # captura "Prefeituras Municipais / Joinville"
]

# Chave obrigatória de Joinville — sem isso o ato é descartado
KEYWORD_JOINVILLE = "joinville"

COLUNAS = ["origem", "hierarquia", "titulo", "link", "link_certificado", "descricao", "tipo", "orgao", "pagina", "palavra_encontrada"]


# ---------------------------------------------------------------------------
# Função principal pública
# ---------------------------------------------------------------------------

def buscar_doesc(
    data_publicacao: date,
    palavras_chave: list[str],
) -> pd.DataFrame:
    """Realiza a busca no DOE-SC e retorna DataFrame filtrado.

    Args:
        data_publicacao: Data da edição a consultar.
        palavras_chave:  Lista de termos para filtrar os resultados.
                         Se vazia, retorna todos os atos de Joinville encontrados.

    Returns:
        DataFrame com colunas: origem, hierarquia, titulo, link, descricao,
        tipo, orgao, pagina, palavra_encontrada.
    """
    data_fmt = data_publicacao.strftime("%d/%m/%Y")
    logger.info(f"Iniciando busca DOE-SC para data {data_fmt}")
    logger.info(f"Palavras-chave: {palavras_chave or '(nenhuma — retorna tudo de Joinville)'}")

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
            # ── 1. Acessa o portal e navega até Buscar Edições ────────────────
            logger.info("Acessando portal DOE-SC...")
            page.goto(URL_BASE, wait_until="domcontentloaded")
            _wait_angular(page)

            page.wait_for_selector("a:has-text('Buscar Edições')")
            page.click("a:has-text('Buscar Edições')")
            _wait_angular(page)
            logger.info("Navegou para 'Buscar Edições'")

            # ── 2. Abre modal de Filtros e preenche datas ─────────────────────
            page.wait_for_selector("button:has-text('Filtros'), button:has(.pi-filter)")
            btn_filtro = page.locator("button:has-text('Filtros'), button:has(.pi-filter)").first
            btn_filtro.click()
            page.wait_for_selector("p-dialog:has(p-calendar) .p-dialog", state="visible")

            _preencher_calendar(page, "p-dialog:has(p-calendar) .p-dialog p-calendar:first-of-type input", data_fmt)
            page.wait_for_timeout(500)
            _preencher_calendar(page, "p-dialog:has(p-calendar) .p-dialog p-calendar:last-of-type input", data_fmt)
            page.wait_for_timeout(500)

            btn_aplicar = page.locator("p-dialog:has(p-calendar) .p-dialog button:has-text('Aplicar')")
            btn_aplicar.click()
            page.wait_for_selector("p-dialog:has(p-calendar) .p-dialog", state="hidden")

            # ── 3. Verifica se há edições na data ─────────────────────────────
            try:
                page.wait_for_selector("button:has-text('Abrir')", state="visible", timeout=WAIT_MD)
            except PlaywrightTimeoutError:
                logger.warning(f"Nenhuma edição encontrada para {data_fmt}")
                browser.close()
                return pd.DataFrame(columns=COLUNAS)

            _wait_angular(page)

            # Conta edições disponíveis
            n_edicoes = page.locator("button:has-text('Abrir')").count()
            logger.info(f"Edições encontradas para {data_fmt}: {n_edicoes}")

            # ── 4. Processa apenas a primeira edição ──────────────────────────
            first_abrir = page.locator("button:has-text('Abrir')").first
            first_abrir.click()
            _wait_angular(page)

            # ── 5. Modal de formato — seleciona Extrato de Publicação ─────────
            page.wait_for_selector("button:has-text('EXTRATO DE PUBLICAÇÃO CERTIFICADA')", state="visible")
            page.click("button:has-text('EXTRATO DE PUBLICAÇÃO CERTIFICADA')")

            # Aguarda o visualizador carregar com os dropdowns de categoria
            page.wait_for_selector(
                "span:has-text('Selecione uma categoria'), "
                "p-dropdown:has-text('Selecione uma categoria'), "
                ".p-placeholder:has-text('Selecione uma categoria')",
                state="visible",
                timeout=WAIT_LG,
            )
            _wait_angular(page)
            logger.info("Visualizador de atos aberto")

            # ── 6. Lista todas as categorias disponíveis (diagnóstico) ─────────
            categorias_disponiveis = _primeng_list_options(page, "Selecione uma categoria")
            logger.info(f"Categorias disponíveis no visualizador: {categorias_disponiveis}")

            # ── 7. Itera pelas categorias-alvo ────────────────────────────────
            for categoria in CATEGORIAS_ALVO:
                cat_encontrada = next(
                    (c for c in categorias_disponiveis if categoria.lower() in c.lower()),
                    None,
                )
                if not cat_encontrada:
                    logger.info(f"Categoria '{categoria}' não encontrada nas opções disponíveis. Pulando.")
                    continue

                logger.info(f"Processando categoria: '{cat_encontrada}'")
                novos = _extrair_por_categoria(page, cat_encontrada, palavras_chave)
                todos.extend(novos)
                logger.info(f"Atos retornados de '{cat_encontrada}': {len(novos)}")

        except PlaywrightTimeoutError as exc:
            logger.error(f"Timeout durante navegação: {exc}")
        except Exception as exc:
            import traceback
            logger.error(f"Erro inesperado: {exc}")
            traceback.print_exc()
        finally:
            browser.close()

    if not todos:
        logger.info("Nenhum ato encontrado após todas as tentativas.")
        return pd.DataFrame(columns=COLUNAS)

    df = pd.DataFrame(todos)
    # Garante que as colunas existem
    for col in COLUNAS:
        if col not in df.columns:
            df[col] = ""
    df = df[COLUNAS]
    logger.info(f"Total de atos retornados: {len(df)}")
    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Preenchimento de data no PrimeNG Calendar
# ---------------------------------------------------------------------------

def _preencher_calendar(page: Page, seletor: str, data_fmt: str) -> None:
    """Preenche um campo de data PrimeNG com a data fornecida."""
    try:
        inp = page.query_selector(seletor)
        if not inp:
            inputs = page.query_selector_all("p-dialog input, .p-dialog-content input")
            inp = next((i for i in inputs if i.is_visible()), None)
        if inp:
            inp.triple_click()
            inp.fill(data_fmt)
            page.keyboard.press("Tab")
            logger.debug(f"Data preenchida: {data_fmt} em '{seletor}'")
    except Exception as exc:
        logger.warning(f"Falha ao preencher data em '{seletor}': {exc}")


# ---------------------------------------------------------------------------
# Extração por categoria
# ---------------------------------------------------------------------------

def _extrair_por_categoria(
    page: Page,
    texto_categoria: str,
    palavras_chave: list[str],
) -> list[dict]:
    """Seleciona uma categoria no visualizador e extrai os atos filtrados."""
    resultados: list[dict] = []

    try:
        if not _primeng_select(page, "Selecione uma categoria", texto_categoria):
            logger.warning(f"Não foi possível selecionar a categoria '{texto_categoria}'")
            return resultados
        _wait_angular(page)

        # Lista assuntos disponíveis
        assuntos = _primeng_list_options(page, "Selecione um assunto")
        logger.info(f"Assuntos disponíveis em '{texto_categoria}': {len(assuntos)} — {assuntos[:10]}")

        assuntos_portaria = [a for a in assuntos if a.strip().upper().startswith("PORTARIA")]
        logger.info(f"Assuntos de PORTARIA: {len(assuntos_portaria)}")

        if not assuntos_portaria:
            logger.info(f"Nenhum assunto de PORTARIA em '{texto_categoria}'")
            _primeng_clear(page, "Selecione uma categoria")
            _wait_angular(page)
            return resultados

        for assunto in assuntos_portaria:
            logger.info(f"Processando assunto: '{assunto}'")
            _primeng_select(page, "Selecione um assunto", assunto)
            _wait_angular(page)

            atos = _extrair_atos_lista(page, texto_categoria, assunto, palavras_chave)
            resultados.extend(atos)
            logger.info(f"Atos encontrados em '{assunto}': {len(atos)}")

            _primeng_clear(page, "Selecione um assunto")
            _wait_angular(page)

        _primeng_clear(page, "Selecione uma categoria")
        _wait_angular(page)

    except Exception as exc:
        logger.error(f"Erro ao processar categoria '{texto_categoria}': {exc}")

    return resultados


# ---------------------------------------------------------------------------
# Extração da lista de atos
# ---------------------------------------------------------------------------

def _extrair_atos_lista(
    page: Page,
    categoria: str,
    assunto: str,
    palavras_chave: list[str],
) -> list[dict]:
    """Extrai atos visíveis na lista, abre cada detalhe e filtra."""
    resultados: list[dict] = []

    try:
        try:
            page.wait_for_selector("section.grid.border-bottom-1, .p-dataview-emptymessage", timeout=WAIT_MD)
        except PlaywrightTimeoutError:
            logger.info(f"Timeout esperando atos para '{assunto}' — pode estar vazio")
            return resultados

        # Verifica se está vazia
        vazia = page.query_selector(".p-dataview-emptymessage")
        if vazia and vazia.is_visible():
            logger.info(f"Lista vazia para '{assunto}'")
            return resultados

        sections = page.query_selector_all("section.grid.border-bottom-1")
        visible_sections = [s for s in sections if s.is_visible()]
        n = len(visible_sections)
        logger.info(f"Atos visíveis na lista para '{assunto}': {n}")

        for i in range(n):
            resultado = _processar_ato(page, i, categoria, assunto, palavras_chave)
            if resultado:
                resultados.append(resultado)

    except Exception as exc:
        logger.error(f"Erro na extração da lista: {exc}")

    return resultados


# ---------------------------------------------------------------------------
# Processamento individual de um ato
# ---------------------------------------------------------------------------

def _processar_ato(
    page: Page,
    idx: int,
    categoria: str,
    assunto: str,
    palavras_chave: list[str],
) -> Optional[dict]:
    """Abre o detalhe de um ato, extrai texto normalizado e verifica critérios."""
    try:
        sections = page.query_selector_all("section.grid.border-bottom-1")
        visible_sections = [s for s in sections if s.is_visible()]
        if idx >= len(visible_sections):
            return None

        section = visible_sections[idx]
        metadados = section.evaluate("el => el.innerText").strip()
        titulo = _extrair_titulo_do_card(metadados, assunto)

        link_detalhe = (
            section.query_selector("a:has-text('Saiba mais')") or
            section.query_selector("a.mr-2, a:has-text('Ver')")
        )

        link_certificado = ""

        if not link_detalhe:
            texto_completo = metadados
            logger.debug(f"Ato {idx}: sem link de detalhe, usando metadados do card")
        else:
            link_detalhe.click()
            _wait_angular(page)
            page.wait_for_selector("button[label='Voltar']", timeout=WAIT_MD)

            texto_completo = _extrair_texto_detalhe(page)
            logger.debug(f"Ato {idx}: texto extraído — {len(texto_completo)} chars")

            # ── Captura link do botão 'Publicação Certificada' ────────────────
            link_certificado = _capturar_link_certificado(page)
            if link_certificado:
                logger.info(f"Ato {idx}: link certificado capturado — {link_certificado[:80]}")

            page.click("button[label='Voltar']")
            _wait_angular(page)
            _restaurar_filtros(page, categoria, assunto)

        # ── Normaliza o texto ────────────────────────────────────────────────
        texto_normalizado = _normalizar_texto(texto_completo)

        # ── Filtro obrigatório: deve mencionar Joinville ─────────────────────
        if KEYWORD_JOINVILLE not in texto_normalizado.lower():
            logger.debug(f"Ato {idx}: descartado — sem menção a 'joinville'")
            return None

        # ── Filtro por palavras-chave do usuário (case-insensitive, substring) ──
        palavras_limpas = [p.strip().lower() for p in palavras_chave if p.strip()]
        palavra_encontrada = ""
        if palavras_limpas:
            texto_lower = texto_normalizado.lower()
            match_encontrado = False
            for palavra in palavras_limpas:
                if palavra in texto_lower:
                    match_encontrado = True
                    palavra_encontrada = palavra
                    break
            if not match_encontrado:
                logger.debug(f"Ato {idx}: descartado — palavras-chave não encontradas")
                return None
        else:
            # Sem filtro de palavras-chave: retorna todos de Joinville
            palavra_encontrada = KEYWORD_JOINVILLE

        # ── Extrai informações estruturadas ───────────────────────────────────
        tipo = _identificar_tipo(titulo)
        orgao = _identificar_orgao(texto_normalizado)
        trecho = _extrair_trecho_contexto(texto_normalizado, palavra_encontrada or KEYWORD_JOINVILLE)

        logger.info(f"Ato {idx}: INCLUÍDO — '{titulo[:60]}...' | tipo={tipo} | orgao={orgao[:40]}")

        return {
            "origem":            "DOE-SC",
            "hierarquia":        f"DOE-SC › {categoria} › {assunto}",
            "titulo":            titulo,
            "link":              "",
            "link_certificado":  link_certificado,
            "descricao":         trecho,
            "tipo":              tipo,
            "orgao":             orgao,
            "pagina":            "",
            "palavra_encontrada": palavra_encontrada,
        }

    except Exception as exc:
        logger.error(f"Erro ao processar ato {idx}: {exc}")
        try:
            btn_voltar = page.query_selector("button[label='Voltar']")
            if btn_voltar and btn_voltar.is_visible():
                btn_voltar.click()
                _wait_angular(page)
            _restaurar_filtros(page, categoria, assunto)
        except Exception:
            pass
        return None


# ---------------------------------------------------------------------------
# Normalização de texto
# ---------------------------------------------------------------------------

# Padrões de linhas que devem ser removidas (tabelas financeiras, códigos, etc.)
_RE_LINHAS_LIXO = re.compile(
    r"""(
        ^\s*[0-9]{5,}\s*$                # linhas só com número ≥5 dígitos (códigos)
      | ^\s*[\d.,]+\s*$                  # linhas só com valores numéricos/decimais
      | ^\s*\d+[.,]\d+\s*[.,]\d+\s*$   # padrões financeiros: 1.234,56
      | ^\s*R\$\s*[\d.,]+               # valores em reais
      | ^\s*[A-Z0-9]{2,}\s{1,3}[A-Z0-9]{2,}\s{1,3}[\d.,]+  # tabela codigos
      | ^\s*Total.*?[\d.,]+\s*$          # linhas de total
      | ^\s*Subtotal.*?[\d.,]+\s*$
      | ^\s*FONTE\s+DE\s+RECURSOS       # cabeçalho de tabela financeira
      | ^\s*ELEMENTO\s+DE\s+DESPESA
      | ^\s*NATUREZA\s+DE\s+DESPESA
      | ^\s*CÓD\.?\s+SIAF               # código SIAF
      | ^\s*[0-9]{4}\s+[0-9]{4}         # linhas de tabela com 2+ grupos de 4+ dígitos
    )""",
    re.VERBOSE | re.IGNORECASE | re.MULTILINE,
)

_RE_BLOCOS_TABELA = re.compile(
    r"([0-9]{1,4}[\s\t]+){4,}",  # 4+ números separados por espaço (linha de tabela)
    re.MULTILINE,
)


def _normalizar_texto(texto: str) -> str:
    """
    Normaliza e limpa o texto extraído do DOE-SC:
    - Remove múltiplos espaços e tabulações
    - Corrige quebras de linha excessivas
    - Une palavras quebradas por hífen no final da linha
    - Remove caracteres de controle inválidos
    - Remove linhas de tabelas financeiras e códigos SIAF/orçamentários
    - Preserva acentuação (não remove diacríticos)
    """
    if not texto:
        return ""

    # Une palavras quebradas com hífen no final da linha (ex: "Secre-\ntaria" → "Secretaria")
    texto = re.sub(r"-\s*\n\s*", "", texto)

    # Remove caracteres de controle (exceto \n e \t)
    texto = "".join(c for c in texto if unicodedata.category(c)[0] != "C" or c in "\n\t")

    # Substitui tabulações por espaço
    texto = texto.replace("\t", " ")

    # Remove blocos de tabela (4+ números separados por espaços em sequência)
    texto = _RE_BLOCOS_TABELA.sub(" ", texto)

    # Remove linhas que são apenas lixo financeiro/tabular
    linhas_filtradas = []
    for linha in texto.splitlines():
        linha_s = linha.strip()
        if linha_s and _RE_LINHAS_LIXO.search(linha_s):
            continue  # descarta linha de lixo
        linhas_filtradas.append(linha_s)

    texto = "\n".join(linhas_filtradas)

    # Substitui múltiplas quebras de linha por no máximo duas
    texto = re.sub(r"\n{3,}", "\n\n", texto)

    # Remove espaços duplicados dentro de uma linha
    texto = re.sub(r" {2,}", " ", texto)

    return texto.strip()


# ---------------------------------------------------------------------------
# Extração de contexto por frases
# ---------------------------------------------------------------------------

def _extrair_trecho_contexto(texto: str, palavra_chave: str, max_chars: int = 800) -> str:
    """
    Extrai um trecho inteligente ao redor da ocorrência da palavra-chave.

    Estratégia:
    1. Divide o texto em frases (separadas por ponto, exclamação, interrogação, \n\n)
    2. Encontra as frases que contêm a palavra-chave
    3. Adiciona frases adjacentes para dar contexto
    4. Limita ao tamanho máximo

    Args:
        texto:       Texto completo normalizado.
        palavra_chave: Palavra a buscar (case-insensitive).
        max_chars:   Tamanho máximo do trecho retornado.

    Returns:
        Trecho legível em prosa com frases completas.
    """
    if not texto:
        return ""

    # Divide em frases usando pontuação e parágrafos como delimitadores
    frases = re.split(r"(?<=[.!?])\s+|\n{2,}", texto)
    frases = [f.strip() for f in frases if f.strip() and len(f.strip()) > 10]

    if not frases:
        return texto[:max_chars]

    kw_lower = palavra_chave.lower()
    indices_com_kw = [i for i, f in enumerate(frases) if kw_lower in f.lower()]

    if not indices_com_kw:
        # Não achou por frase — fallback para busca por posição no texto bruto
        idx = texto.lower().find(kw_lower)
        if idx == -1:
            return texto[:max_chars]
        inicio = max(0, idx - 300)
        fim = min(len(texto), idx + len(palavra_chave) + 300)
        trecho = texto[inicio:fim].strip()
        if inicio > 0:
            trecho = "..." + trecho
        if fim < len(texto):
            trecho += "..."
        return trecho

    # Coleta frases ao redor do primeiro índice com keyword
    alvo = indices_com_kw[0]
    # Tenta incluir 1 frase antes e 2 depois para contexto
    inicio_idx = max(0, alvo - 1)
    fim_idx = min(len(frases), alvo + 3)

    trecho_frases = frases[inicio_idx:fim_idx]
    trecho = " ".join(trecho_frases)

    # Se ainda muito curto, expande o contexto
    if len(trecho) < 120 and len(frases) > fim_idx:
        trecho_frases = frases[max(0, alvo - 2):min(len(frases), alvo + 5)]
        trecho = " ".join(trecho_frases)

    # Trunca se exceder o máximo
    if len(trecho) > max_chars:
        trecho = trecho[:max_chars].rsplit(" ", 1)[0] + "..."

    # Indica contexto parcial
    if inicio_idx > 0:
        trecho = "..." + trecho

    return trecho.strip()


# ---------------------------------------------------------------------------
# Identificação de tipo e órgão
# ---------------------------------------------------------------------------

def _identificar_tipo(titulo: str) -> str:
    """Identifica o tipo de ato a partir do título."""
    titulo_upper = titulo.upper()
    tipos = ["PORTARIA", "DECRETO", "RESOLUÇÃO", "EDITAL", "AVISO", "INSTRUÇÃO NORMATIVA", "DESPACHO", "ATO"]
    for tipo in tipos:
        if tipo in titulo_upper:
            return tipo
    return "ATO"


def _identificar_orgao(texto: str) -> str:
    """Tenta identificar o órgão emissor do ato."""
    padroes = [
        r"(Secretaria[^\n,.]{3,80})",
        r"(Prefeitura[^\n,.]{3,60})",
        r"(Município de[^\n,.]{3,60})",
        r"(Câmara[^\n,.]{3,60})",
        r"(Fundação[^\n,.]{3,60})",
    ]
    for padrao in padroes:
        match = re.search(padrao, texto, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return ""


# ---------------------------------------------------------------------------
# Utilitários DOM
# ---------------------------------------------------------------------------

def _capturar_link_certificado(page: Page) -> str:
    """
    Tenta capturar a URL da publicação certificada a partir do botão
    'Publicação Certificada' presente na tela de detalhe do ato.

    O portal DOE-SC usa botões que podem abrir PDFs em nova aba ou redirecionar
    para uma URL de certificação. Esta função tenta:
    1. Encontrar o elemento pelo atributo label="Publicação Certificada"
    2. Capturar o href ou o data-url associado
    3. Interceptar via click + nova aba se necessário

    Returns:
        URL da publicação certificada, ou string vazia se não encontrada.
    """
    try:
        # Seletores mais prováveis para o botão de certificação
        seletores = [
            "button[label='Publicação Certificada']",
            "button:has-text('Publicação Certificada')",
            "a:has-text('Publicação Certificada')",
            "a[href*='certificad']",
            "a[href*='publicacao']",
        ]

        for sel in seletores:
            try:
                el = page.query_selector(sel)
                if not el or not el.is_visible():
                    continue

                # Tenta capturar href diretamente
                href = el.get_attribute("href") or ""
                if href and href.startswith("http"):
                    return href

                # Tenta via ng-reflect-href (Angular) ou routerLink
                for attr in ["ng-reflect-href", "ng-reflect-router-link", "data-url", "data-href"]:
                    val = el.get_attribute(attr) or ""
                    if val and val.startswith("http"):
                        return val

                # Intercepção via nova aba — o clique pode abrir um PDF
                with page.context.expect_page(timeout=3000) as new_page_info:
                    el.click()
                new_page = new_page_info.value
                url = new_page.url
                new_page.close()
                if url and url != "about:blank":
                    return url

            except Exception:
                continue

    except Exception as exc:
        logger.debug(f"Não foi possível capturar link certificado: {exc}")

    return ""


def _extrair_titulo_do_card(metadados: str, fallback: str) -> str:
    """Tenta extrair título do ato dos metadados do card."""
    match = re.search(r"(PORTARIA[\s\S]{0,120}?\n)", metadados, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    # Tenta qualquer linha que pareça título de ato normativo
    for linha in metadados.splitlines():
        linha = linha.strip()
        if len(linha) > 10 and re.match(r"^(PORTARIA|DECRETO|RESOLUÇÃO|EDITAL)", linha, re.IGNORECASE):
            return linha
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
        "main",
    ]
    textos = []
    for sel in seletores:
        try:
            elementos = page.query_selector_all(sel)
            for el in elementos:
                if el.is_visible():
                    t = el.inner_text().strip()
                    if t and len(t) > 30:
                        textos.append(t)
        except Exception:
            continue

    if textos:
        return "\n\n".join(textos)

    # Fallback: todos os parágrafos com mais de 60 caracteres
    try:
        return page.evaluate("""() => {
            return Array.from(document.querySelectorAll('p, div.text-justify, span.text-lg'))
                .map(p => p.innerText.trim())
                .filter(t => t.length > 60)
                .join('\\n\\n');
        }""") or ""
    except Exception:
        return ""


def _restaurar_filtros(page: Page, categoria: str, assunto: str) -> None:
    """Garante que a categoria e o assunto continuem selecionados após voltar do detalhe."""
    try:
        selector_cat = (
            'p-dropdown[placeholder*="Selecione uma categoria" i], '
            'p-dropdown:has(span:has-text("Selecione uma categoria"))'
        )
        cat_dropdown = page.locator(selector_cat).first
        if cat_dropdown.is_visible():
            label = cat_dropdown.inner_text().strip()
            if "Selecione uma categoria" in label:
                logger.debug("Dropdown de categoria resetado — restaurando...")
                _primeng_select(page, "Selecione uma categoria", categoria)
                _wait_angular(page)

        selector_ass = (
            'p-dropdown[placeholder*="Selecione um assunto" i], '
            'p-dropdown:has(span:has-text("Selecione um assunto"))'
        )
        sub_dropdown = page.locator(selector_ass).first
        if sub_dropdown.is_visible():
            label = sub_dropdown.inner_text().strip()
            if "Selecione um assunto" in label:
                logger.debug("Dropdown de assunto resetado — restaurando...")
                _primeng_select(page, "Selecione um assunto", assunto)
                _wait_angular(page)

    except Exception as exc:
        logger.warning(f"Falha ao restaurar filtros: {exc}")


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
    """Abre um p-dropdown PrimeNG e seleciona a opção que contém o texto-alvo."""
    try:
        dropdown = page.locator(
            f'p-dropdown[placeholder*="{placeholder}" i], '
            f'p-dropdown:has(span:has-text("{placeholder}"))'
        ).first
        if not dropdown.is_visible():
            return False
        dropdown.click()
        page.wait_for_timeout(500)

        # Aguarda o painel abrir
        try:
            page.wait_for_selector(".p-dropdown-panel:visible", timeout=WAIT_SM)
        except PlaywrightTimeoutError:
            return False

        option = (
            page.locator(".p-dropdown-panel:visible .p-dropdown-item")
            .filter(has_text=texto_alvo)
            .first
        )
        if option.is_visible():
            option.click()
            page.wait_for_timeout(400)
            return True

        logger.warning(f"Opção '{texto_alvo}' não encontrada no dropdown '{placeholder}'")
        page.keyboard.press("Escape")
        return False

    except Exception as exc:
        logger.warning(f"Erro ao selecionar '{texto_alvo}' em '{placeholder}': {exc}")
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass
        return False


def _primeng_list_options(page: Page, placeholder: str) -> list[str]:
    """Abre um p-dropdown PrimeNG e retorna todas as opções disponíveis."""
    opcoes: list[str] = []
    try:
        dropdown = page.locator(
            f'p-dropdown[placeholder*="{placeholder}" i], '
            f'p-dropdown:has(span:has-text("{placeholder}"))'
        ).first
        if not dropdown.is_visible():
            return opcoes

        dropdown.click()
        page.wait_for_timeout(500)

        try:
            page.wait_for_selector(".p-dropdown-panel:visible", timeout=WAIT_SM)
        except PlaywrightTimeoutError:
            return opcoes

        items = page.locator(".p-dropdown-panel:visible .p-dropdown-item")
        opcoes = [t.strip() for t in items.all_inner_texts() if t.strip()]

        page.keyboard.press("Escape")
        page.wait_for_timeout(300)

    except Exception as exc:
        logger.warning(f"Erro ao listar opções de '{placeholder}': {exc}")
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass

    return opcoes


def _primeng_clear(page: Page, placeholder: str) -> None:
    """Limpa a seleção de um p-dropdown PrimeNG."""
    try:
        dropdown = page.locator(
            f'p-dropdown[placeholder*="{placeholder}" i], '
            f'p-dropdown:has(span:has-text("{placeholder}"))'
        ).first
        clear_btn = dropdown.locator(".p-dropdown-clear-icon")
        if clear_btn.is_visible():
            clear_btn.click()
            page.wait_for_timeout(500)
            return
        # Fallback: seleciona a opção vazia se existir
        dropdown.click()
        page.wait_for_timeout(300)
        page.keyboard.press("Escape")
    except Exception as exc:
        logger.debug(f"Erro ao limpar dropdown '{placeholder}': {exc}")
