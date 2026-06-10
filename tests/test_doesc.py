"""Testes do mapeamento do DOE-SC (sem rede)."""

from vigilia_core.doesc import _mapear_materia, extrair_tipo


def test_extrair_tipo():
    assert extrair_tipo("PORTARIA 123", "") == "PORTARIA"
    assert extrair_tipo("portaria nº 9", "") == "PORTARIA"
    assert extrair_tipo("", "RESOLUÇÃO 9") == "RESOLUÇÃO"
    assert extrair_tipo("texto qualquer", "outro texto") == "ATO"
    assert extrair_tipo("", "") == "ATO"


def test_mapear_materia_link_extrato():
    mat = {"resumo": "Portaria nº 1\nCorpo do texto", "assunto": "PESSOAL",
           "categoria": "SAÚDE", "extrato": "https://doe/extrato/1"}
    registro = _mapear_materia(mat, "09/06/2026")
    assert registro["link"] == "https://doe/extrato/1"
    assert registro["titulo"] == "Portaria nº 1"
    assert registro["tipo"] == "PORTARIA"
    assert registro["origem"] == "DOE-SC"


def test_mapear_materia_link_construido():
    mat = {"resumo": "Ato Y", "assunto": "", "categoria": "",
           "cdJornal": 99, "id": 1234}
    registro = _mapear_materia(mat, "09/06/2026")
    assert registro["link"].endswith("/portal/edicao/99/materia/1234")
    assert registro["orgao"] == "Estado de Santa Catarina"


def test_mapear_materia_titulo_longo_truncado():
    mat = {"resumo": "X" * 300, "assunto": "", "categoria": ""}
    registro = _mapear_materia(mat, "09/06/2026")
    assert len(registro["titulo"]) == 200
    assert registro["titulo"].endswith("...")
