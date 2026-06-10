"""Testes do mapeamento e deduplicação do DOU (sem rede)."""

from vigilia_core.dou import _deduplicar_por_link, _limpar_html, _mapear_materia


def test_mapear_materia_completo():
    mat = {
        "urlTitle": "portaria-gm-ms-n-1",
        "hierarchyStr": "Ministério da Saúde/Gabinete do Ministro",
        "title": "PORTARIA GM/MS Nº 1",
        "artType": "Portaria",
        "content": "<p>Texto <b>oficial</b></p>",
    }
    registro = _mapear_materia(mat, "do1", "09/06/2026")
    assert registro["origem"] == "DOU"
    assert registro["secao"] == "DO1"
    assert registro["link"] == "https://www.in.gov.br/en/web/dou/-/portaria-gm-ms-n-1"
    assert registro["descricao"] == "Texto oficial"
    assert registro["data"] == "09/06/2026"
    assert registro["resumo"] == ""  # sempre presente como string


def test_mapear_materia_sem_url_title():
    registro = _mapear_materia({"title": "Ato X"}, "do2", "09/06/2026")
    assert registro["link"] == ""


def test_dedup_preserva_links_vazios():
    """Matérias sem urlTitle não são duplicatas entre si (bug histórico)."""
    registros = [
        {"titulo": "A", "link": ""},
        {"titulo": "B", "link": ""},
        {"titulo": "C", "link": "https://x/1"},
        {"titulo": "C-dup", "link": "https://x/1"},
    ]
    unicos = _deduplicar_por_link(registros)
    titulos = [r["titulo"] for r in unicos]
    assert titulos == ["A", "B", "C"]


def test_limpar_html():
    assert _limpar_html("<p>Olá <b>mundo</b></p>") == "Olá mundo"
    assert _limpar_html("") == ""
