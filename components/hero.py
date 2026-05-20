import streamlit as st
from pathlib import Path

def render_hero():
    banner_path = Path("assets/banner_vigilia.png")

    if not banner_path.exists():
        return

    st.markdown('<div class="hero-wrapper"><div class="hero-banner">', unsafe_allow_html=True)
    st.image(str(banner_path), use_container_width=True)
    st.markdown('</div></div>', unsafe_allow_html=True)