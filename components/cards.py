import streamlit as st

# ---------------------------------------------------------------------------
# Ícones SVG
# ---------------------------------------------------------------------------

_ICON_INFO = """
<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22"
viewBox="0 0 24 24" fill="none" stroke="currentColor"
stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <circle cx="12" cy="12" r="10"></circle>
    <path d="M12 16v-4"></path>
    <path d="M12 8h.01"></path>
</svg>
"""

_ICON_DOC = """
<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22"
viewBox="0 0 24 24" fill="none" stroke="currentColor"
stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
    <polyline points="14 2 14 8 20 8"></polyline>
    <line x1="16" y1="13" x2="8" y2="13"></line>
    <line x1="16" y1="17" x2="8" y2="17"></line>
</svg>
"""

_ICON_SEARCH = """
<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18"
viewBox="0 0 24 24" fill="none" stroke="currentColor"
stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <circle cx="11" cy="11" r="8"></circle>
    <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
</svg>
"""

_ICON_SPARK = """
<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18"
viewBox="0 0 24 24" fill="none" stroke="currentColor"
stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <path d="M12 3L13.5 8.5L19 10L13.5 11.5L12 17L10.5 11.5L5 10L10.5 8.5L12 3Z"></path>
</svg>
"""

# ---------------------------------------------------------------------------
# CSS GLOBAL DOS CARDS
# ---------------------------------------------------------------------------

def _inject_cards_css():
    st.markdown("""
    <style>

    .vigilia-card {
        position: relative;
        overflow: hidden;

        background:
            linear-gradient(
                145deg,
                rgba(15, 23, 42, 0.92),
                rgba(30, 41, 59, 0.96)
            );

        border: 1px solid rgba(148, 163, 184, 0.12);

        border-radius: 24px;

        padding: 1.6rem;

        min-height: 250px;

        transition:
            transform 0.25s ease,
            border 0.25s ease,
            box-shadow 0.25s ease;

        backdrop-filter: blur(14px);

        box-shadow:
            0 10px 30px rgba(15, 23, 42, 0.25);
    }

    .vigilia-card:hover {
        transform: translateY(-4px);

        border: 1px solid rgba(14, 165, 233, 0.35);

        box-shadow:
            0 18px 40px rgba(14, 165, 233, 0.12);
    }

    .vigilia-card::before {
        content: "";

        position: absolute;

        top: -120px;
        right: -120px;

        width: 240px;
        height: 240px;

        background:
            radial-gradient(
                circle,
                rgba(14, 165, 233, 0.18),
                transparent 70%
            );

        pointer-events: none;
    }

    .vigilia-card-top {
        display: flex;
        align-items: center;
        justify-content: space-between;

        margin-bottom: 1.4rem;
    }

    .vigilia-card-icon {
        width: 54px;
        height: 54px;

        display: flex;
        align-items: center;
        justify-content: center;

        border-radius: 16px;

        background:
            linear-gradient(
                135deg,
                rgba(14, 165, 233, 0.22),
                rgba(59, 130, 246, 0.12)
            );

        color: #38bdf8;

        border: 1px solid rgba(56, 189, 248, 0.15);
    }

    .vigilia-card-badge {
        display: flex;
        align-items: center;
        gap: 0.4rem;

        padding: 0.4rem 0.75rem;

        border-radius: 999px;

        background: rgba(14, 165, 233, 0.08);

        border: 1px solid rgba(14, 165, 233, 0.18);

        color: #7dd3fc;

        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.06em;
        text-transform: uppercase;
    }

    .vigilia-card-title {
        color: #f8fafc;

        font-size: 1.15rem;
        font-weight: 700;

        margin-bottom: 0.85rem;

        line-height: 1.3;
    }

    .vigilia-card-description {
        color: #cbd5e1;

        font-size: 0.96rem;
        line-height: 1.75;

        margin-bottom: 1.5rem;
    }

    .vigilia-card-footer {
        display: flex;
        align-items: center;
        gap: 0.55rem;

        margin-top: auto;

        color: #38bdf8;

        font-size: 0.88rem;
        font-weight: 600;
    }

    .vigilia-card-divider {
        width: 100%;
        height: 1px;

        margin: 1rem 0 1.2rem 0;

        background:
            linear-gradient(
                90deg,
                rgba(14,165,233,0),
                rgba(14,165,233,0.22),
                rgba(14,165,233,0)
            );
    }

    </style>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# CARD — INSTRUÇÕES
# ---------------------------------------------------------------------------

def render_instruction_card():
    _inject_cards_css()

    st.markdown(f"""
    <div class="vigilia-card">

        <div class="vigilia-card-top">

            <div class="vigilia-card-icon">
                {_ICON_INFO}
            </div>

            <div class="vigilia-card-badge">
                {_ICON_SPARK}
                Guia rápido
            </div>

        </div>

        <div class="vigilia-card-title">
            Pesquisa Inteligente de Publicações
        </div>

        <div class="vigilia-card-description">
            Configure os filtros, escolha os diários oficiais desejados
            e utilize operadores <strong>E</strong> ou <strong>OU</strong>
            para refinar a varredura automatizada.

            <br><br>

            A plataforma identifica atos normativos, portarias,
            convênios, repasses e publicações estratégicas em tempo real.
        </div>

        <div class="vigilia-card-divider"></div>

        <div class="vigilia-card-footer">
            {_ICON_SEARCH}
            Monitoramento automatizado e rastreável
        </div>

    </div>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# CARD — CONTEÚDO
# ---------------------------------------------------------------------------

def render_content_card():
    _inject_cards_css()

    st.markdown(f"""
    <div class="vigilia-card">

        <div class="vigilia-card-top">

            <div class="vigilia-card-icon">
                {_ICON_DOC}
            </div>

            <div class="vigilia-card-badge">
                {_ICON_SPARK}
                Inteligência documental
            </div>

        </div>

        <div class="vigilia-card-title">
            Consolidação Automatizada de Resultados
        </div>

        <div class="vigilia-card-description">
            Visualize publicações oficiais em uma interface moderna,
            organizada e otimizada para análise institucional.

            <br><br>

            Os resultados são agrupados por origem, destacados por
            palavras-chave e apresentados com acesso direto à publicação oficial.
        </div>

        <div class="vigilia-card-divider"></div>

        <div class="vigilia-card-footer">
            {_ICON_SEARCH}
            Interface otimizada para análise regulatória
        </div>

    </div>
    """, unsafe_allow_html=True)