import streamlit as st

if hasattr(st, "dialog"):
    @st.dialog("Surpresa!")
    def mostrar_surpresa():
        st.image("assets/foto_barbara.png", use_container_width=True)
        if st.button("Fechar"):
            st.rerun()
else:
    def mostrar_surpresa():
        st.session_state["show_barbara"] = True

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
        Plataforma institucional para monitoramento automatizado de publicações governamentais.
        """)

        st.divider()
        st.markdown("### Diários Oficiais")

        # Card 1: Diário Oficial da União (inicia desmarcado - value=False)
        with st.container(border=True):
            st.checkbox(
                "Diário Oficial da União",
                value=False,
                key="src_dou",
                help="Selecionar Diário Oficial da União para busca"
            )
            st.caption('Regra: Varredura na Seção 1 (Atos Normativos) e Edições Extras. Filtros aplicados diretamente no portal: Organização "Ministério da Saúde" e Tipo de Ato "Portaria".')

        # Card 2: Diário Oficial de Santa Catarina (inicia desmarcado - value=False)
        with st.container(border=True):
            st.checkbox(
                "Diário Oficial de Santa Catarina",
                value=False,
                key="src_doesc",
                help="Selecionar Diário Oficial de Santa Catarina para busca"
            )
            st.caption('Regra: Varredura automatizada em Edições Ordinárias e Extras. Filtros internos aplicados: Categoria "Secretarias de Estado / Saúde" e assunto todos que começam com "PORTARIA". Extração do texto integral com filtro para Município = Joinville.')

        # Card 3: Diário Oficial de Joinville (inicia desmarcado - value=False)
        with st.container(border=True):
            st.checkbox(
                "Diário Oficial de Joinville",
                value=False,
                key="src_doej",
                help="Módulo do Diário Oficial de Joinville em desenvolvimento"
            )
            st.caption('Regra: Varredura nos atos do município de Joinville. (Em desenvolvimento).')

        # Easter Egg da Barbara
        st.divider()
        if st.button("NÃO CLIQUE, BARBARA 😂", key="btn_barbara", use_container_width=True):
            st.balloons()
            mostrar_surpresa()

        if not hasattr(st, "dialog") and st.session_state.get("show_barbara", False):
            with st.container(border=True):
                st.subheader("Surpresa!")
                st.image("assets/foto_barbara.png", use_container_width=True)
                if st.button("Fechar", key="close_barbara"):
                    st.session_state["show_barbara"] = False
                    st.rerun()

        st.divider()

        st.markdown("""
        **Secretaria Municipal de Saúde de Joinville**  
        Unidade de Convênios e Parcerias
        """)