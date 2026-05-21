import streamlit as st
from pathlib import Path


import streamlit as st
from pathlib import Path
import base64


def _img_to_base64(path: Path) -> str:
    data = path.read_bytes()
    return base64.b64encode(data).decode()


def render_hero():

    banner_path = Path("assets/banner_vigilia.png")

    if not banner_path.exists():
        return

    banner_base64 = _img_to_base64(banner_path)

    st.markdown(f"""
    <style>

    .vigilia-hero-wrapper {{
        position: relative;
        margin-bottom: 2.8rem;
        border-radius: 34px;
        overflow: hidden;
        background:
            linear-gradient(
                145deg,
                rgba(15, 23, 42, 0.98),
                rgba(30, 41, 59, 0.96)
            );
        border:
            1px solid rgba(56, 189, 248, 0.14);

        box-shadow:
            0 25px 60px rgba(15, 23, 42, 0.32);

        isolation: isolate;
    }}

    .vigilia-hero-banner {{
        position: relative;
        overflow: hidden;
        border-radius: 34px;
    }}

    .vigilia-hero-banner img {{
        width: 100%;
        display: block;
        border-radius: 34px;
    }}

    .vigilia-hero-overlay {{
        position: absolute;
        inset: 0;

        display: flex;
        flex-direction: column;
        justify-content: flex-end;

        padding: 2.2rem 2.4rem;

        background:
            linear-gradient(
                to top,
                rgba(2, 6, 23, 0.82),
                rgba(2, 6, 23, 0.15),
                transparent
            );
    }}

    .vigilia-hero-badge {{
        width: fit-content;

        padding:
            0.45rem
            0.9rem;

        border-radius: 999px;

        background:
            rgba(15, 23, 42, 0.68);

        border:
            1px solid rgba(56, 189, 248, 0.18);

        color: #7dd3fc;

        font-size: 0.76rem;
        font-weight: 700;

        margin-bottom: 1rem;
    }}

    .vigilia-hero-title {{
        color: white;
        font-size: 2.4rem;
        font-weight: 800;
        margin-bottom: 0.8rem;
    }}

    .vigilia-hero-subtitle {{
        color: rgba(241,245,249,0.92);
        max-width: 780px;
        line-height: 1.7;
    }}

    </style>

    <div class="vigilia-hero-wrapper">

        <div class="vigilia-hero-banner">

            <img src="data:image/png;base64,{banner_base64}">

            <div class="vigilia-hero-overlay">

                <div class="vigilia-hero-badge">
                    Inteligência Regulatória • Monitoramento Automatizado
                </div>

                <div class="vigilia-hero-title">
                    Plataforma Vigília
                </div>

                <div class="vigilia-hero-subtitle">
                    Sistema institucional de rastreamento estratégico de
                    publicações oficiais, análise documental automatizada
                    e monitoramento inteligente de atos normativos.
                </div>

            </div>

        </div>

    </div>
    """, unsafe_allow_html=True)