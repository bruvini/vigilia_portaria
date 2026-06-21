"""Testes do relatório HTML para e-mail."""

from datetime import date

from vigilia_core.relatorio import detectar_urgencia, gerar_relatorio_html


def _registro(origem="DOU", titulo="Portaria X"):
    return {
        "origem": origem,
        "titulo": titulo,
        "link": "https://in.gov.br/x",
        "descricao": "corpo do ato",
        "resumo": "",
        "hierarquia": "MS/Gabinete",
    }


def test_relatorio_com_resultados():
    assunto, corpo = gerar_relatorio_html(
        [_registro(), _registro("DOE-SC", "Portaria Y")],
        date(2026, 6, 9),
        ["saúde"],
    )
    assert "2 publicação(ões)" in assunto or "09/06/2026" in assunto
    assert "Diário Oficial da União" in corpo
    assert "Diário Oficial de Santa Catarina" in corpo
    assert "Portaria X" in corpo
    assert "saúde" in corpo


def test_relatorio_vazio_nada_consta():
    assunto, corpo = gerar_relatorio_html([], date(2026, 6, 9), ["termo"])
    assert "0 publicação(ões)" in assunto
    assert "Nada consta" in corpo


def test_relatorio_escapa_html_malicioso():
    registro = _registro(titulo="<script>alert(1)</script>")
    _, corpo = gerar_relatorio_html([registro], date(2026, 6, 9), [])
    assert "<script>" not in corpo
    assert "&lt;script&gt;" in corpo


# ---------------------------------------------------------------------------
# Urgência
# ---------------------------------------------------------------------------

_PANORAMA_CRITICO = (
    "✦ **Vigília IA · Análise de Impacto**\n"
    "## 📊 Panorama do Dia\n"
    "* 🔴 Crítico | **Volume:** 3 atos relevantes (de 40 publicações varridas).\n"
    "* **Foco Principal:** repasse emergencial de R$ 1.200.000,00 para Joinville."
)

_PANORAMA_MODERADO = (
    "## 📊 Panorama do Dia\n"
    "* 🟡 Moderado | **Volume:** 2 atos.\n"
)

_PANORAMA_BAIXO = (
    "## 📊 Panorama do Dia\n"
    "* 🟢 Baixo | **Volume:** 1 ato.\n"
)


def test_detectar_urgencia_critico():
    assert detectar_urgencia(_PANORAMA_CRITICO) == "critico"


def test_detectar_urgencia_moderado():
    assert detectar_urgencia(_PANORAMA_MODERADO) == "moderado"


def test_detectar_urgencia_baixo():
    assert detectar_urgencia(_PANORAMA_BAIXO) == "baixo"


def test_detectar_urgencia_sem_ia():
    assert detectar_urgencia(None) == "nenhum"
    assert detectar_urgencia("") == "nenhum"
    assert detectar_urgencia("Texto sem nível.") == "nenhum"


def test_relatorio_urgencia_critico_prefixo_no_assunto():
    assunto, corpo = gerar_relatorio_html(
        [_registro()], date(2026, 6, 9), ["saúde"], resumo_ia=_PANORAMA_CRITICO
    )
    assert assunto.startswith("⚠️ URGENTE:")
    assert "URGENTE" in corpo          # faixa de alerta no corpo do e-mail


def test_relatorio_urgencia_moderado_prefixo_no_assunto():
    assunto, corpo = gerar_relatorio_html(
        [_registro()], date(2026, 6, 9), ["saúde"], resumo_ia=_PANORAMA_MODERADO
    )
    assert assunto.startswith("⚡ Atenção:")
    assert "ATENÇÃO" in corpo


def test_relatorio_urgencia_baixo_assunto_padrao():
    assunto, corpo = gerar_relatorio_html(
        [_registro()], date(2026, 6, 9), ["saúde"], resumo_ia=_PANORAMA_BAIXO
    )
    assert assunto.startswith("Vigília ·")   # sem prefixo de urgência
    assert "URGENTE" not in corpo
    assert "ATENÇÃO" not in corpo


def test_relatorio_sem_ia_sem_faixa_alerta():
    assunto, corpo = gerar_relatorio_html([_registro()], date(2026, 6, 9), [])
    assert assunto.startswith("Vigília ·")
    assert "URGENTE" not in corpo
    assert "ATENÇÃO" not in corpo
