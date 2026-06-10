"""
Envio de e-mail do Vigília via SMTP.

Usa smtplib (stdlib) — sem dependências extras. As credenciais NÃO ficam no
código: são lidas de variáveis de ambiente, populadas no deploy a partir de
Firebase Secrets (ver functions/main.py e README).

Variáveis esperadas:
    VIGILIA_SMTP_HOST     ex.: smtp.gmail.com
    VIGILIA_SMTP_PORT     ex.: 587 (STARTTLS) ou 465 (SSL)
    VIGILIA_SMTP_USER     usuário/login SMTP (e o e-mail de envio)
    VIGILIA_SMTP_PASS     senha SMTP (no Gmail, uma "Senha de app")
    VIGILIA_SMTP_FROM     (opcional) nome de exibição do remetente
                          padrão: "Vigília · Diários Oficiais SMS Joinville"

O e-mail sai com um remetente "bonito": o nome de exibição + o endereço,
ex.:  Vigília · Diários Oficiais SMS Joinville <vigilia@...>
"""

from __future__ import annotations

import logging
import os
import smtplib
import ssl
from email.headerregistry import Address
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

logger = logging.getLogger("vigilia.email")

REMETENTE_PADRAO = "Vigília · Diários Oficiais SMS Joinville"


class EmailNaoConfigurado(RuntimeError):
    """Levantada quando faltam credenciais SMTP."""


def _config_smtp() -> dict:
    host = os.environ.get("VIGILIA_SMTP_HOST", "smtp.gmail.com")
    porta = int(os.environ.get("VIGILIA_SMTP_PORT", "587"))
    user = os.environ.get("VIGILIA_SMTP_USER", "")
    senha = os.environ.get("VIGILIA_SMTP_PASS", "")
    nome = os.environ.get("VIGILIA_SMTP_FROM", REMETENTE_PADRAO)
    if not user or not senha:
        raise EmailNaoConfigurado(
            "Credenciais SMTP ausentes. Defina os secrets VIGILIA_SMTP_USER e "
            "VIGILIA_SMTP_PASS (ver README, seção 'Relatório por e-mail')."
        )
    return {"host": host, "porta": porta, "user": user, "senha": senha, "nome": nome}


def remetente_formatado() -> str:
    """
    Retorna 'Nome Bonito <endereco>' legível para exibição na UI (sem o
    encoding RFC 2047 que o cabeçalho real usa). Não envia nada.
    """
    try:
        cfg = _config_smtp()
        return f"{cfg['nome']} <{cfg['user']}>"
    except EmailNaoConfigurado:
        return f"{REMETENTE_PADRAO} <e-mail não configurado>"


def enviar_email(
    destinatarios: list[str],
    assunto: str,
    corpo_html: str,
    corpo_texto: str | None = None,
) -> dict:
    """
    Envia um e-mail HTML (com alternativa em texto puro) para os destinatários.

    Retorna {"enviado": True, "destinatarios": [...]} em caso de sucesso.
    Levanta EmailNaoConfigurado se faltarem credenciais, ou propaga erros SMTP.
    """
    destinatarios = [d.strip() for d in destinatarios if d and "@" in d]
    if not destinatarios:
        raise ValueError("Nenhum destinatário válido informado.")

    cfg = _config_smtp()

    msg = EmailMessage()
    msg["Subject"] = assunto
    msg["From"] = formataddr((cfg["nome"], cfg["user"]))
    msg["To"] = ", ".join(destinatarios)
    msg["Message-ID"] = make_msgid(domain="vigiliasms.web.app")
    msg["Reply-To"] = cfg["user"]

    msg.set_content(corpo_texto or _html_para_texto(corpo_html))
    msg.add_alternative(corpo_html, subtype="html")

    contexto = ssl.create_default_context()
    logger.info("Enviando e-mail '%s' para %d destinatário(s)", assunto, len(destinatarios))

    if cfg["porta"] == 465:
        with smtplib.SMTP_SSL(cfg["host"], cfg["porta"], context=contexto, timeout=30) as smtp:
            smtp.login(cfg["user"], cfg["senha"])
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(cfg["host"], cfg["porta"], timeout=30) as smtp:
            smtp.ehlo()
            smtp.starttls(context=contexto)
            smtp.ehlo()
            smtp.login(cfg["user"], cfg["senha"])
            smtp.send_message(msg)

    logger.info("E-mail enviado com sucesso.")
    return {"enviado": True, "destinatarios": destinatarios}


def _html_para_texto(html: str) -> str:
    """Alternativa textual mínima (clientes sem HTML)."""
    import re
    texto = re.sub(r"<\s*br\s*/?>", "\n", html, flags=re.IGNORECASE)
    texto = re.sub(r"</\s*(p|div|h[1-6]|tr)\s*>", "\n", texto, flags=re.IGNORECASE)
    texto = re.sub(r"<[^>]+>", "", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip() or "Relatório Vigília (visualização em HTML)."
