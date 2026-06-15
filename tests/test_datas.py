"""Testes da lógica de dia útil anterior (relatório das 07h)."""

from datetime import date

from vigilia_core.datas import dia_util_anterior, hora_de_horario


def test_terca_a_sexta_volta_um_dia():
    # quinta 11/06/2026 → quarta 10/06/2026
    assert dia_util_anterior(date(2026, 6, 11)) == date(2026, 6, 10)
    # sexta 12/06/2026 → quinta 11/06/2026
    assert dia_util_anterior(date(2026, 6, 12)) == date(2026, 6, 11)


def test_segunda_volta_para_sexta():
    # segunda 08/06/2026 → sexta 05/06/2026 (pula sáb/dom)
    assert dia_util_anterior(date(2026, 6, 8)) == date(2026, 6, 5)


def test_pula_feriado_fixo():
    # 02/01 (sexta em 2026) → dia anterior seria 01/01 (feriado) → 31/12/2025
    assert dia_util_anterior(date(2026, 1, 2)) == date(2025, 12, 31)


def test_dia_apos_finados():
    # 03/11/2026 (terça) → 02/11 é Finados (feriado) → 30/10/2026 (sexta)
    assert dia_util_anterior(date(2026, 11, 3)) == date(2026, 10, 30)


def test_hora_de_horario():
    assert hora_de_horario("07:00") == 7
    assert hora_de_horario("18:30") == 18
    assert hora_de_horario("00:00") == 0
    assert hora_de_horario("inválido") == 7   # fallback
    assert hora_de_horario("") == 7
    assert hora_de_horario("99:00") == 23      # clamp
