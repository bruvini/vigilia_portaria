"""Testes da triagem e extração de texto completo do DOU (sem rede)."""

from vigilia_core import dou


def test_triagem_materia_saude():
    mat = {"hierarchyStr": "Ministério da Saúde/Gabinete do Ministro",
           "title": "Portaria X", "content": "texto qualquer"}
    assert dou._triagem_materia(mat) is True


def test_triagem_materia_joinville_na_previa():
    mat = {"hierarchyStr": "Ministério da Educação", "title": "Edital",
           "content": "repasse para o município de Joinville"}
    assert dou._triagem_materia(mat) is True


def test_triagem_materia_descartada():
    mat = {"hierarchyStr": "Ministério da Agricultura", "title": "Portaria",
           "content": "assunto sem relação"}
    assert dou._triagem_materia(mat) is False


def test_extrair_texto_artigo_div():
    html = "<html><body><div class='texto-dou'>Texto completo do ato com CACON.</div></body></html>"
    assert "CACON" in dou._extrair_texto_artigo(html)


def test_extrair_texto_artigo_fallback_params():
    html = (
        '<html><body><script id="params">'
        '{"jsonArray":[{"content":"<p>corpo via fallback</p>"}]}'
        "</script></body></html>"
    )
    assert "corpo via fallback" in dou._extrair_texto_artigo(html)


def test_extrair_texto_artigo_vazio():
    assert dou._extrair_texto_artigo("<html><body>nada</body></html>") == ""


def test_cache_texto_reaproveita(monkeypatch):
    dou._CACHE_TEXTO.clear()
    chamadas = {"n": 0}

    class FakeResp:
        status_code = 200
        text = "<div class='texto-dou'>conteúdo do ato</div>"

    def fake_requisitar(sessao, metodo, url, **kw):
        chamadas["n"] += 1
        return FakeResp()

    monkeypatch.setattr(dou, "requisitar", fake_requisitar)
    link = "https://www.in.gov.br/en/web/dou/-/portaria-1"
    t1 = dou._buscar_texto(None, link)
    t2 = dou._buscar_texto(None, link)   # deve vir do cache, sem nova requisição
    assert t1 == t2 == "conteúdo do ato"
    assert chamadas["n"] == 1
    dou._CACHE_TEXTO.clear()
