import streamlit as st

def render_sidebar():

    with st.sidebar:

        st.markdown("## Vigília")

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