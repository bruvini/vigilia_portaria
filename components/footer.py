import streamlit as st


def render_footer():
    st.markdown(
        """
        <div class="vigilia-footer">
            <hr class="vigilia-footer-divider">
            <div class="vigilia-footer-brand">
                Vigília &nbsp;•&nbsp; Plataforma Institucional de Monitoramento Estratégico
            </div>
            <div class="vigilia-footer-sub">
                Secretaria Municipal de Saúde de Joinville
            </div>
            <div class="vigilia-footer-sub">
                Desenvolvido por Enf. Bruno Vinícius
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )