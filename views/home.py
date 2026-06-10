"""
Página principal do Vigília (versão Streamlit — execução local/legada).

A versão de produção é a SPA hospedada no Firebase (vigiliasms.web.app);
esta interface consome o mesmo núcleo `functions/vigilia_core`.

Correções incorporadas (auditoria de 09/06/2026):
  - Sem pandas: trabalha com list[dict] no esquema padronizado do núcleo
    (elimina o bug do "nan" nos cards e o crash de pd.read_json no pandas 3).
  - Todo texto vindo dos diários é escapado com html.escape antes da
    renderização (anti-XSS, conforme SECURITY.md).
  - Destaque de palavras-chave em passada única (não corrompe mais o HTML
    quando um termo casa dentro da marcação inserida por outro).
  - Renderização limitada a um lote de cards por vez, com download CSV/FHIR
    do conjunto completo.
  - Seleção de fontes movida da sidebar para o painel de filtros.
"""

from __future__ import annotations

import csv
import html
import io
import json
import re
import sys
from datetime import date
from pathlib import Path

import streamlit as st

# O núcleo compartilhado mora em functions/ (única fonte de verdade,
# empacotada no deploy das Cloud Functions).
_FUNCTIONS_DIR = Path(__file__).resolve().parent.parent / "functions"
if str(_FUNCTIONS_DIR) not in sys.path:
    sys.path.insert(0, str(_FUNCTIONS_DIR))

from vigilia_core.config_padrao import OPERADOR_PADRAO, PALAVRAS_PADRAO  # noqa: E402
from vigilia_core.dou import buscar_dou_completo  # noqa: E402
from vigilia_core.doesc import buscar_doesc  # noqa: E402
from vigilia_core.fhir import (  # noqa: E402
    create_hl7_fhir_message_bundle,
    to_fhir_document_reference,
)

from components.hero import render_hero  # noqa: E402
from components.footer import render_footer  # noqa: E402

MAX_CARDS_POR_LOTE = 120

NOMES_FONTES = {
    "DOU": "Diário Oficial da União",
    "DOE-SC": "Diário Oficial de Santa Catarina",
    "DOE-JOI": "Diário Oficial de Joinville",
}

_ICON_FILTER = """
<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18"
viewBox="0 0 24 24" fill="none" stroke="currentColor"
stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"></polygon>
</svg>
"""

_ICON_RESULT = """
<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18"
viewBox="0 0 24 24" fill="none" stroke="currentColor"
stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
<polyline points="14 2 14 8 20 8"></polyline>
<line x1="16" y1="13" x2="8" y2="13"></line>
<line x1="16" y1="17" x2="8" y2="17"></line>
</svg>
"""


# -----------------------------------------------------------------------------
# Helpers de renderização segura
# -----------------------------------------------------------------------------

def _destacar_palavras(texto: str, palavras: list[str]) -> str:
    """
    Escapa o texto (anti-XSS) e destaca os termos em UMA passada.

    O split com grupo de captura alterna [texto, match, texto, match, ...]:
    índices ímpares são sempre termos encontrados — imune ao bug de um termo
    casar dentro do <mark> inserido por outro.
    """
    texto = str(texto or "")
    termos = [p for p in palavras if p and p.strip()]
    if not termos:
        return html.escape(texto)

    padrao = re.compile(
        "(" + "|".join(re.escape(p.strip()) for p in termos) + ")",
        re.IGNORECASE,
    )
    partes = padrao.split(texto)
    return "".join(
        f"<mark class='keyword-highlight'>{html.escape(parte)}</mark>"
        if i % 2 == 1
        else html.escape(parte)
        for i, parte in enumerate(partes)
    )


def _badge_origem(origem: str) -> str:
    cores = {
        "DOU": ("#DBEAFE", "#1D4ED8"),
        "DOE-SC": ("#DCFCE7", "#15803D"),
        "DOE-JOI": ("#FEF3C7", "#92400E"),
    }
    bg, cor = cores.get(origem, ("#E2E8F0", "#334155"))
    return (
        f"<span class='vigilia-badge' style='background:{bg}; color:{cor};'>"
        f"{html.escape(origem)}</span>"
    )


def _gerar_csv(registros: list[dict]) -> str:
    campos = ["origem", "secao", "data", "tipo", "orgao",
              "hierarquia", "titulo", "link", "descricao"]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=campos, delimiter=";",
                            extrasaction="ignore", quoting=csv.QUOTE_ALL)
    writer.writeheader()
    for r in registros:
        writer.writerow({c: str(r.get(c, "")).replace("\n", " ") for c in campos})
    return "﻿" + buffer.getvalue()  # BOM p/ Excel pt-BR


# -----------------------------------------------------------------------------
# Bundle FHIR (cacheado por conteúdo)
# -----------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def _build_fhir_bundle(registros_json: str) -> tuple[list, dict, str]:
    """
    Constrói o FHIR Bundle a partir dos registros serializados em JSON.
    A prévia exibe até 50 recursos; o download contém todos.
    """
    registros = json.loads(registros_json)
    recursos = [to_fhir_document_reference(r) for r in registros]
    bundle = create_hl7_fhir_message_bundle(recursos)
    bundle_json = json.dumps(bundle, indent=2, ensure_ascii=False)
    return recursos[:50], bundle, bundle_json


# -----------------------------------------------------------------------------
# Intro
# -----------------------------------------------------------------------------

def _render_intro() -> None:
    st.markdown(
        """<div class="vigilia-home-hero">
<div class="vigilia-home-badge">
Plataforma Institucional • Monitoramento Estratégico
</div>
<h1 class="vigilia-home-title">
Inteligência automatizada para monitoramento
de Diários Oficiais
</h1>
<p class="vigilia-home-description">
Centralize a busca, rastreie publicações relevantes em tempo real
e reduza o tempo operacional das equipes institucionais.
</p>
<div class="vigilia-home-stats">
<div class="vigilia-stat-card">
<div class="vigilia-stat-number">DOU</div>
<div class="vigilia-stat-label">União</div>
</div>
<div class="vigilia-stat-card">
<div class="vigilia-stat-number">DOE</div>
<div class="vigilia-stat-label">Santa Catarina</div>
</div>
<div class="vigilia-stat-card">
<div class="vigilia-stat-number">24h</div>
<div class="vigilia-stat-label">Monitoramento</div>
</div>
</div>
</div>""",
        unsafe_allow_html=True,
    )


# -----------------------------------------------------------------------------
# Filtros (inclui seleção de fontes — a sidebar foi removida)
# -----------------------------------------------------------------------------

def _render_filtros() -> dict:
    st.markdown(
        f"""<div class="vigilia-section-header">
<div class="vigilia-section-icon">
{_ICON_FILTER}
</div>
<div>
<div class="vigilia-section-title">
Filtros da Varredura
</div>
<div class="vigilia-section-subtitle">
Configure os parâmetros utilizados na pesquisa automatizada.
</div>
</div>
</div>""",
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        col1, col2 = st.columns([1, 2])

        with col1:
            data_pub = st.date_input(
                "Data da publicação",
                value=date.today(),
                format="DD/MM/YYYY",
                help="Selecione a edição do Diário Oficial.",
            )

        with col2:
            palavras_raw = st.text_input(
                "Palavras-chave",
                value=", ".join(PALAVRAS_PADRAO),
                placeholder="Ex: convênio, incentivo, financiamento...",
                help="Separe múltiplos termos utilizando vírgula. "
                     "Os termos padrão podem ser ajustados em "
                     "functions/vigilia_core/config_padrao.py.",
            )

        col_op, col_fontes = st.columns([1, 2])

        with col_op:
            operador = st.radio(
                "Operador lógico",
                options=["OU", "E"],
                index=0 if OPERADOR_PADRAO == "OU" else 1,
                horizontal=True,
                help=(
                    "OU → retorna publicações contendo qualquer termo.\n"
                    "E → retorna apenas publicações contendo TODOS os termos."
                ),
            )

        with col_fontes:
            st.markdown("**Fontes monitoradas**")
            c1, c2, c3 = st.columns(3)
            with c1:
                src_dou = st.checkbox("DOU", value=True, key="src_dou",
                                      help="Diário Oficial da União — Seções 1, 2 e 3, "
                                           "filtrado para o Ministério da Saúde.")
            with c2:
                src_doesc = st.checkbox("DOE-SC", value=True, key="src_doesc",
                                        help="Diário Oficial de Santa Catarina — "
                                             "todas as publicações do dia.")
            with c3:
                st.checkbox("DOE-JOI", value=False, disabled=True, key="src_doej",
                            help="Diário Oficial de Joinville — em desenvolvimento.")

    return {
        "data": data_pub,
        "palavras": [p.strip() for p in palavras_raw.split(",") if p.strip()],
        "operador": operador,
        "fontes": {"dou": src_dou, "doesc": src_doesc},
    }


# -----------------------------------------------------------------------------
# Execução da varredura
# -----------------------------------------------------------------------------

def _executar_varredura(filtros: dict) -> list[dict]:
    registros: list[dict] = []
    data = filtros["data"]
    palavras = filtros["palavras"]
    operador = filtros["operador"]

    if filtros["fontes"]["dou"]:
        with st.status("Varrendo Diário Oficial da União (Seções 1, 2 e 3)...",
                       expanded=False):
            try:
                encontrados = buscar_dou_completo(data, palavras, operador)
                registros.extend(encontrados)
                por_secao: dict[str, int] = {}
                for r in encontrados:
                    por_secao[r["secao"]] = por_secao.get(r["secao"], 0) + 1
                detalhe = " | ".join(f"{s}: {n}" for s, n in sorted(por_secao.items()))
                st.write(
                    f"{len(encontrados)} publicação(ões) encontradas no DOU"
                    f"{f' ({detalhe})' if detalhe else ''}."
                )
            except Exception as e:
                st.error(f"Erro ao acessar o DOU: {e}")

    if filtros["fontes"]["doesc"]:
        with st.status("Varrendo Diário Oficial de Santa Catarina...", expanded=False):
            try:
                encontrados = buscar_doesc(data, palavras, operador)
                registros.extend(encontrados)
                st.write(f"{len(encontrados)} publicação(ões) encontradas no DOE-SC.")
            except Exception as e:
                st.error(f"Erro ao acessar o DOE-SC: {e}")

    return registros


# -----------------------------------------------------------------------------
# Resultados
# -----------------------------------------------------------------------------

def _render_resultados(registros: list[dict], palavras_chave: list[str]) -> None:
    st.markdown(
        f"""<div class="vigilia-results-header">
<div class="vigilia-section-header">
<div class="vigilia-section-icon">
{_ICON_RESULT}
</div>
<div>
<div class="vigilia-section-title">
Resultados Encontrados
</div>
<div class="vigilia-section-subtitle">
Publicações identificadas na varredura institucional.
</div>
</div>
</div>
</div>""",
        unsafe_allow_html=True,
    )

    if not registros:
        st.markdown(
            """<div class="vigilia-empty-state">
<div>
<div class="vigilia-empty-title">
Nada consta
</div>
<div class="vigilia-empty-text">
Ajuste os filtros ou revise as palavras-chave utilizadas.
</div>
</div>
</div>""",
            unsafe_allow_html=True,
        )
        return

    st.markdown(
        f"""<div class="vigilia-results-counter">
{len(registros)} publicação(ões) encontrada(s)
</div>""",
        unsafe_allow_html=True,
    )

    col_csv, _ = st.columns([1, 3])
    with col_csv:
        st.download_button(
            "📄 Baixar resultados (CSV)",
            data=_gerar_csv(registros),
            file_name=f"vigilia_resultados_{date.today().strftime('%d-%m-%Y')}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    ordem = {"DOU": 0, "DOE-SC": 1, "DOE-JOI": 2}
    origens = sorted(
        {r["origem"] for r in registros},
        key=lambda o: ordem.get(o, 9),
    )

    exibidos = 0
    truncado = False
    for idx_grp, origem in enumerate(origens):
        if idx_grp > 0:
            st.markdown("<div style='height: 1rem'></div>", unsafe_allow_html=True)

        grupo = [r for r in registros if r["origem"] == origem]
        st.markdown(
            f"""<div class="vigilia-group-title">
{html.escape(NOMES_FONTES.get(origem, origem))} • {len(grupo)}
</div>""",
            unsafe_allow_html=True,
        )

        for registro in grupo:
            if exibidos >= MAX_CARDS_POR_LOTE:
                truncado = True
                break
            _render_card(registro, palavras_chave)
            exibidos += 1
        if truncado:
            break

    if truncado:
        st.info(
            f"Exibindo os primeiros {MAX_CARDS_POR_LOTE} resultados para manter a "
            f"página responsiva. O arquivo CSV acima contém todos os "
            f"{len(registros)} registros."
        )

    _render_painel_fhir(registros)


def _render_card(registro: dict, palavras_chave: list[str]) -> None:
    titulo = _destacar_palavras(registro.get("titulo", ""), palavras_chave)
    corpo_texto = registro.get("resumo") or registro.get("descricao") or ""
    corpo = _destacar_palavras(corpo_texto[:1200], palavras_chave)
    hierarquia = html.escape(str(registro.get("hierarquia", "")))
    data_pub = html.escape(str(registro.get("data", "")))
    origem = str(registro.get("origem", "DOU"))
    link = str(registro.get("link", ""))
    link_seguro = html.escape(link, quote=True)

    titulo_html = (
        f"<a href=\"{link_seguro}\" target=\"_blank\" rel=\"noopener noreferrer\">{titulo}</a>"
        if link.startswith("http")
        else titulo
    )
    botao_html = (
        f"""<div class="vigilia-result-actions">
<a href="{link_seguro}" target="_blank" rel="noopener noreferrer" class="vigilia-result-button">
Acessar publicação oficial
</a>
</div>"""
        if link.startswith("http")
        else ""
    )

    st.markdown(
        f"""<div class="vigilia-result-card">
<div class="vigilia-result-top">
<div class="vigilia-result-hierarchy">
{hierarquia}
</div>
<div class="vigilia-result-date">
{data_pub}
{_badge_origem(origem)}
</div>
</div>
<div class="vigilia-result-title">
{titulo_html}
</div>
<div class="vigilia-result-description">
{corpo}
</div>
{botao_html}
</div>""",
        unsafe_allow_html=True,
    )


def _render_painel_fhir(registros: list[dict]) -> None:
    st.markdown("<div style='height: 1.5rem'></div>", unsafe_allow_html=True)
    with st.expander("🔗 Interoperabilidade de Saúde (FHIR & HL7 / Messaging)"):
        st.markdown(
            """<div style="font-size:0.9rem; color:#475569; margin-bottom:0.8rem; line-height:1.7;">
Os atos normativos extraídos são estruturados como recursos
<strong>FHIR DocumentReference</strong> (R4) e encapsulados em um
<strong>FHIR Message Bundle</strong> (HL7) para futura integração com
barramentos de saúde do SUS e do PEP municipal.
A prévia exibe até 50 registros; o arquivo de download contém todos.
</div>""",
            unsafe_allow_html=True,
        )
        try:
            registros_json = json.dumps(registros, ensure_ascii=False, sort_keys=True)
            fhir_preview, bundle, bundle_json = _build_fhir_bundle(registros_json)
            if fhir_preview:
                col_left, col_right = st.columns(2)
                with col_left:
                    st.markdown("##### Exemplo: FHIR DocumentReference (1º Recurso)")
                    st.json(fhir_preview[0])
                with col_right:
                    st.markdown("##### Estrutura: FHIR Message Bundle (HL7)")
                    st.json({
                        "resourceType": bundle["resourceType"],
                        "id": bundle["id"],
                        "type": bundle["type"],
                        "timestamp": bundle["timestamp"],
                        "total_entries": len(bundle["entry"]),
                        "message_header": bundle["entry"][0]["resource"],
                    })
            st.download_button(
                label="📥 Baixar FHIR Bundle Completo (JSON)",
                data=bundle_json,
                file_name=f"vigilia_fhir_bundle_{date.today().strftime('%d-%m-%Y')}.json",
                mime="application/fhir+json",
                use_container_width=True,
            )
        except Exception as e:
            st.warning(
                f"⚠️ Não foi possível gerar o mapeamento FHIR: {e}\n\n"
                "Os resultados da busca acima não foram afetados."
            )


# -----------------------------------------------------------------------------
# Página principal
# -----------------------------------------------------------------------------

def render_home() -> None:
    render_hero()
    _render_intro()

    st.markdown("<div style='height: 1rem'></div>", unsafe_allow_html=True)
    filtros = _render_filtros()
    st.markdown("<div style='height: 1rem'></div>", unsafe_allow_html=True)

    iniciar = st.button(
        "Iniciar Varredura",
        type="primary",
        key="btn_busca",
        use_container_width=True,
    )

    if iniciar:
        if not filtros["fontes"]["dou"] and not filtros["fontes"]["doesc"]:
            st.warning("Selecione pelo menos um Diário Oficial para realizar a busca.")
            st.stop()

        if not filtros["palavras"]:
            st.warning(
                "Nenhuma palavra-chave informada. A varredura retornará "
                "todas as publicações do Ministério da Saúde no DOU e todas "
                "as publicações do dia no DOE-SC, o que pode gerar muitos resultados."
            )

        st.session_state["resultados"] = _executar_varredura(filtros)
        st.session_state["palavras_busca"] = filtros["palavras"]

    if st.session_state.get("resultados") is not None:
        st.markdown("<div style='height: 2rem'></div>", unsafe_allow_html=True)
        _render_resultados(
            st.session_state["resultados"],
            st.session_state.get("palavras_busca", []),
        )

    render_footer()
