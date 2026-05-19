import streamlit as st
from pathlib import Path

def render_hero():

    banner_path = Path("assets/banner_vigilia.png")

    if not banner_path.exists():
        return

    col_l, col_c, col_r = st.columns([1, 1, 1])
    with col_c:
        st.markdown('<div class="hero-banner">', unsafe_allow_html=True)
        st.image(str(banner_path), use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)