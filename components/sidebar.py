import streamlit as st

def render_sidebar():
    with st.sidebar:
        st.markdown("""
        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 20px;">
            <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#0ea5e9" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
            </svg>
            <h2 style="margin: 0; padding: 0; font-size: 1.5rem; color: #0f172a;">Vigília</h2>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        Plataforma institucional para monitoramento automatizado de:

        - Atos oficiais
        - Portarias
        - Convênios
        - Regulamentações
        - Publicações governamentais
        """)

        st.divider()

        st.markdown("""
        **Secretaria Municipal de Saúde de Joinville**  
        Unidade de Convênios e Parcerias
        """)