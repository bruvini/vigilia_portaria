"""
Configuração padrão da varredura institucional.

Estes valores alimentam:
  - o documento `config/varredura` no Firestore (seed na primeira leitura);
  - o preenchimento inicial dos filtros na interface Streamlit legada;
  - a função agendada de relatório diário, quando não houver config salva.
"""

# Modelo de "kits" (conjuntos): lista de grupos; cada grupo é um E de termos,
# e entre grupos vale OU. Ex.: [["Joinville", "saúde"], ["Joinville", "portaria"]]
# = (Joinville E saúde) OU (Joinville E portaria).
GRUPOS_PADRAO: list[list[str]] = [
    ["Joinville", "saúde"],
    ["Joinville", "portaria"],
]

# Mantidos para a migração de configs antigas (palavras_chave + operador).
PALAVRAS_PADRAO: list[str] = ["Joinville", "convênio", "saúde"]
OPERADOR_PADRAO: str = "OU"

FONTES_PADRAO: dict[str, bool] = {
    "dou": True,
    "doesc": True,
}

# Relatório automático por e-mail (preparado, desativado por padrão).
# O envio usa SMTP direto (vigilia_core.email_sender) com credenciais em
# Firebase Secrets — ver README, seção "Relatório por e-mail".
RELATORIO_PADRAO: dict = {
    "ativo": False,
    "destinatarios": [],
    "horario": "07:00",   # America/Sao_Paulo — informativo; o cron real está em main.py
    "resumo_ia": False,    # síntese por IA (Gemini) — exige GEMINI_API_KEY (futuro)
}
