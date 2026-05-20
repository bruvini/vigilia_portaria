import base64
from pathlib import Path

import streamlit as st


# ---------------------------------------------------------------------------
# Easter Egg
# ---------------------------------------------------------------------------

if hasattr(st, "dialog"):
    @st.dialog("Surpresa!")
    def _mostrar_surpresa():
        st.image("assets/foto_barbara.png", use_container_width=True)
        if st.button("Fechar", key="fechar_barbara_dialog"):
            st.rerun()
else:
    def _mostrar_surpresa():
        st.session_state["show_barbara"] = True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _img_to_base64(path: str) -> str:
    """Converte imagem para base64 para embutir no HTML sem depender de URL."""
    try:
        data = Path(path).read_bytes()
        ext = Path(path).suffix.lstrip(".").lower()
        mime = "image/png" if ext == "png" else f"image/{ext}"
        b64 = base64.b64encode(data).decode()
        return f"data:{mime};base64,{b64}"
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Render principal
# ---------------------------------------------------------------------------

def render_sidebar():
    with st.sidebar:

        # ── Cabeçalho escuro premium ──────────────────────────────────────────
        logo_src = _img_to_base64("assets/icone_vigilia.png")
        logo_tag = (
            f'<img class="sidebar-logo" src="{logo_src}" alt="Vigília Logo">'
            if logo_src else
            '<div style="width:64px;height:64px;margin:0 auto 0.75rem;'
            'background:#1e3a5f;border-radius:50%;"></div>'
        )

        st.markdown(
            f"""
            <div class="sidebar-header">
                {logo_tag}
                <div class="sidebar-app-name">Vigília</div>
                <div class="sidebar-subtitle">Monitoramento Estratégico</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ── Descrição institucional ───────────────────────────────────────────
        st.markdown(
            """
            <p style="font-size:0.82rem; color:#475569; line-height:1.6; margin:0 0 1rem 0;">
                Plataforma institucional de monitoramento automatizado de publicações
                em diários oficiais.
            </p>
            """,
            unsafe_allow_html=True,
        )

        # ── Seção: Fontes de pesquisa ─────────────────────────────────────────
        st.markdown(
            '<div class="sidebar-section-label">Diários Oficiais</div>',
            unsafe_allow_html=True,
        )

        # Card 1 — Diário Oficial da União
        with st.container(border=True):
            st.checkbox(
                "Diário Oficial da União",
                value=False,
                key="src_dou",
            )
            st.markdown(
                '<div class="sidebar-rule-text">'
                'Varredura na Seção 1 (Atos Normativos). Filtros: '
                'Organização "Ministério da Saúde" · Tipo "Portaria".'
                '</div>',
                unsafe_allow_html=True,
            )

        # Card 2 — Diário Oficial de Santa Catarina
        with st.container(border=True):
            st.checkbox(
                "Diário Oficial de Santa Catarina",
                value=False,
                key="src_doesc",
            )
            st.markdown(
                '<div class="sidebar-rule-text">'
                'Edições Ordinárias e Extras. Filtros: Categoria "Saúde" · '
                'Assuntos iniciados por "PORTARIA" · Município = Joinville.'
                '</div>',
                unsafe_allow_html=True,
            )

        # Card 3 — Diário Oficial de Joinville
        with st.container(border=True):
            st.checkbox(
                "Diário Oficial de Joinville",
                value=False,
                key="src_doej",
            )
            st.markdown(
                '<div class="sidebar-rule-text">'
                'Módulo em desenvolvimento.'
                ' <span class="sidebar-badge-dev">EM BREVE</span>'
                '</div>',
                unsafe_allow_html=True,
            )

        # ── Easter Egg da Barbara ─────────────────────────────────────────────
        st.markdown("<div style='margin-top: 0.5rem;'></div>", unsafe_allow_html=True)

        if st.button(
            "NÃO CLIQUE, BARBARA 😂",
            key="btn_barbara",
            use_container_width=True,
        ):
            st.balloons()
            _mostrar_surpresa()

        if not hasattr(st, "dialog") and st.session_state.get("show_barbara", False):
            with st.container(border=True):
                st.subheader("Surpresa!")
                st.image("assets/foto_barbara.png", use_container_width=True)
                if st.button("Fechar", key="close_barbara"):
                    st.session_state["show_barbara"] = False
                    st.rerun()

        # ── Rodapé institucional ──────────────────────────────────────────────
        st.markdown("<hr style='border-color:#e2e8f0; margin:1rem 0 0.75rem;'>", unsafe_allow_html=True)

        st.markdown(
            """
            <div class="sidebar-footer-text">
                <strong>Secretaria Municipal de Saúde</strong><br>
                Joinville · Unidade de Convênios e Parcerias
            </div>
            """,
            unsafe_allow_html=True,
        )