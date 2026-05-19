import streamlit as st
from datetime import date

from components.hero import render_hero
from components.footer import render_footer
from services.dou_service import buscar_dou


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
            help="Separe os termos por vírgula. A busca é feita no título e na descrição do ato.",
        )

    fontes = st.multiselect(
        "Fontes de Pesquisa",
        options=[
            "Diário Oficial da União",
            "Diário Oficial de Santa Catarina",
            "Diário Oficial de Joinville",
        ],
        default=["Diário Oficial da União"],
        help="Selecione as fontes a serem consultadas. Nesta versão, apenas o DOU está disponível.",
    )

    return {
        "data": data_pub,
        "palavras": [p.strip() for p in palavras_raw.split(",") if p.strip()],
        "fontes": fontes,
    }


# ---------------------------------------------------------------------------
# Seção: Exibição de Resultados
# ---------------------------------------------------------------------------

def _render_resultados(df, palavras_chave: list[str]) -> None:
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
        # Destaca palavras-chave no título e na descrição
        titulo_html = _destacar_palavras(str(linha.get("titulo", "")), palavras_chave)
        descricao_html = _destacar_palavras(str(linha.get("descricao", "")), palavras_chave)
        hierarquia = str(linha.get("hierarquia", ""))
        link = str(linha.get("link", ""))
        url_completa = f"https://www.in.gov.br{link}" if link and not link.startswith("http") else link

        st.markdown(f"""
        <div class="result-card">
            <div class="result-breadcrumb">{hierarquia}</div>
            <div class="result-title">
                <a href="{url_completa}" target="_blank" rel="noopener noreferrer">
                    {titulo_html}
                </a>
            </div>
            <div class="result-description">{descricao_html}</div>
        </div>
        """, unsafe_allow_html=True)


def _destacar_palavras(texto: str, palavras: list[str]) -> str:
    """Envolve as palavras-chave encontradas no texto com uma tag de destaque."""
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
        if "Diário Oficial da União" not in filtros["fontes"]:
            st.warning(
                "Selecione o 'Diário Oficial da União' como fonte. "
                "As demais fontes ainda não estão disponíveis nesta versão."
            )
        else:
            with st.spinner("Conectando ao Diário Oficial da União e extraindo publicações..."):
                try:
                    df = buscar_dou(
                        data_publicacao=filtros["data"],
                        palavras_chave=filtros["palavras"],
                    )
                    st.session_state["df_resultados"] = df
                    st.session_state["palavras_busca"] = filtros["palavras"]
                except Exception as e:
                    st.error(f"Ocorreu um erro durante a varredura: {e}")
                    st.session_state["df_resultados"] = None

    # Renderiza resultados se existirem no estado da sessão
    if "df_resultados" in st.session_state and st.session_state["df_resultados"] is not None:
        _render_resultados(
            st.session_state["df_resultados"],
            st.session_state.get("palavras_busca", []),
        )

    render_footer()