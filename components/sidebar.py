import base64
from pathlib import Path

import streamlit as st


# ---------------------------------------------------------------------------
# Easter Egg
# ---------------------------------------------------------------------------

if hasattr(st, "dialog"):

    @st.dialog("😂 Você clicou mesmo")
    def _mostrar_surpresa():
        st.image("assets/foto_barbara.png", use_container_width=True)

        st.markdown("""
        <div style="
            text-align:center;
            color:#475569;
            font-size:0.95rem;
            margin-top:0.5rem;
            line-height:1.7;
        ">
            Eu literalmente avisei pra não clicar.
        </div>
        """, unsafe_allow_html=True)

        if st.button("Fechar", key="fechar_barbara_dialog"):
            st.rerun()

else:

    def _mostrar_surpresa():
        st.session_state["show_barbara"] = True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _img_to_base64(path: str) -> str:
    """Converte imagem local em base64."""
    try:
        data = Path(path).read_bytes()

        ext = Path(path).suffix.lstrip(".").lower()

        mime = (
            "image/png"
            if ext == "png"
            else f"image/{ext}"
        )

        b64 = base64.b64encode(data).decode()

        return f"data:{mime};base64,{b64}"

    except Exception:
        return ""


# ---------------------------------------------------------------------------
# CSS GLOBAL SIDEBAR
# ---------------------------------------------------------------------------

def _inject_sidebar_css():

    st.markdown("""
    <style>

    section[data-testid="stSidebar"] {
        background:
            linear-gradient(
                180deg,
                #0f172a 0%,
                #111827 100%
            );

        border-right:
            1px solid rgba(148, 163, 184, 0.08);
    }

    section[data-testid="stSidebar"] > div {
        padding-top: 1rem;
    }

    .vigilia-sidebar-header {
        position: relative;

        overflow: hidden;

        padding:
            2rem
            1.3rem
            1.7rem
            1.3rem;

        margin-bottom: 1.4rem;

        border-radius: 28px;

        background:
            linear-gradient(
                145deg,
                rgba(15, 23, 42, 0.95),
                rgba(30, 41, 59, 0.98)
            );

        border:
            1px solid rgba(56, 189, 248, 0.14);

        text-align: center;

        box-shadow:
            0 18px 40px rgba(0,0,0,0.28);
    }

    .vigilia-sidebar-header::before {
        content: "";

        position: absolute;

        top: -120px;
        right: -120px;

        width: 240px;
        height: 240px;

        background:
            radial-gradient(
                circle,
                rgba(14,165,233,0.18),
                transparent 72%
            );

        pointer-events: none;
    }

    .sidebar-logo {
        width: 78px;
        height: 78px;

        object-fit: cover;

        border-radius: 24px;

        margin-bottom: 1rem;

        box-shadow:
            0 10px 30px rgba(14,165,233,0.22);

        border:
            1px solid rgba(255,255,255,0.08);
    }

    .vigilia-sidebar-app-name {
        color: #f8fafc;

        font-size: 1.5rem;
        font-weight: 800;

        letter-spacing: 0.02em;

        margin-bottom: 0.25rem;
    }

    .vigilia-sidebar-subtitle {
        color: #7dd3fc;

        font-size: 0.85rem;
        font-weight: 600;

        letter-spacing: 0.08em;
        text-transform: uppercase;
    }

    .vigilia-sidebar-description {
        color: #cbd5e1;

        font-size: 0.88rem;
        line-height: 1.75;

        margin:
            0 0 1.6rem 0;
    }

    .vigilia-sidebar-section {
        display: flex;
        align-items: center;
        gap: 0.6rem;

        color: #f8fafc;

        font-size: 0.82rem;
        font-weight: 700;

        letter-spacing: 0.08em;
        text-transform: uppercase;

        margin:
            1.8rem 0 0.9rem 0;
    }

    .vigilia-sidebar-dot {
        width: 8px;
        height: 8px;

        border-radius: 999px;

        background: #38bdf8;

        box-shadow:
            0 0 12px rgba(56,189,248,0.7);
    }

    .vigilia-source-card {
        position: relative;

        overflow: hidden;

        padding:
            1rem
            1rem
            0.7rem
            1rem;

        margin-bottom: 1rem;

        border-radius: 22px;

        background:
            linear-gradient(
                145deg,
                rgba(15,23,42,0.92),
                rgba(30,41,59,0.96)
            );

        border:
            1px solid rgba(148,163,184,0.10);

        transition:
            border 0.25s ease,
            transform 0.25s ease;
    }

    .vigilia-source-card:hover {
        border:
            1px solid rgba(56,189,248,0.22);

        transform: translateY(-2px);
    }

    .vigilia-source-description {
        color: #94a3b8;

        font-size: 0.79rem;
        line-height: 1.65;

        margin-top: 0.45rem;
    }

    .vigilia-dev-badge {
        display: inline-flex;
        align-items: center;

        margin-left: 0.45rem;

        padding:
            0.2rem
            0.55rem;

        border-radius: 999px;

        background:
            rgba(251,191,36,0.12);

        border:
            1px solid rgba(251,191,36,0.25);

        color: #fde68a;

        font-size: 0.66rem;
        font-weight: 700;

        letter-spacing: 0.06em;
    }

    .vigilia-easter-button button {
        margin-top: 0.5rem;

        background:
            linear-gradient(
                135deg,
                #0ea5e9,
                #0284c7
            ) !important;

        color: white !important;

        border: none !important;

        border-radius: 14px !important;

        font-weight: 700 !important;

        height: 3rem !important;

        transition:
            transform 0.2s ease,
            box-shadow 0.2s ease !important;

        box-shadow:
            0 10px 24px rgba(14,165,233,0.22);
    }

    .vigilia-easter-button button:hover {
        transform: translateY(-2px);

        box-shadow:
            0 14px 30px rgba(14,165,233,0.28);
    }

    .vigilia-sidebar-footer {
        margin-top: 2rem;

        padding-top: 1.4rem;

        border-top:
            1px solid rgba(148,163,184,0.08);

        text-align: center;

        color: #94a3b8;

        font-size: 0.76rem;
        line-height: 1.7;
    }

    .vigilia-sidebar-footer strong {
        color: #f8fafc;
    }

    .vigilia-sidebar-footer-highlight {
        color: #38bdf8;
        font-weight: 700;
    }

    </style>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Render Principal
# ---------------------------------------------------------------------------

def render_sidebar():

    _inject_sidebar_css()

    with st.sidebar:

        # -------------------------------------------------------------------
        # HEADER
        # -------------------------------------------------------------------

        logo_src = _img_to_base64("assets/icone_vigilia.png")

        logo_tag = (
            f'<img class="sidebar-logo" src="{logo_src}" alt="Vigília Logo">'
            if logo_src
            else ""
        )

        st.markdown(f"""
        <div class="vigilia-sidebar-header">

            {logo_tag}

            <div class="vigilia-sidebar-app-name">
                Vigília
            </div>

            <div class="vigilia-sidebar-subtitle">
                Inteligência Regulatória
            </div>

        </div>
        """, unsafe_allow_html=True)

        # -------------------------------------------------------------------
        # DESCRIÇÃO
        # -------------------------------------------------------------------

        st.markdown("""
        <div class="vigilia-sidebar-description">
            Plataforma institucional para monitoramento automatizado
            de publicações oficiais, análise normativa e rastreamento
            estratégico de atos administrativos.
        </div>
        """, unsafe_allow_html=True)

        # -------------------------------------------------------------------
        # SEÇÃO
        # -------------------------------------------------------------------

        st.markdown("""
        <div class="vigilia-sidebar-section">
            <div class="vigilia-sidebar-dot"></div>
            Fontes de Monitoramento
        </div>
        """, unsafe_allow_html=True)

        # -------------------------------------------------------------------
        # DOU
        # -------------------------------------------------------------------

        st.markdown('<div class="vigilia-source-card">', unsafe_allow_html=True)

        st.checkbox(
            "Diário Oficial da União",
            value=True,
            key="src_dou",
        )

        st.markdown("""
        <div class="vigilia-source-description">
            Varredura da Seção 1 com foco em atos normativos,
            portarias e publicações vinculadas ao Ministério da Saúde.
        </div>
        """, unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

        # -------------------------------------------------------------------
        # DOE-SC
        # -------------------------------------------------------------------

        st.markdown('<div class="vigilia-source-card">', unsafe_allow_html=True)

        st.checkbox(
            "Diário Oficial de Santa Catarina",
            value=True,
            key="src_doesc",
        )

        st.markdown("""
        <div class="vigilia-source-description">
            Monitoramento de edições ordinárias e extras do Estado,
            incluindo atos relacionados à saúde e gestão pública.
        </div>
        """, unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

        # -------------------------------------------------------------------
        # DOE JOINVILLE
        # -------------------------------------------------------------------

        st.markdown('<div class="vigilia-source-card">', unsafe_allow_html=True)

        st.checkbox(
            "Diário Oficial de Joinville",
            value=False,
            key="src_doej",
        )

        st.markdown("""
        <div class="vigilia-source-description">
            Integração municipal em fase final de desenvolvimento.
            <span class="vigilia-dev-badge">
                EM BREVE
            </span>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

        # -------------------------------------------------------------------
        # EASTER EGG
        # -------------------------------------------------------------------

        st.markdown(
            '<div class="vigilia-easter-button">',
            unsafe_allow_html=True
        )

        if st.button(
            "NÃO CLIQUE, BARBARA 😂",
            key="btn_barbara",
            use_container_width=True,
        ):
            st.balloons()
            _mostrar_surpresa()

        st.markdown("</div>", unsafe_allow_html=True)

        if (
            not hasattr(st, "dialog")
            and st.session_state.get("show_barbara", False)
        ):

            with st.container(border=True):

                st.subheader("😂 Você clicou mesmo")

                st.image(
                    "assets/foto_barbara.png",
                    use_container_width=True
                )

                st.markdown("""
                <div style="
                    text-align:center;
                    color:#475569;
                    margin-top:0.6rem;
                    line-height:1.7;
                ">
                    Eu literalmente avisei pra não clicar.
                </div>
                """, unsafe_allow_html=True)

                if st.button("Fechar", key="close_barbara"):
                    st.session_state["show_barbara"] = False
                    st.rerun()

        # -------------------------------------------------------------------
        # FOOTER
        # -------------------------------------------------------------------

        st.markdown("""
        <div class="vigilia-sidebar-footer">

            <strong>
                Secretaria Municipal da Saúde
            </strong>

            <br>

            Joinville • Unidade de Convênios e Parcerias

            <br><br>

            Desenvolvido por
            <span class="vigilia-sidebar-footer-highlight">
                Enf. Bruno Vinícius
            </span>

        </div>
        """, unsafe_allow_html=True)