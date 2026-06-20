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
    _, corpo = gerar_relatorio_html([_ato()], date(2026, 6, 9), ["saúde"],
                                    resumo_ia=md)
    assert "Panorama do Dia" in corpo            # heading ## renderizado
    assert "<strong>Volume:</strong>" in corpo   # **negrito** → <strong>
    assert "Vigília IA" in corpo                  # banner ✦
    # aviso de imprecisões da IA (novo layout: bloco amarelo abaixo do resumo)
    assert "Resumo gerado por IA" in corpo


def test_relatorio_sem_resumo_ia_omite_bloco():
    _, corpo = gerar_relatorio_html([_ato()], date(2026, 6, 9), ["saúde"])
    assert "Resumo gerado por IA" not in corpo   # aviso IA ausente quando sem resumo


def test_relatorio_escapa_xss_no_email():
    # Sem IA → lista compacta exibe o título; o escape XSS deve proteger o HTML.
    ato = _ato()
    ato["titulo"] = "<script>alert(1)</script>"
    _, corpo = gerar_relatorio_html([ato], date(2026, 6, 9), [])
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
    assert "PORTARIA X" in prompt                          # publicação
    assert "saúde" in prompt                               # termo monitorado
    assert "TOTAL DE PUBLICAÇÕES VARRIDAS: 2" in prompt    # contagem
    assert "de um total de 2 varridos" in prompt


def test_ia_prompt_avisa_dados_parciais():
    prompt = ia._montar_prompt([_ato()], "09/06/2026", [], avisos=["timeout no DOU"])
    assert "DADOS PARCIAIS" in prompt and "timeout no DOU" in prompt


def test_ia_system_instruction_triagem_e_restricao():
    si = ia.SYSTEM_INSTRUCTION
    for secao in ("Panorama do Dia", "Atos Relevantes para Convênios", "Próximos Passos"):
        assert secao in si
    assert "Vigília IA" in si
    # diretriz de triagem/descarte e critérios de inclusão
    assert "TRIAGEM E DESCARTE" in si
    assert "CRITÉRIOS DE INCLUSÃO" in si
    assert "Recursos Humanos" in si           # descarte de atos de pessoal
    # regra de restrição absoluta (quando nada relevante)
    assert "Nenhuma publicação de alto impacto" in si
    # regra de não inventar valores
    assert "Valor sob consulta nos anexos do ato" in si


def test_ia_system_instruction_calibracao_abrangencia():
    """A triagem não pode descartar programas nacionais/estaduais aplicáveis a SC."""
    si = ia.SYSTEM_INSTRUCTION
    assert "ABRANGÊNCIA ESTADUAL/NACIONAL" in si
    assert "SOBREPÕE" in si                              # prioridade sobre o geográfico
    assert "Grupo Hospitalar Conceição" in si or "GHC" in si
    assert "Estado de Santa Catarina" in si
    assert "PREVALECE" in si                             # inclusão de programa > exclusão geográfica
