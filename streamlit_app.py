"""
Vigília — interface Streamlit (execução local / legada).

A versão de produção é a SPA hospedada no Firebase Hosting
(https://vigiliasms.web.app) — ver README. Esta interface consome o mesmo
núcleo de varredura (functions/vigilia_core) e é mantida para uso local.
"""

import streamlit as st

from views.home import render_home
from utils.helpers import load_css

st.set_page_config(
    page_title="Vigília",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="collapsed",
)

load_css("styles/main.css")

render_home()
