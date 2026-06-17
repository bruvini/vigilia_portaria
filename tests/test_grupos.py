"""Testes do modelo de kits (DNF) e do filtro de ruído."""

from vigilia_core.filtros import (
    eh_ruido,
    filtrar_por_grupos,
    grupos_de_legado,
    grupos_para_termos,
    limpar_grupos,
    normalizar_registro,
)


def _reg(titulo="", descricao="", hierarquia="", orgao=""):
    return normalizar_registro({
        "origem": "DOU", "titulo": titulo, "descricao": descricao,
        "hierarquia": hierarquia, "orgao": orgao,
    })


def test_limpar_grupos():
    assert limpar_grupos([["a", " "], [], ["b", "c"]]) == [["a"], ["b", "c"]]
    assert limpar_grupos(None) == []
    assert limpar_grupos(["x"]) == []  # item não-lista é ignorado


def test_grupos_de_legado():
    assert grupos_de_legado(["a", "b"], "E") == [["a", "b"]]
    assert grupos_de_legado(["a", "b"], "OU") == [["a"], ["b"]]
    assert grupos_de_legado([], "E") == []


def test_grupos_para_termos():
    assert grupos_para_termos([["Joinville", "saúde"], ["Joinville", "oncologia"]]) == \
        ["Joinville", "saúde", "oncologia"]


def test_kit_e_interno_ou_entre_kits():
    regs = [
        _reg(titulo="Hospital São José em Joinville"),   # casa kit 1
        _reg(titulo="Oncologia em Joinville"),           # casa kit 2
        _reg(titulo="Joinville apenas"),                 # casa kit 3
        _reg(titulo="Hospital São José em Curitiba"),    # não casa nenhum
    ]
    grupos = [["Joinville", "Hospital São José"], ["Joinville", "Oncologia"], ["Joinville"]]
    out = filtrar_por_grupos(regs, grupos)
    assert len(out) == 3
    assert all("Joinville" in r["palavras_encontradas"] for r in out)


def test_kit_insensivel_acento_e_caixa():
    regs = [_reg(titulo="PORTARIA sobre SAÚDE em JOINVILLE")]
    # termos sem acento e minúsculos devem casar
    assert len(filtrar_por_grupos(regs, [["joinville", "saude"]])) == 1


def test_kit_frase_multipalavra():
    regs = [_reg(descricao="habilitação no programa Agora Tem Especialistas para Joinville")]
    assert len(filtrar_por_grupos(regs, [["Joinville", "Agora Tem Especialistas"]])) == 1
    # frase incompleta não casa
    assert len(filtrar_por_grupos(regs, [["Joinville", "Agora Tem Cardiologistas"]])) == 0


def test_sem_grupos_retorna_tudo_menos_ruido():
    regs = [_reg(titulo="Portaria de saúde"), _reg(orgao="DETRAN", titulo="Edital")]
    out = filtrar_por_grupos(regs, [])
    assert len(out) == 1  # o do DETRAN é ruído


def test_filtro_ruido():
    assert eh_ruido(_reg(orgao="DETRAN", titulo="Edital de notificação")) is True
    assert eh_ruido(_reg(hierarquia="DOE-SC › Leilão", titulo="Edital de leilão")) is True
    assert eh_ruido(_reg(titulo="Portaria de habilitação de leitos")) is False
    # ruído não derruba ato de saúde que só CITE o termo no corpo
    assert eh_ruido(_reg(titulo="Portaria de saúde",
                         descricao="menciona infração de trânsito")) is False


def test_ruido_excluido_mesmo_casando_kit():
    # edital do DETRAN que contém "Joinville" no corpo NÃO deve passar
    reg = _reg(orgao="DETRAN", hierarquia="DOE-SC › DETRAN › EDITAL",
               titulo="Suspensão do direito de dirigir",
               descricao="notificação para condutores de Joinville")
    assert filtrar_por_grupos([reg], [["Joinville"]]) == []
