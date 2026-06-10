"""Testes da filtragem compartilhada (vigilia_core.filtros)."""

from vigilia_core.filtros import (
    SCHEMA_CAMPOS,
    filtrar_publicacoes,
    limpar_palavras,
    normalizar_operador,
    normalizar_registro,
    remover_acentos,
)


def _registro(**kwargs):
    return normalizar_registro({
        "origem": "DOU",
        "titulo": "PORTARIA sobre saúde",
        "descricao": "convênio com o município",
        **kwargs,
    })


def test_remover_acentos():
    assert remover_acentos("Saúde") == "saude"
    assert remover_acentos("CONVÊNIO") == "convenio"
    assert remover_acentos("ação líquida") == "acao liquida"
    assert remover_acentos(None) == ""


def test_busca_insensivel_a_acentos_nos_dois_sentidos():
    registros = [_registro()]
    # termo sem acento encontra texto acentuado (bug histórico do DOU)
    assert len(filtrar_publicacoes(registros, ["saude"], "OU")) == 1
    # termo acentuado encontra texto sem acento
    registros2 = [_registro(titulo="PORTARIA sobre saude")]
    assert len(filtrar_publicacoes(registros2, ["saúde"], "OU")) == 1


def test_operador_ou_e():
    registros = [_registro()]
    assert len(filtrar_publicacoes(registros, ["saúde", "inexistente"], "OU")) == 1
    assert len(filtrar_publicacoes(registros, ["saúde", "inexistente"], "E")) == 0
    assert len(filtrar_publicacoes(registros, ["saúde", "convênio"], "E")) == 1


def test_operador_invalido_vira_ou():
    assert normalizar_operador("XYZ") == "OU"
    assert normalizar_operador("") == "OU"
    assert normalizar_operador(None) == "OU"
    assert normalizar_operador(" e ") == "E"
    assert normalizar_operador("ou") == "OU"


def test_sem_palavras_retorna_tudo():
    registros = [_registro(), _registro(titulo="DECRETO qualquer")]
    assert len(filtrar_publicacoes(registros, [], "OU")) == 2
    assert len(filtrar_publicacoes(registros, None, "OU")) == 2
    assert len(filtrar_publicacoes(registros, ["  ", ""], "OU")) == 2


def test_palavras_encontradas_preenchidas():
    registros = [_registro()]
    filtrados = filtrar_publicacoes(registros, ["saúde", "convênio", "nada"], "OU")
    assert filtrados[0]["palavras_encontradas"] == ["saúde", "convênio"]


def test_limpar_palavras():
    assert limpar_palavras(["  a ", "", "b", None]) == ["a", "b"]
    assert limpar_palavras(None) == []


def test_normalizar_registro_completa_schema():
    registro = normalizar_registro({"titulo": "x"})
    assert set(registro.keys()) == set(SCHEMA_CAMPOS)
    # campos ausentes viram string vazia — nunca None/NaN (bug do "nan" nos cards)
    assert registro["resumo"] == ""
    assert registro["descricao"] == ""
    assert registro["palavras_encontradas"] == []
