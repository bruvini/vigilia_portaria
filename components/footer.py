import streamlit as st
import textwrap


def render_footer():
    st.markdown(textwrap.dedent("""\
        <style>
        .vigilia-footer {
            position: relative;
            margin-top: 5rem;
            padding: 2.8rem 1.5rem 2rem 1.5rem;
            border-radius: 28px 28px 0 0;
            overflow: hidden;
            background:
                linear-gradient(
                    145deg,
                    rgba(15, 23, 42, 0.98),
                    rgba(30, 41, 59, 0.96)
                );
            border-top: 1px solid rgba(56, 189, 248, 0.18);
            box-shadow: 0 -10px 40px rgba(15, 23, 42, 0.18);
            text-align: center;
        }

        .vigilia-footer::before {
            content: "";
            position: absolute;
            top: -180px;
            left: 50%;
            transform: translateX(-50%);
            width: 420px;
            height: 420px;
            background:
                radial-gradient(
                    circle,
                    rgba(14, 165, 233, 0.14),
                    transparent 72%
                );
            pointer-events: none;
        }

        .vigilia-footer-divider {
            width: 90px;
            height: 4px;
            margin: 0 auto 1.8rem auto;
            border: none;
            border-radius: 999px;
            background: linear-gradient(90deg, #0ea5e9, #38bdf8);
            box-shadow: 0 0 24px rgba(14, 165, 233, 0.35);
        }

        .vigilia-footer-brand {
            position: relative;
            z-index: 2;
            font-size: 1.15rem;
            font-weight: 800;
            color: #f8fafc;
            letter-spacing: 0.02em;
            margin-bottom: 0.9rem;
        }

        .vigilia-footer-highlight {
            color: #38bdf8;
        }

        .vigilia-footer-description {
            position: relative;
            z-index: 2;
            max-width: 760px;
            margin: 0 auto 1.8rem auto;
            color: #cbd5e1;
            font-size: 0.95rem;
            line-height: 1.8;
        }

        .vigilia-footer-grid {
            position: relative;
            z-index: 2;
            display: flex;
            justify-content: center;
            align-items: center;
            flex-wrap: wrap;
            gap: 0.8rem;
            margin-bottom: 1.6rem;
        }

        .vigilia-footer-chip {
            padding: 0.55rem 1rem;
            border-radius: 999px;
            background: rgba(15, 23, 42, 0.65);
            border: 1px solid rgba(148, 163, 184, 0.12);
            color: #cbd5e1;
            font-size: 0.82rem;
            font-weight: 600;
            backdrop-filter: blur(8px);
        }

        .vigilia-footer-bottom {
            position: relative;
            z-index: 2;
            padding-top: 1.2rem;
            border-top: 1px solid rgba(148, 163, 184, 0.08);
            color: #94a3b8;
            font-size: 0.82rem;
            line-height: 1.7;
        }

        .vigilia-footer-signature {
            color: #38bdf8;
            font-weight: 700;
        }

        @media (max-width: 768px) {
            .vigilia-footer {
                padding: 2.2rem 1rem 1.8rem 1rem;
            }
            .vigilia-footer-brand {
                font-size: 1rem;
            }
            .vigilia-footer-description {
                font-size: 0.9rem;
            }
            .vigilia-footer-grid {
                gap: 0.6rem;
            }
            .vigilia-footer-chip {
                width: 100%;
            }
        }
        </style>
        <div class="vigilia-footer">
        <hr class="vigilia-footer-divider">
        <div class="vigilia-footer-brand">
        <span class="vigilia-footer-highlight">Vigília</span>
        • Plataforma Institucional de Inteligência Regulatória
        </div>
        <div class="vigilia-footer-description">
        Sistema institucional desenvolvido para monitoramento automatizado
        de publicações oficiais, rastreamento estratégico de atos normativos
        e apoio à gestão pública em saúde.
        </div>
        <div class="vigilia-footer-grid">
        <div class="vigilia-footer-chip">Diário Oficial da União</div>
        <div class="vigilia-footer-chip">Diário Oficial de Santa Catarina</div>
        <div class="vigilia-footer-chip">Monitoramento Automatizado</div>
        <div class="vigilia-footer-chip">Inteligência Documental</div>
        </div>
        <div class="vigilia-footer-bottom">
        Secretaria Municipal da Saúde de Joinville
        <br>
        Desenvolvido por
        <span class="vigilia-footer-signature">Enf. Bruno Vinícius</span>
        </div>
        </div>"""), unsafe_allow_html=True)