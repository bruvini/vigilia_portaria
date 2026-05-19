import streamlit as st

from pages.home import render_home
from components.sidebar import render_sidebar
from utils.helpers import load_css

# -----------------------------------------------------------------------------
# CONFIGURAÇÃO

st.set_page_config(
    page_title="Vigília",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -----------------------------------------------------------------------------
# CSS

load_css("styles/main.css")

# -----------------------------------------------------------------------------
# SIDEBAR

render_sidebar()

# -----------------------------------------------------------------------------
# HOME

render_home()