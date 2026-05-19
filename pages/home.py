import streamlit as st

from components.hero import render_hero
from components.cards import (
    render_instruction_card,
    render_content_card
)
from components.footer import render_footer

def render_home():

    render_hero()

    st.markdown("""
    # Plataforma Vigília

    Sistema institucional de inteligência e monitoramento automatizado
    de publicações oficiais.
    """)

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        render_instruction_card()

    with col2:
        render_content_card()

    render_footer()