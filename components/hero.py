import streamlit as st
from pathlib import Path


<<<<<<< HEAD
import streamlit as st
from pathlib import Path
import base64


def _img_to_base64(path: Path) -> str:
    data = path.read_bytes()
    return base64.b64encode(data).decode()


=======
>>>>>>> 71695c9 (feat: implement DOU data scraper and integrate search page with filters)
def render_hero():

    banner_path = Path("assets/banner_vigilia.png")

    if not banner_path.exists():
        return

<<<<<<< HEAD
    banner_base64 = _img_to_base64(banner_path)

    st.markdown(f"""
    <style>

    .vigilia-hero-wrapper {{
        position: relative;
        margin-bottom: 2.8rem;
        border-radius: 34px;
        overflow: hidden;
=======
    st.markdown("""
    <style>

    .vigilia-hero-wrapper {
        position: relative;

        margin-bottom: 2.8rem;

        border-radius: 34px;

        overflow: hidden;

>>>>>>> 71695c9 (feat: implement DOU data scraper and integrate search page with filters)
        background:
            linear-gradient(
                145deg,
                rgba(15, 23, 42, 0.98),
                rgba(30, 41, 59, 0.96)
            );
<<<<<<< HEAD
=======

>>>>>>> 71695c9 (feat: implement DOU data scraper and integrate search page with filters)
        border:
            1px solid rgba(56, 189, 248, 0.14);

        box-shadow:
            0 25px 60px rgba(15, 23, 42, 0.32);

        isolation: isolate;
<<<<<<< HEAD
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

=======
    }

    .vigilia-hero-wrapper::before {
        content: "";

        position: absolute;

        top: -180px;
        right: -120px;

        width: 420px;
        height: 420px;

        background:
            radial-gradient(
                circle,
                rgba(14, 165, 233, 0.18),
                transparent 72%
            );

        pointer-events: none;

        z-index: 1;
    }

    .vigilia-hero-wrapper::after {
        content: "";

        position: absolute;

        bottom: -220px;
        left: -180px;

        width: 420px;
        height: 420px;

        background:
            radial-gradient(
                circle,
                rgba(59, 130, 246, 0.12),
                transparent 75%
            );

        pointer-events: none;

        z-index: 1;
    }

    .vigilia-hero-banner {
        position: relative;
        z-index: 2;

        overflow: hidden;

        border-radius: 34px;
    }

    .vigilia-hero-banner img {
        border-radius: 34px;

        transition:
            transform 0.5s ease,
            filter 0.5s ease;

        filter:
            saturate(1.05)
            contrast(1.02);
    }

    .vigilia-hero-banner:hover img {
        transform: scale(1.015);

        filter:
            saturate(1.08)
            contrast(1.04);
    }

    .vigilia-hero-overlay {
        position: absolute;

        inset: 0;

        z-index: 3;

>>>>>>> 71695c9 (feat: implement DOU data scraper and integrate search page with filters)
        display: flex;
        flex-direction: column;
        justify-content: flex-end;

<<<<<<< HEAD
        padding: 2.2rem 2.4rem;
=======
        padding:
            2.2rem
            2.4rem;
>>>>>>> 71695c9 (feat: implement DOU data scraper and integrate search page with filters)

        background:
            linear-gradient(
                to top,
                rgba(2, 6, 23, 0.82),
                rgba(2, 6, 23, 0.15),
                transparent
            );
<<<<<<< HEAD
    }}

    .vigilia-hero-badge {{
        width: fit-content;

=======

        pointer-events: none;
    }

    .vigilia-hero-badge {
        width: fit-content;

        display: flex;
        align-items: center;
        gap: 0.5rem;

        margin-bottom: 1rem;

>>>>>>> 71695c9 (feat: implement DOU data scraper and integrate search page with filters)
        padding:
            0.45rem
            0.9rem;

        border-radius: 999px;

        background:
            rgba(15, 23, 42, 0.68);

        border:
            1px solid rgba(56, 189, 248, 0.18);

<<<<<<< HEAD
=======
        backdrop-filter: blur(12px);

>>>>>>> 71695c9 (feat: implement DOU data scraper and integrate search page with filters)
        color: #7dd3fc;

        font-size: 0.76rem;
        font-weight: 700;

<<<<<<< HEAD
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

=======
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }

    .vigilia-hero-title {
        color: #f8fafc;

        font-size: 2.4rem;
        font-weight: 800;

        line-height: 1.1;

        margin-bottom: 0.8rem;

        text-shadow:
            0 4px 18px rgba(0,0,0,0.35);
    }

    .vigilia-hero-subtitle {
        max-width: 780px;

        color: rgba(241, 245, 249, 0.92);

        font-size: 1rem;
        line-height: 1.75;

        text-shadow:
            0 2px 12px rgba(0,0,0,0.28);
    }

    .vigilia-hero-highlight {
        color: #38bdf8;
        font-weight: 700;
    }

    @media (max-width: 768px) {

        .vigilia-hero-overlay {
            padding:
                1.4rem
                1.2rem;
        }

        .vigilia-hero-title {
            font-size: 1.6rem;
        }

        .vigilia-hero-subtitle {
            font-size: 0.92rem;
            line-height: 1.6;
        }

        .vigilia-hero-badge {
            font-size: 0.68rem;
        }
    }

    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="vigilia-hero-wrapper">

        <div class="vigilia-hero-banner">
    """, unsafe_allow_html=True)

    st.image(str(banner_path), use_container_width=True)

    st.markdown("""
>>>>>>> 71695c9 (feat: implement DOU data scraper and integrate search page with filters)
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
<<<<<<< HEAD
                    e monitoramento inteligente de atos normativos.
                </div>

            </div>

        </div>

=======
                    e monitoramento inteligente de atos normativos em
                    múltiplos diários oficiais.
                </div>

            </div>
        </div>
>>>>>>> 71695c9 (feat: implement DOU data scraper and integrate search page with filters)
    </div>
    """, unsafe_allow_html=True)