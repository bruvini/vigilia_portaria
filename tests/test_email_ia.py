"""Testes do envio de e-mail (SMTP) e do módulo de IA (sem rede)."""

import os
from datetime import date
from unittest import mock

import pytest

from vigilia_core import ia
from vigilia_core.email_sender import (
    EmailNaoConfigurado,
    enviar_email,
    remetente_formatado,
)
from vigilia_core.relatorio import gerar_relatorio_html


def _ato(origem="DOU"):
    return {"origem": origem, "titulo": "PORTARIA X", "link": "https://in.gov.br/x",
            "descricao": "corpo", "resumo": "", "hierarquia": "MS", "secao": "DO1",
            "data": "09/06/2026"}


# ----------------------------------------------------------------- e-mail

def test_email_sem_credenciais_levanta():
    with mock.patch.dict(os.environ, {"VIGILIA_SMTP_USER": "", "VIGILIA_SMTP_PASS": ""}, clear=False):
        with pytest.raises(EmailNaoConfigurado):
            enviar_email(["a@b.com"], "assunto", "<p>oi</p>")


def test_remetente_formatado_com_credenciais():
    """O preview da UI é legível (sem encoding RFC 2047)."""
    env = {"VIGILIA_SMTP_USER": "vigilia@joinville.sc.gov.br",
           "VIGILIA_SMTP_PASS": "x", "VIGILIA_SMTP_FROM": "Vigília SMS"}
    with mock.patch.dict(os.environ, env, clear=False):
        assert remetente_formatado() == "Vigília SMS <vigilia@joinville.sc.gov.br>"


def test_email_header_from_codifica_acentos(monkeypatch):
    """No envio real, o cabeçalho From usa RFC 2047 para o nome acentuado."""
    capturado = {}

    class FakeSMTP:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def ehlo(self): pass
        def starttls(self, **k): pass
        def login(self, u, p): pass
        def send_message(self, msg): capturado["raw"] = msg.as_string()

    env = {"VIGILIA_SMTP_USER": "v@x.com", "VIGILIA_SMTP_PASS": "p",
           "VIGILIA_SMTP_FROM": "Vigília SMS", "VIGILIA_SMTP_PORT": "587"}
    monkeypatch.setattr("vigilia_core.email_sender.smtplib.SMTP", FakeSMTP)
    with mock.patch.dict(os.environ, env, clear=False):
        enviar_email(["d@y.com"], "a", "<p>b</p>")
    # no header serializado (o que vai pelo fio), o nome acentuado é codificado
    assert "=?utf-8?" in capturado["raw"]
    assert "<v@x.com>" in capturado["raw"]


def test_enviar_email_usa_smtp(monkeypatch):
    enviados = {}

    class FakeSMTP:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def ehlo(self): pass
        def starttls(self, **k): pass
        def login(self, u, p): enviados["login"] = u
        def send_message(self, msg):
            enviados["from"] = msg["From"]
            enviados["to"] = msg["To"]
            enviados["subject"] = msg["Subject"]

    env = {"VIGILIA_SMTP_USER": "remetente@x.com", "VIGILIA_SMTP_PASS": "senha",
           "VIGILIA_SMTP_FROM": "Vigília", "VIGILIA_SMTP_PORT": "587"}
    monkeypatch.setattr("vigilia_core.email_sender.smtplib.SMTP", FakeSMTP)
    with mock.patch.dict(os.environ, env, clear=False):
        r = enviar_email(["dest@y.com", "invalido"], "Assunto", "<p>Olá</p>")
    assert r["enviado"] is True
    assert r["destinatarios"] == ["dest@y.com"]   # filtra inválidos
    assert enviados["from"] == "Vigília <remetente@x.com>"
    assert enviados["subject"] == "Assunto"


def test_enviar_email_sem_destinatario_valido():
    env = {"VIGILIA_SMTP_USER": "u@x.com", "VIGILIA_SMTP_PASS": "p"}
    with mock.patch.dict(os.environ, env, clear=False):
        with pytest.raises(ValueError):
            enviar_email(["sem-arroba"], "a", "<p>b</p>")


# ----------------------------------------------------------------- relatório

def test_relatorio_com_resumo_ia_renderiza_markdown():
    md = (
        "✦ **Vigília IA · Análise de Impacto**\n"
        "## 📊 Panorama do Dia\n"
        "* 🟡 **Volume:** 1 publicação.\n"
        "* **Foco Principal:** repasse para Joinville."
    )
    _, corpo = gerar_relatorio_html([_ato()], date(2026, 6, 9), ["saúde"], "OU",
                                    resumo_ia=md)
    assert "Panorama do Dia" in corpo            # heading ## renderizado
    assert "<strong>Volume:</strong>" in corpo   # **negrito** → <strong>
    assert "Vigília IA" in corpo                  # banner ✦
    assert "Resumo gerado" in corpo               # rodapé do bloco de IA


def test_relatorio_sem_resumo_ia_omite_bloco():
    _, corpo = gerar_relatorio_html([_ato()], date(2026, 6, 9), ["saúde"], "OU")
    assert "Resumo gerado" not in corpo           # bloco de IA ausente


def test_relatorio_escapa_xss_no_email():
    ato = _ato()
    ato["titulo"] = "<script>alert(1)</script>"
    _, corpo = gerar_relatorio_html([ato], date(2026, 6, 9), [], "OU")
    assert "<script>alert" not in corpo
    assert "&lt;script&gt;" in corpo


# ----------------------------------------------------------------- IA

def test_ia_indisponivel_sem_key():
    with mock.patch.dict(os.environ, {"GEMINI_API_KEY": ""}, clear=False):
        assert ia.resumo_disponivel() is False
        assert ia.gerar_resumo([_ato()], "09/06/2026", ["saúde"]) is None


def test_ia_disponivel_com_key():
    with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "fake-key"}, clear=False):
        assert ia.resumo_disponivel() is True


def test_ia_prompt_inclui_publicacoes_e_total():
    prompt = ia._montar_prompt([_ato(), _ato("DOE-SC")], "09/06/2026", ["saúde"])
    assert "PORTARIA X" in prompt                              # publicação
    assert "saúde" in prompt                                   # termo monitorado
    assert "TOTAL DE PUBLICAÇÕES ENCONTRADAS: 2" in prompt     # contagem
    assert "use o total real de 2" in prompt


def test_ia_system_instruction_template_e_restricao():
    si = ia.SYSTEM_INSTRUCTION
    # seções do template
    for secao in ("Panorama do Dia", "Atos de Alto Impacto", "Próximos Passos"):
        assert secao in si
    assert "Vigília IA" in si
    # regra de restrição absoluta (quando nada relevante)
    assert "Nenhuma publicação de alto impacto" in si
    # regra de não inventar valores
    assert "valor sob consulta nos anexos do ato" in si
