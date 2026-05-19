import streamlit as st
from pathlib import Path

def render_hero():

    banner_path = Path("assets/banner_vigilia.png")

    st.markdown(
        '<div class="hero-banner">',
        unsafe_allow_html=True
    )

    st.image(
        str(banner_path),
        use_container_width=True
    )

    st.markdown(
        '</div>',
        unsafe_allow_html=True
    )