import streamlit as st
from datetime import date
import pandas as pd

from components.hero import render_hero
from components.footer import render_footer
from services.dou_service import buscar_dou
from services.doesc_service import buscar_doesc


# ---------------------------------------------------------------------------
# Ícones SVG reutilizáveis
# ---------------------------------------------------------------------------

_ICON_SEARCH = """<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24"
    fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line>
</svg>"""

_ICON_FILTER = """<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24"
    fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"></polygon>
</svg>"""

_ICON_RESULT = """<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24"
    fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
    <polyline points="14 2 14 8 20 8"></polyline>
    <line x1="16" y1="13" x2="8" y2="13"></line>
    <line x1="16" y1="17" x2="8" y2="17"></line>
</svg>"""

_ICON_ALERT = """<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24"
    fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <circle cx="12" cy="12" r="10"></circle>
    <line x1="12" y1="8" x2="12" y2="12"></line>
    <line x1="12" y1="16" x2="12.01" y2="16"></line>
</svg>"""

_ICON_SOURCE = """<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24"
    fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <circle cx="12" cy="12" r="10"></circle>
    <polyline points="12 6 12 12 16 14"></polyline>
</svg>"""


# ---------------------------------------------------------------------------
# Funções de execução por fonte
# ---------------------------------------------------------------------------

def _executar_dou(data: date, palavras: list[str]) -> pd.DataFrame:
    return buscar_dou(data_publicacao=data, palavras_chave=palavras)


def _executar_doesc(data: date, palavras: list[str]) -> pd.DataFrame:
    return buscar_doesc(data_publicacao=data, palavras_chave=palavras)


# ---------------------------------------------------------------------------
# Seção: Painel de Filtros
# ---------------------------------------------------------------------------

def _render_filtros() -> dict:
    """Renderiza o painel de filtros e retorna os valores selecionados."""

    st.markdown(f"""
    <div class="section-header">
        <span class="section-icon">{_ICON_FILTER}</span>
        <span class="section-title">Filtros de Busca</span>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([1, 2])

    with col1:
        data_pub = st.date_input(
            "Data da Publicação",
            value=date.today(),
            format="DD/MM/YYYY",
            help="Selecione a data de edição do Diário Oficial a ser consultado.",
        )

    with col2:
        palavras_raw = st.text_input(
            "Palavras-chave",
            placeholder="Ex: convênio, repasse, município...",
            help="Separe os termos por vírgula. A busca é feita no título e no texto do ato.",
        )

    fontes = st.multiselect(
        "Fontes de Pesquisa",
        options=[
            "Diário Oficial da União",
            "Diário Oficial de Santa Catarina",
            "Diário Oficial de Joinville",
        ],
        default=["Diário Oficial da União"],
        help=(
            "Selecione as fontes a serem consultadas. "
            "DOU e DOE-SC disponíveis. Joinville em desenvolvimento."
        ),
    )

    return {
        "data": data_pub,
        "palavras": [p.strip() for p in palavras_raw.split(",") if p.strip()],
        "fontes": fontes,
    }


# ---------------------------------------------------------------------------
# Seção: Exibição de Resultados
# ---------------------------------------------------------------------------

def _render_resultados(df: pd.DataFrame, palavras_chave: list[str]) -> None:
    """Renderiza os resultados da busca em cards estilizados."""

    st.markdown(f"""
    <div class="section-header" style="margin-top: 2rem;">
        <span class="section-icon">{_ICON_RESULT}</span>
        <span class="section-title">Resultados Encontrados</span>
    </div>
    """, unsafe_allow_html=True)

    if df.empty:
        st.markdown(f"""
        <div class="alert-box">
            <span>{_ICON_ALERT}</span>
            <span>Nenhuma publicação encontrada para os critérios informados.
            Verifique a data, os filtros e as palavras-chave.</span>
        </div>
        """, unsafe_allow_html=True)
        return

    st.markdown(
        f'<div class="result-count">{len(df)} publicação(ões) encontrada(s)</div>',
        unsafe_allow_html=True,
    )

    for _, linha in df.iterrows():
        titulo_html    = _destacar_palavras(str(linha.get("titulo", "")), palavras_chave)
        descricao_html = _destacar_palavras(str(linha.get("descricao", "")), palavras_chave)
        hierarquia     = str(linha.get("hierarquia", ""))
        link           = str(linha.get("link", ""))
        origem         = str(linha.get("origem", "DOU"))

        if link and not link.startswith("http"):
            url_completa = f"https://www.in.gov.br{link}"
        else:
            url_completa = link

        badge_origem = _badge_origem(origem)

        st.markdown(f"""
        <div class="result-card">
            <div class="result-breadcrumb">{hierarquia} {badge_origem}</div>
            <div class="result-title">
                {"<a href='" + url_completa + "' target='_blank' rel='noopener noreferrer'>" if url_completa else "<span>"}
                    {titulo_html}
                {"</a>" if url_completa else "</span>"}
            </div>
            <div class="result-description">{descricao_html}</div>
        </div>
        """, unsafe_allow_html=True)


def _badge_origem(origem: str) -> str:
    """Retorna um badge HTML indicando a fonte da publicação."""
    cores = {
        "DOU":    ("#dbeafe", "#1d4ed8"),
        "DOE-SC": ("#dcfce7", "#15803d"),
        "DOE-JOI":("#fef9c3", "#92400e"),
    }
    chave = "DOU" if "União" in origem or origem == "DOU" else (
        "DOE-SC" if "Santa Catarina" in origem or origem == "DOE-SC" else "DOE-JOI"
    )
    bg, cor = cores.get(chave, ("#f1f5f9", "#334155"))
    label   = {"DOU": "DOU", "DOE-SC": "DOE-SC", "DOE-JOI": "DOE-JOI"}.get(chave, origem)
    return (
        f'<span style="display:inline-block;margin-left:6px;padding:1px 8px;'
        f'border-radius:999px;background:{bg};color:{cor};'
        f'font-size:0.7rem;font-weight:600;letter-spacing:0.05em;">{label}</span>'
    )


def _destacar_palavras(texto: str, palavras: list[str]) -> str:
    """Envolve as palavras-chave no texto com marcação de destaque."""
    import re
    for palavra in palavras:
        if not palavra:
            continue
        padrao = re.compile(re.escape(palavra), re.IGNORECASE)
        texto = padrao.sub(
            lambda m: f'<mark class="keyword-highlight">{m.group()}</mark>',
            texto,
        )
    return texto


# ---------------------------------------------------------------------------
# Orquestrador principal de busca
# ---------------------------------------------------------------------------

def _executar_varredura(filtros: dict) -> pd.DataFrame:
    """Executa a varredura em todas as fontes selecionadas e consolida."""
    frames: list[pd.DataFrame] = []
    fontes_sel = filtros["fontes"]
    data       = filtros["data"]
    palavras   = filtros["palavras"]

    for fonte in fontes_sel:
        if fonte == "Diário Oficial da União":
            with st.status(f"Varrendo {fonte}...", expanded=False):
                try:
                    df = _executar_dou(data, palavras)
                    df["origem"] = "DOU"
                    frames.append(df)
                    st.write(f"{len(df)} resultado(s) encontrado(s) no DOU.")
                except Exception as e:
                    st.error(f"Erro ao acessar o DOU: {e}")

        elif fonte == "Diário Oficial de Santa Catarina":
            with st.status(f"Varrendo {fonte}...", expanded=False):
                try:
                    df = _executar_doesc(data, palavras)
                    frames.append(df)
                    st.write(f"{len(df)} resultado(s) encontrado(s) no DOE-SC.")
                except Exception as e:
                    st.error(f"Erro ao acessar o DOE-SC: {e}")

        elif fonte == "Diário Oficial de Joinville":
            st.info("O módulo do Diário Oficial de Joinville está em desenvolvimento.")

    if not frames:
        return pd.DataFrame(columns=["origem", "hierarquia", "titulo", "link", "descricao"])

    return pd.concat(frames, ignore_index=True)


# ---------------------------------------------------------------------------
# Ponto de entrada principal da página
# ---------------------------------------------------------------------------

def render_home():

    render_hero()

    st.markdown("""
    <div class="page-intro">
        <h1 class="page-title">Plataforma Vigília</h1>
        <p class="page-subtitle">
            Sistema institucional de inteligência e monitoramento automatizado
            de publicações em diários oficiais.
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    filtros = _render_filtros()

    st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)

    iniciar = st.button(
        "Iniciar Varredura",
        type="primary",
        use_container_width=False,
        key="btn_busca",
    )

    st.divider()

    if iniciar:
        if not filtros["fontes"]:
            st.warning("Selecione ao menos uma fonte de pesquisa.")
        else:
            df_consolidado = _executar_varredura(filtros)
            st.session_state["df_resultados"]  = df_consolidado
            st.session_state["palavras_busca"] = filtros["palavras"]

    # Renderiza resultados persistidos
    if "df_resultados" in st.session_state and st.session_state["df_resultados"] is not None:
        _render_resultados(
            st.session_state["df_resultados"],
            st.session_state.get("palavras_busca", []),
        )

    render_footer()