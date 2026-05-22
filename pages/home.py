import streamlit as st
from datetime import date
import pandas as pd

from components.hero import render_hero
from components.footer import render_footer
from services.dou_service import buscar_dou
from services.doesc_service import buscar_doesc_direto


# -----------------------------------------------------------------------------
# Ícones SVG
# -----------------------------------------------------------------------------

_ICON_FILTER = """
<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18"
viewBox="0 0 24 24" fill="none" stroke="currentColor"
stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"></polygon>
</svg>
"""

_ICON_RESULT = """
<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18"
viewBox="0 0 24 24" fill="none" stroke="currentColor"
stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
<polyline points="14 2 14 8 20 8"></polyline>
<line x1="16" y1="13" x2="8" y2="13"></line>
<line x1="16" y1="17" x2="8" y2="17"></line>
</svg>
"""

_ICON_ALERT = """
<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18"
viewBox="0 0 24 24" fill="none" stroke="currentColor"
stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<circle cx="12" cy="12" r="10"></circle>
<line x1="12" y1="8" x2="12" y2="12"></line>
<line x1="12" y1="16" x2="12.01" y2="16"></line>
</svg>
"""

_ICON_SEARCH = """
<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18"
viewBox="0 0 24 24" fill="none" stroke="currentColor"
stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<circle cx="11" cy="11" r="8"></circle>
<line x1="21" y1="21" x2="16.65" y2="16.65"></line>
</svg>
"""


# -----------------------------------------------------------------------------
# Execução de serviços
# -----------------------------------------------------------------------------

def _executar_dou(
    data: date,
    palavras: list[str],
    operador: str = "OU",
) -> pd.DataFrame:
    return buscar_dou(
        data_publicacao=data,
        palavras_chave=palavras,
        operador=operador,
    )


def _executar_doesc(
    data: date,
    palavras: list[str],
    operador: str = "OU",
) -> pd.DataFrame:
    return buscar_doesc_direto(
        data_publicacao=data,
        palavras_chave=palavras,
        operador=operador,
    )


# -----------------------------------------------------------------------------
# Hero institucional da home
# -----------------------------------------------------------------------------

def _render_intro():
    st.markdown(
        """
        <div class="vigilia-home-hero">

            <div class="vigilia-home-badge">
                Plataforma Institucional • Monitoramento Estratégico
            </div>

            <h1 class="vigilia-home-title">
                Inteligência automatizada para monitoramento
                de Diários Oficiais
            </h1>

            <p class="vigilia-home-description">
                Centralize a busca, rastreie publicações relevantes em tempo real
                e reduza o tempo operacional das equipes institucionais.
            </p>

            <div class="vigilia-home-stats">
                <div class="vigilia-stat-card">
                    <div class="vigilia-stat-number">DOU</div>
                    <div class="vigilia-stat-label">União</div>
                </div>

                <div class="vigilia-stat-card">
                    <div class="vigilia-stat-number">DOE</div>
                    <div class="vigilia-stat-label">Santa Catarina</div>
                </div>

                <div class="vigilia-stat-card">
                    <div class="vigilia-stat-number">24h</div>
                    <div class="vigilia-stat-label">Monitoramento</div>
                </div>
            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )


# -----------------------------------------------------------------------------
# Painel de filtros
# -----------------------------------------------------------------------------

def _render_filtros() -> dict:

    st.markdown(
        f"""
        <div class="vigilia-section-header">
            <div class="vigilia-section-icon">
                {_ICON_FILTER}
            </div>

            <div>
                <div class="vigilia-section-title">
                    Filtros da Varredura
                </div>

                <div class="vigilia-section-subtitle">
                    Configure os parâmetros utilizados na pesquisa automatizada.
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.container(border=True):

        col1, col2 = st.columns([1, 2])

        with col1:
            data_pub = st.date_input(
                "Data da publicação",
                value=date.today(),
                format="DD/MM/YYYY",
                help="Selecione a edição do Diário Oficial.",
            )

        with col2:
            palavras_raw = st.text_input(
                "Palavras-chave",
                placeholder="Ex: convênio, incentivo, financiamento...",
                help="Separe múltiplos termos utilizando vírgula.",
            )

        operador = st.radio(
            "Operador lógico",
            options=["OU", "E"],
            horizontal=True,
            help=(
                "OU → retorna publicações contendo qualquer termo.\n"
                "E → retorna apenas publicações contendo TODOS os termos."
            ),
        )

    fontes = []

    if st.session_state.get("src_dou", True):
        fontes.append("Diário Oficial da União")

    if st.session_state.get("src_doesc", False):
        fontes.append("Diário Oficial de Santa Catarina")

    if st.session_state.get("src_doej", False):
        fontes.append("Diário Oficial de Joinville")

    return {
        "data": data_pub,
        "palavras": [p.strip() for p in palavras_raw.split(",") if p.strip()],
        "fontes": fontes,
        "operador": operador,
    }


# -----------------------------------------------------------------------------
# Renderização de resultados
# -----------------------------------------------------------------------------

def _render_resultados(
    df: pd.DataFrame,
    palavras_chave: list[str],
) -> None:

    st.markdown(
        f"""
        <div class="vigilia-results-header">

            <div class="vigilia-section-header">
                <div class="vigilia-section-icon">
                    {_ICON_RESULT}
                </div>

                <div>
                    <div class="vigilia-section-title">
                        Resultados Encontrados
                    </div>

                    <div class="vigilia-section-subtitle">
                        Publicações identificadas na varredura institucional.
                    </div>
                </div>
            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )

    if df.empty:
        st.markdown(
            f"""
            <div class="vigilia-empty-state">
                <div class="vigilia-empty-icon">
                    {_ICON_ALERT}
                </div>

                <div>
                    <div class="vigilia-empty-title">
                        Nenhuma publicação encontrada
                    </div>

                    <div class="vigilia-empty-text">
                        Ajuste os filtros ou revise as palavras-chave utilizadas.
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    st.markdown(
        f"""
        <div class="vigilia-results-counter">
            {len(df)} publicação(ões) encontrada(s)
        </div>
        """,
        unsafe_allow_html=True,
    )

    # -------------------------------------------------------------------------
    # PAINEL DE INTEROPERABILIDADE (FHIR & HL7)
    # -------------------------------------------------------------------------
    with st.expander("🔗 Interoperabilidade de Saúde (FHIR & HL7 v3 / Messaging)"):
        st.markdown("""
        <div style="font-size: 0.9rem; color: #cbd5e1; margin-bottom: 0.8rem;">
            Esta seção demonstra a interoperabilidade semântica do Vigília. Os atos normativos extraídos 
            são estruturados como recursos <strong>FHIR DocumentReference</strong> (R4) e encapsulados 
            em um <strong>FHIR Message Bundle</strong> (HL7) para futura integração com barramentos de saúde do SUS e do PEP municipal.
        </div>
        """, unsafe_allow_html=True)
        
        try:
            from services.fhir_service import to_fhir_document_reference, create_hl7_fhir_message_bundle
            import json
            
            # Converter linhas para recursos FHIR
            fhir_resources = []
            for _, row in df.iterrows():
                act_dict = row.to_dict()
                if "tipo" not in act_dict:
                    from services.doesc_service import _extrair_tipo
                    act_dict["tipo"] = _extrair_tipo(act_dict.get("titulo", ""), act_dict.get("hierarquia", ""))
                fhir_res = to_fhir_document_reference(act_dict)
                fhir_resources.append(fhir_res)
            
            # Criar Bundle de Mensagem HL7/FHIR
            hl7_bundle = create_hl7_fhir_message_bundle(fhir_resources)
            bundle_json = json.dumps(hl7_bundle, indent=2, ensure_ascii=False)
            
            # Exibir visualização do primeiro recurso FHIR
            if fhir_resources:
                col_left, col_right = st.columns([1, 1])
                with col_left:
                    st.markdown("##### Exemplo de Recurso FHIR DocumentReference (Único)")
                    st.json(fhir_resources[0])
                with col_right:
                    st.markdown("##### Estrutura do FHIR Message Bundle (HL7)")
                    st.json({
                        "resourceType": hl7_bundle["resourceType"],
                        "id": hl7_bundle["id"],
                        "type": hl7_bundle["type"],
                        "timestamp": hl7_bundle["timestamp"],
                        "total_entries": len(hl7_bundle["entry"]),
                        "message_header": hl7_bundle["entry"][0]["resource"]
                    })
            
            st.download_button(
                label="📥 Baixar FHIR Bundle Completo (JSON)",
                data=bundle_json,
                file_name=f"vigilia_fhir_bundle_{df['data'].iloc[0].replace('/', '-')}.json",
                mime="application/json",
                use_container_width=True
            )
        except Exception as e:
            st.error(f"Erro ao processar mapeamento FHIR: {e}")

    nomes_fontes = {
        "DOU": "Diário Oficial da União",
        "DOE-SC": "Diário Oficial de Santa Catarina",
        "DOE-JOI": "Diário Oficial de Joinville",
    }

    origens_presentes = df["origem"].unique()

    ordem_preferencial = [
        "DOU",
        "DOE-SC",
        "DOE-JOI",
    ]

    origens_ordenadas = [
        o for o in ordem_preferencial if o in origens_presentes
    ]

    origens_ordenadas += [
        o for o in origens_presentes
        if o not in origens_ordenadas
    ]

    for idx_grp, origem_grupo in enumerate(origens_ordenadas):

        if idx_grp > 0:
            st.markdown("<div style='height: 1rem'></div>", unsafe_allow_html=True)

        st.markdown(
            f"""
            <div class="vigilia-group-title">
                {nomes_fontes.get(origem_grupo, origem_grupo)}
            </div>
            """,
            unsafe_allow_html=True,
        )

        df_grupo = df[df["origem"] == origem_grupo]

        for _, linha in df_grupo.iterrows():

            titulo = str(linha.get("titulo", ""))
            descricao = str(linha.get("descricao", ""))
            resumo = str(linha.get("resumo", ""))
            hierarquia = str(linha.get("hierarquia", ""))
            link = str(linha.get("link", ""))
            origem = str(linha.get("origem", "DOU"))
            data_pub = str(linha.get("data", ""))

            if not data_pub:
                data_pub = date.today().strftime("%d/%m/%Y")

            badge_origem = _badge_origem(origem)

            titulo_html = _destacar_palavras(titulo, palavras_chave)
            descricao_html = _destacar_palavras(descricao, palavras_chave)
            resumo_html = _destacar_palavras(resumo, palavras_chave)

            if link and not link.startswith("http") and origem == "DOU":
                link = f"https://in.gov.br{link}"

            st.markdown(
                f"""
                <div class="vigilia-result-card">

                    <div class="vigilia-result-top">

                        <div class="vigilia-result-hierarchy">
                            {hierarquia}
                        </div>

                        <div class="vigilia-result-date">
                            {data_pub}
                            {badge_origem}
                        </div>

                    </div>

                    <div class="vigilia-result-title">
                        <a href="{link}" target="_blank">
                            {titulo_html}
                        </a>
                    </div>

                    <div class="vigilia-result-description">
                        {resumo_html if resumo else descricao_html}
                    </div>

                    <div class="vigilia-result-actions">
                        <a
                            href="{link}"
                            target="_blank"
                            class="vigilia-result-button"
                        >
                            {_ICON_SEARCH}
                            Acessar publicação oficial
                        </a>
                    </div>

                </div>
                """,
                unsafe_allow_html=True,
            )


# -----------------------------------------------------------------------------
# Badge de origem
# -----------------------------------------------------------------------------

def _badge_origem(origem: str) -> str:

    cores = {
        "DOU": ("#DBEAFE", "#1D4ED8"),
        "DOE-SC": ("#DCFCE7", "#15803D"),
        "DOE-JOI": ("#FEF3C7", "#92400E"),
    }

    chave = (
        "DOU"
        if "União" in origem or origem == "DOU"
        else (
            "DOE-SC"
            if "Santa Catarina" in origem or origem == "DOE-SC"
            else "DOE-JOI"
        )
    )

    bg, cor = cores.get(chave, ("#E2E8F0", "#334155"))

    return (
        f"<span class='vigilia-badge' "
        f"style='background:{bg}; color:{cor};'>"
        f"{chave}"
        f"</span>"
    )


# -----------------------------------------------------------------------------
# Destaque de palavras-chave
# -----------------------------------------------------------------------------

def _destacar_palavras(texto: str, palavras: list[str]) -> str:
    import re

    for palavra in palavras:

        if not palavra:
            continue

        padrao = re.compile(re.escape(palavra), re.IGNORECASE)

        texto = padrao.sub(
            lambda m: (
                f"<mark class='keyword-highlight'>"
                f"{m.group()}"
                f"</mark>"
            ),
            texto,
        )

    return texto


# -----------------------------------------------------------------------------
# Orquestrador da busca
# -----------------------------------------------------------------------------

def _executar_varredura(filtros: dict) -> pd.DataFrame:

    frames: list[pd.DataFrame] = []

    fontes_sel = filtros["fontes"]
    data = filtros["data"]
    palavras = filtros["palavras"]
    operador = filtros.get("operador", "OU")

    data_str = data.strftime("%d/%m/%Y")

    for fonte in fontes_sel:

        if fonte == "Diário Oficial da União":

            with st.status(
                f"Varrendo {fonte}...",
                expanded=False,
            ):

                try:

                    df = _executar_dou(
                        data,
                        palavras,
                        operador,
                    )

                    df["origem"] = "DOU"
                    df["data"] = data_str

                    frames.append(df)

                    st.write(
                        f"{len(df)} publicação(ões) encontradas no DOU."
                    )

                except Exception as e:
                    st.error(f"Erro ao acessar o DOU: {e}")

        elif fonte == "Diário Oficial de Santa Catarina":

            with st.status(
                f"Varrendo {fonte}...",
                expanded=False,
            ):

                try:

                    df = _executar_doesc(
                        data,
                        palavras,
                        operador,
                    )

                    df["origem"] = "DOE-SC"
                    df["data"] = data_str

                    frames.append(df)

                    st.write(
                        f"{len(df)} publicação(ões) encontradas no DOE-SC."
                    )

                except Exception as e:
                    st.error(f"Erro ao acessar o DOE-SC: {e}")

        elif fonte == "Diário Oficial de Joinville":

            st.info(
                "O módulo do Diário Oficial de Joinville ainda está em desenvolvimento."
            )

    if not frames:
        return pd.DataFrame(
            columns=[
                "origem",
                "hierarquia",
                "titulo",
                "link",
                "descricao",
                "data",
            ]
        )

    return pd.concat(frames, ignore_index=True)


# -----------------------------------------------------------------------------
# Página principal
# -----------------------------------------------------------------------------

def render_home():

    render_hero()

    _render_intro()

    st.markdown("<div style='height: 1rem'></div>", unsafe_allow_html=True)

    filtros = _render_filtros()

    st.markdown("<div style='height: 1rem'></div>", unsafe_allow_html=True)

    iniciar = st.button(
        "Iniciar Varredura",
        type="primary",
        key="btn_busca",
        use_container_width=True,
    )

    if iniciar:

        if not filtros["fontes"]:

            st.warning(
                "Selecione pelo menos um Diário Oficial para realizar a busca."
            )

            st.stop()

        df_consolidado = _executar_varredura(filtros)

        st.session_state["df_resultados"] = df_consolidado
        st.session_state["palavras_busca"] = filtros["palavras"]

    if (
        "df_resultados" in st.session_state
        and st.session_state["df_resultados"] is not None
    ):

        st.markdown(
            "<div style='height: 2rem'></div>",
            unsafe_allow_html=True,
        )

        _render_resultados(
            st.session_state["df_resultados"],
            st.session_state.get("palavras_busca", []),
        )

    render_footer()