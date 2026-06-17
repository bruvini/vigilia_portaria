"""Testes do relatório HTML para e-mail."""

from datetime import date

from vigilia_core.relatorio import gerar_relatorio_html


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
