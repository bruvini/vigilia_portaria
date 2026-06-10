"""
Utilitários de data do Vigília.

O relatório automático é enviado às 07h (America/Sao_Paulo), antes da publicação
da edição do próprio dia. Por isso a varredura agendada usa sempre o **dia útil
anterior** — ver `dia_util_anterior`.
"""

from __future__ import annotations

from datetime import date, timedelta

# Feriados fixos nacionais relevantes (MM-DD). Feriados móveis (Carnaval,
# Corpus Christi, Sexta-feira Santa) e municipais de Joinville podem ser
# acrescentados aqui no futuro, se necessário.
FERIADOS_FIXOS = {
    (1, 1),    # Confraternização Universal
    (4, 21),   # Tiradentes
    (5, 1),    # Dia do Trabalho
    (9, 7),    # Independência
    (10, 12),  # Nossa Senhora Aparecida
    (11, 2),   # Finados
    (11, 15),  # Proclamação da República
    (12, 25),  # Natal
}


def _e_dia_util(d: date) -> bool:
    """True se for dia de semana e não for feriado fixo conhecido."""
    if d.weekday() >= 5:  # 5 = sábado, 6 = domingo
        return False
    if (d.month, d.day) in FERIADOS_FIXOS:
        return False
    return True


def dia_util_anterior(referencia: date) -> date:
    """
    Retorna o dia útil imediatamente anterior à `referencia`.

    Pula fins de semana e feriados fixos conhecidos. Exemplos:
      - segunda-feira  → sexta-feira anterior
      - terça a sexta  → dia anterior
      - dia seguinte a feriado → último dia útil antes do feriado
    """
    d = referencia - timedelta(days=1)
    while not _e_dia_util(d):
        d -= timedelta(days=1)
    return d
