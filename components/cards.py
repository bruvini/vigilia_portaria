import streamlit as st

def render_instruction_card():
    st.markdown("""
    <div class="custom-card">
        <div class="card-header">
            <div class="card-icon">
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="12" cy="12" r="10"></circle>
                    <path d="M12 16v-4"></path>
                    <path d="M12 8h.01"></path>
                </svg>
            </div>
            <div class="card-title">
                Instruções de Uso
            </div>
        </div>
        <div class="card-text">
            Nesta área, você encontra as orientações operacionais detalhadas para realizar a pesquisa e extração de dados normativos de forma eficiente.
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_content_card():
    st.markdown("""
    <div class="custom-card">
        <div class="card-header">
            <div class="card-icon">
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                    <polyline points="14 2 14 8 20 8"></polyline>
                    <line x1="16" y1="13" x2="8" y2="13"></line>
                    <line x1="16" y1="17" x2="8" y2="17"></line>
                    <polyline points="10 9 9 9 8 9"></polyline>
                </svg>
            </div>
            <div class="card-title">
                Área de Conteúdo
            </div>
        </div>
        <div class="card-text">
            Este módulo é responsável pela exibição dos relatórios consolidados e documentos extraídos das publicações oficiais recentes.
        </div>
    </div>
    """, unsafe_allow_html=True)