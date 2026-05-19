import streamlit as st

def render_instruction_card():

    st.markdown("""
    <div class="custom-card">

        <div class="card-title">
            Instruções de Uso
        </div>

        <div class="card-text">

        Espaço reservado para orientações operacionais da plataforma.

        </div>

    </div>
    """, unsafe_allow_html=True)


def render_content_card():

    st.markdown("""
    <div class="custom-card">

        <div class="card-title">
            Área de Conteúdo
        </div>

        <div class="card-text">

        Espaço reservado para os módulos e relatórios do sistema.

        </div>

    </div>
    """, unsafe_allow_html=True)