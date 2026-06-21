"""
Relatório institucional de varredura (e-mail HTML).

Gera um e-mail no estilo "briefing executivo" — bloco IA com links diretos aos
atos relevantes, aviso de imprecisões e botão CTA que leva ao app com a data
pré-carregada (deep-link). Sem IA: lista compacta com até 10 publicações.

Layout:
  1. Cabeçalho  (fundo escuro + marca)
  2. Faixa de alerta  (🔴/🟡 — inserida apenas quando a IA detecta urgência)
  3. Faixa de métricas  (N publicações · DOU:X · DOE-SC:Y · termos usados)
  4. Bloco IA  (se disponível — análise de impacto com links clicáveis)
  5. Lista compacta  (sem IA → top 10 títulos+links; com IA → omitida)
  6. Aviso IA  (se disponível — isenção de erros + contagem de publicações)
  7. Botão CTA  → deep-link vigiliasms.web.app?data=AAAA-MM-DD
  8. Rodapé

Urgência (detectada automaticamente do output da IA):
  🔴 Crítico   → assunto prefixado com "⚠️ URGENTE:" e faixa vermelha no e-mail
  🟡 Moderado  → assunto prefixado com "⚡ Atenção:"  e faixa âmbar no e-mail
  🟢 Baixo     → assunto e layout padrão

Usa apenas estilos inline e tabelas — máxima compatibilidade com clientes
de e-mail que ignoram <style> externo e fl/grid modernos (Outlook, Gmail).
"""

from __future__ import annotations

import html
import re
from datetime import date

NOMES_FONTES = {
    "DOU": "Diário Oficial da União",
    "DOE-SC": "Diário Oficial de Santa Catarina",
}

CORES_ORIGEM = {
    "DOU": "#1d4ed8",
    "DOE-SC": "#15803d",
}

# Paleta coerente com a SPA
_TINTA = "#101a2e"
_TINTA_SUAVE = "#3d4a61"
_PAPEL = "#f6f3ec"
_CARD = "#ffffff"
_BORDA = "#d8d2c4"
_AZUL = "#0ea5e9"
_AZUL_FUNDO = "#0a6da4"

_URL_APP = "https://vigiliasms.web.app"

# Número máximo de publicações exibidas no e-mail quando não há resumo IA.
_MAX_ITENS_SEM_IA = 10

# Paleta de urgência (faixa de alerta + prefixo no assunto)
_URGENCIA = {
    "critico":  {"emoji": "🔴", "label": "URGENTE",  "prefixo": "⚠️ URGENTE:",  "cor": "#b91c1c", "fundo": "#fef2f2", "borda": "#fca5a5"},
    "moderado": {"emoji": "🟡", "label": "ATENÇÃO",  "prefixo": "⚡ Atenção:",  "cor": "#92400e", "fundo": "#fffbeb", "borda": "#fcd34d"},
}

_RE_NIVEL = re.compile(r"(🔴|🟡|🟢)\s*(Cr[íi]tico|Moderado|Baixo)", re.IGNORECASE)


def detectar_urgencia(resumo_ia: str | None) -> str:
    """
    Lê o nível de urgência da linha de Panorama do output da IA.
    Retorna: 'critico', 'moderado', 'baixo' ou 'nenhum' (sem IA / sem nível).
    """
    if not resumo_ia:
        return "nenhum"
    m = _RE_NIVEL.search(resumo_ia)
    if not m:
        return "nenhum"
    emoji = m.group(1)
    if emoji == "🔴":
        return "critico"
    if emoji == "🟡":
        return "moderado"
    return "baixo"


def _e(texto) -> str:
    return html.escape(str(texto or ""))


_RE_NEGRITO = re.compile(r"\*\*(.+?)\*\*")
_RE_ITALICO = re.compile(r"\*(.+?)\*")
_RE_URL = re.compile(r"(https?://[^\s,\"<>]+)")


def _inline_md(texto: str) -> str:
    """Escapa o texto e aplica negrito (**), itálico (*) e URLs clicáveis."""
    seguro = _e(texto)
    seguro = _RE_NEGRITO.sub(r"<strong>\1</strong>", seguro)
    seguro = _RE_ITALICO.sub(r"<em>\1</em>", seguro)
    seguro = _RE_URL.sub(
        lambda m: (
            f"<a href='{m.group(1)}' style='color:{_AZUL_FUNDO};"
            f"font-weight:bold;'>Ver ato &rarr;</a>"
        ),
        seguro,
    )
    return seguro


def gerar_relatorio_html(
    resultados: list[dict],
    data_publicacao: date,
    termos: list[str],
    resumo_ia: str | None = None,
) -> tuple[str, str]:
    """
    Gera (assunto, corpo_html) do relatório diário.

    termos: lista achatada dos termos monitorados (apenas para exibição).
    resumo_ia: se fornecido, renderiza o bloco de análise de impacto e omite
               a lista compacta — o bloco IA é o conteúdo principal do e-mail.
    """
    data_br = data_publicacao.strftime("%d/%m/%Y")
    data_ext = _data_extenso(data_publicacao)
    total = len(resultados)

    por_origem: dict[str, list[dict]] = {}
    for r in resultados:
        por_origem.setdefault(r.get("origem", "DOU"), []).append(r)

    url_dia = f"{_URL_APP}?data={data_publicacao.isoformat()}"

    urgencia = detectar_urgencia(resumo_ia)
    cfg_urg = _URGENCIA.get(urgencia)

    if cfg_urg:
        assunto = f"{cfg_urg['prefixo']} Vigília · {total} publicação(ões) filtradas · {data_br}"
    else:
        assunto = f"Vigília · {total} publicação(ões) filtradas · {data_br}"

    faixa_alerta = _faixa_alerta(urgencia, cfg_urg) if cfg_urg else ""
    faixa_metricas = _faixa_metricas(total, por_origem, termos)

    if resumo_ia:
        corpo_central = _bloco_resumo_ia(resumo_ia) + _bloco_aviso_ia(total, url_dia)
    elif total == 0:
        corpo_central = _bloco_vazio()
    else:
        corpo_central = _bloco_lista_compacta(resultados, por_origem) + _bloco_cta(total, url_dia)

    corpo_central_final = corpo_central

    corpo = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:{_PAPEL};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{_PAPEL};">
<tr><td align="center" style="padding:28px 12px;">
<table role="presentation" width="640" cellpadding="0" cellspacing="0" style="max-width:640px;width:100%;">

  <!-- CABEÇALHO -->
  <tr><td style="background:{_TINTA};padding:0;border-top:4px solid {_AZUL};">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
      <tr><td style="padding:26px 34px 8px 34px;">
        <div style="font-family:Arial,sans-serif;font-size:10px;letter-spacing:3px;
             text-transform:uppercase;color:#7dd3fc;">
          Secretaria Municipal da Saúde · Joinville/SC
        </div>
      </td></tr>
      <tr><td style="padding:0 34px 4px 34px;">
        <div style="font-family:Georgia,'Times New Roman',serif;font-size:42px;
             font-weight:bold;color:#f8fafc;letter-spacing:-1px;">
          Vigília<span style="color:{_AZUL};">.</span>
        </div>
      </td></tr>
      <tr><td style="padding:0 34px 22px 34px;">
        <div style="font-family:Arial,sans-serif;font-size:12px;color:#cbd5e1;
             border-top:1px solid rgba(148,163,184,0.25);padding-top:12px;">
          Relatório automático de varredura · edição de <strong style="color:#f8fafc;">{_e(data_ext)}</strong>
        </div>
      </td></tr>
    </table>
  </td></tr>

  {faixa_alerta}

  {faixa_metricas}

  {corpo_central_final}

  <!-- RODAPÉ -->
  <tr><td style="background:{_TINTA};padding:24px 34px;text-align:center;
       border-bottom-left-radius:4px;border-bottom-right-radius:4px;">
    <div style="width:60px;height:3px;background:{_AZUL};margin:0 auto 16px auto;"></div>
    <div style="font-family:Georgia,serif;font-size:15px;font-weight:bold;color:#f8fafc;margin-bottom:6px;">
      Plataforma Vigília
    </div>
    <div style="font-family:Arial,sans-serif;font-size:12px;color:#94a3b8;line-height:1.7;">
      Unidade de Convênios e Parcerias · SMS Joinville<br>
      <a href="{_URL_APP}" style="color:#7dd3fc;text-decoration:none;">vigiliasms.web.app</a>
    </div>
    <div style="font-family:Arial,sans-serif;font-size:10px;color:#475569;
         letter-spacing:2px;margin-top:14px;">
      DOU · DOE-SC · FHIR R4 · HL7
    </div>
  </td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""
    return assunto, corpo


# ---------------------------------------------------------------------------
# Blocos internos
# ---------------------------------------------------------------------------

def _faixa_alerta(urgencia: str, cfg: dict) -> str:
    """Faixa de alerta colorida inserida abaixo do cabeçalho para 🔴/🟡."""
    mensagem = {
        "critico":  "Ação imediata pode ser necessária. Leia a análise abaixo e verifique os prazos.",
        "moderado": "Há atos que merecem atenção hoje. Confira a análise e os próximos passos.",
    }.get(urgencia, "")
    return f"""
  <tr><td style="background:{cfg['cor']};padding:12px 34px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
      <tr>
        <td style="font-family:Arial,sans-serif;font-size:13px;font-weight:bold;
            color:#ffffff;letter-spacing:0.3px;">
          {cfg['emoji']} {cfg['label']} · Vigília IA identificou atos de impacto
        </td>
      </tr>
      <tr><td style="font-family:Arial,sans-serif;font-size:11px;color:rgba(255,255,255,0.85);
           padding-top:3px;">{_e(mensagem)}</td></tr>
    </table>
  </td></tr>"""


def _faixa_metricas(total: int, por_origem: dict, termos: list[str]) -> str:
    """Faixa compacta com contagem total, breakdown por fonte e termos usados."""
    breakdown = " · ".join(
        f"{orig}: {len(regs)}"
        for orig, regs in por_origem.items()
    )
    termos_txt = (
        " · ".join(_e(t) for t in termos)
        if termos else "todas as publicações do dia"
    )
    return f"""
  <tr><td style="background:{_CARD};border-left:1px solid {_BORDA};
       border-right:1px solid {_BORDA};padding:18px 34px 16px 34px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
      <tr>
        <td style="font-family:Georgia,serif;font-size:36px;font-weight:bold;
            color:{_AZUL_FUNDO};line-height:1;width:70px;vertical-align:top;">{total}</td>
        <td style="font-family:Arial,sans-serif;font-size:12px;color:{_TINTA_SUAVE};
            line-height:1.7;vertical-align:top;padding-top:2px;">
          publicação(ões) filtradas com os termos monitorados<br>
          <span style="font-size:11px;color:#64748b;">{_e(breakdown)}</span><br>
          <span style="font-size:10px;color:#94a3b8;">termos: </span>
          <span style="font-size:10px;color:{_TINTA_SUAVE};font-weight:bold;">{termos_txt}</span>
        </td>
      </tr>
    </table>
  </td></tr>"""


def _bloco_resumo_ia(resumo: str) -> str:
    """
    Renderiza a análise de impacto da IA (Markdown) como HTML para e-mail.
    Suporta: '## ' (seção), '### ' (subtítulo), '* ' (lista), '✦ ' (banner)
    e formatação inline **negrito** / *itálico* / URLs → links clicáveis.
    """
    corpo = []
    for linha_bruta in str(resumo).split("\n"):
        linha = linha_bruta.strip()
        if not linha:
            continue

        if linha.startswith("## "):
            corpo.append(
                f"<div style='font-family:Arial,sans-serif;font-size:14px;font-weight:bold;"
                f"color:{_TINTA};border-bottom:1px solid #bae6fd;padding-bottom:5px;"
                f"margin:16px 0 8px 0;'>{_inline_md(linha[3:].strip())}</div>"
            )
        elif linha.startswith("### "):
            corpo.append(
                f"<div style='font-family:Arial,sans-serif;font-size:13px;font-weight:bold;"
                f"color:{_AZUL_FUNDO};margin:12px 0 4px 0;'>{_inline_md(linha[4:].strip())}</div>"
            )
        elif linha.startswith("✦"):
            corpo.append(
                f"<div style='font-family:Arial,sans-serif;font-size:13px;font-weight:bold;"
                f"color:{_AZUL_FUNDO};letter-spacing:0.5px;margin:0 0 10px 0;'>"
                f"{_inline_md(linha)}</div>"
            )
        elif linha.startswith(("* ", "- ", "• ")):
            item = linha[2:].strip()
            corpo.append(
                f"<div style='font-family:Arial,sans-serif;font-size:13px;color:{_TINTA};"
                f"line-height:1.6;margin:0 0 5px 0;padding-left:14px;'>{_inline_md(item)}</div>"
            )
        else:
            corpo.append(
                f"<p style='font-family:Arial,sans-serif;font-size:13px;color:{_TINTA};"
                f"line-height:1.6;margin:0 0 6px 0;'>{_inline_md(linha)}</p>"
            )

    return f"""
  <tr><td style="background:{_CARD};border-left:1px solid {_BORDA};
       border-right:1px solid {_BORDA};padding:4px 34px 20px 34px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
           style="background:#f0f9ff;border:1px solid #bae6fd;border-radius:6px;">
      <tr><td style="height:4px;background:{_AZUL};line-height:4px;font-size:0;">&nbsp;</td></tr>
      <tr><td style="padding:16px 22px 18px 22px;">
        <div style="color:{_TINTA};line-height:1.7;">
          {''.join(corpo)}
        </div>
      </td></tr>
    </table>
  </td></tr>"""


def _bloco_aviso_ia(total: int, url_dia: str) -> str:
    """Aviso de imprecisões da IA + botão CTA com deep-link."""
    return f"""
  <tr><td style="background:{_CARD};border-left:1px solid {_BORDA};
       border-right:1px solid {_BORDA};padding:0 34px 28px 34px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
           style="background:#fffbeb;border:1px solid #fde68a;border-radius:6px;">
      <tr><td style="padding:14px 20px;">
        <div style="font-family:Arial,sans-serif;font-size:12px;color:#78350f;line-height:1.6;">
          ⚠️ <strong>Resumo gerado por IA — pode conter erros ou omissões.</strong>
          Confirme sempre nos atos oficiais antes de qualquer decisão.<br>
          A varredura retornou <strong>{total} publicação(ões)</strong> com os termos
          monitorados. Acesse o Vigília para consultar todas.
        </div>
        <div style="margin-top:14px;text-align:center;">
          <a href="{_e(url_dia)}"
             style="display:inline-block;background:{_AZUL_FUNDO};color:#ffffff;
                    font-family:Arial,sans-serif;font-size:13px;font-weight:bold;
                    letter-spacing:0.5px;text-decoration:none;
                    padding:12px 28px;border-radius:5px;">
            Ver as {total} publicações no Vigília &rarr;
          </a>
        </div>
      </td></tr>
    </table>
  </td></tr>"""


def _bloco_lista_compacta(resultados: list[dict], por_origem: dict) -> str:
    """
    Lista compacta (sem IA): apenas título + link, agrupada por fonte,
    limitada a _MAX_ITENS_SEM_IA itens no total.
    """
    blocos = []
    exibidos = 0

    for origem in ("DOU", "DOE-SC"):
        grupo = por_origem.get(origem, [])
        if not grupo or exibidos >= _MAX_ITENS_SEM_IA:
            break
        nome = NOMES_FONTES.get(origem, origem)
        cor = CORES_ORIGEM.get(origem, _TINTA)
        itens_html = []
        for r in grupo:
            if exibidos >= _MAX_ITENS_SEM_IA:
                break
            titulo = _e(r.get("titulo", "(sem título)"))
            link = str(r.get("link", "") or "")
            tipo = _e(r.get("tipo", ""))
            titulo_html = (
                f"<a href='{_e(link)}' style='color:{_AZUL_FUNDO};font-weight:bold;"
                f"text-decoration:none;font-size:13px;'>{titulo}</a>"
                if link.startswith("http") else
                f"<span style='font-size:13px;font-weight:bold;color:{_TINTA};'>{titulo}</span>"
            )
            tipo_html = (
                f"<span style='font-family:Arial,sans-serif;font-size:10px;"
                f"color:#94a3b8;margin-right:6px;'>{tipo}</span>"
                if tipo else ""
            )
            itens_html.append(
                f"<tr><td style='padding:8px 0;border-bottom:1px solid #f1f5f9;'>"
                f"{tipo_html}{titulo_html}</td></tr>"
            )
            exibidos += 1

        if itens_html:
            blocos.append(f"""
      <tr><td style="padding:18px 0 6px 0;">
        <div style="font-family:Arial,sans-serif;font-size:11px;font-weight:bold;
             letter-spacing:2px;text-transform:uppercase;color:{cor};
             border-bottom:2px solid {cor};padding-bottom:4px;margin-bottom:4px;">
          {_e(nome)}
        </div>
      </td></tr>
      <tr><td>
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
          {''.join(itens_html)}
        </table>
      </td></tr>""")

    return f"""
  <tr><td style="background:{_CARD};border-left:1px solid {_BORDA};
       border-right:1px solid {_BORDA};padding:8px 34px 4px 34px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
      {''.join(blocos) if blocos else '<tr><td></td></tr>'}
    </table>
  </td></tr>"""


def _bloco_cta(total: int, url_dia: str) -> str:
    """Botão CTA com contagem e deep-link (usado quando não há IA)."""
    restantes = total - _MAX_ITENS_SEM_IA
    nota = (
        f"<div style='font-family:Arial,sans-serif;font-size:12px;color:#64748b;"
        f"margin-bottom:12px;'>... e mais <strong>{restantes}</strong> "
        f"publicação(ões) disponíveis no sistema.</div>"
        if restantes > 0 else ""
    )
    return f"""
  <tr><td style="background:{_CARD};border-left:1px solid {_BORDA};
       border-right:1px solid {_BORDA};padding:20px 34px 28px 34px;text-align:center;">
    {nota}
    <a href="{_e(url_dia)}"
       style="display:inline-block;background:{_AZUL_FUNDO};color:#ffffff;
              font-family:Arial,sans-serif;font-size:13px;font-weight:bold;
              letter-spacing:0.5px;text-decoration:none;
              padding:12px 28px;border-radius:5px;">
      Ver as {total} publicações no Vigília &rarr;
    </a>
    <div style="font-family:Arial,sans-serif;font-size:10px;color:#94a3b8;
         margin-top:10px;">
      Ative o Resumo por IA na configuração para receber uma análise de impacto neste e-mail.
    </div>
  </td></tr>"""


def _bloco_vazio() -> str:
    return (
        f"<tr><td style='background:{_CARD};border-left:1px solid {_BORDA};"
        f"border-right:1px solid {_BORDA};padding:40px 32px;text-align:center;'>"
        f"<div style=\"font-family:Georgia,serif;font-style:italic;font-size:22px;"
        f"color:{_TINTA_SUAVE};\">Nada consta.</div>"
        f"<div style='font-family:Arial,sans-serif;font-size:13px;color:#94a3b8;"
        f"margin-top:8px;'>Nenhuma publicação correspondeu aos critérios "
        f"configurados nesta edição.</div></td></tr>"
    )


def _data_extenso(d: date) -> str:
    meses = ["janeiro", "fevereiro", "março", "abril", "maio", "junho",
             "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
    return f"{d.day} de {meses[d.month - 1]} de {d.year}"


def gerar_digest_html(
    data_inicio: date,
    data_fim: date,
    termos: list[str],
    resumo_ia: str | None,
    dias_resumidos: list[dict],
) -> tuple[str, str]:
    """
    Gera (assunto, corpo_html) do digest semanal (sexta-feira).

    dias_resumidos: [{"data_br": "16/06", "total": N, "urgencia": "baixo"}, ...]
    """
    semana_inicio = data_inicio.strftime("%d/%m")
    semana_fim = data_fim.strftime("%d/%m/%Y")
    assunto = f"Vigília · Digest Semanal · {semana_inicio} a {semana_fim}"
    termos_txt = (
        " · ".join(_e(t) for t in termos)
        if termos else "todas as publicações"
    )
    total_semana = sum(d.get("total", 0) for d in dias_resumidos)

    linhas_dias = ""
    for dia in dias_resumidos:
        data_br = _e(dia.get("data_br", ""))
        total_dia = dia.get("total", 0)
        urgencia = dia.get("urgencia", "nenhum")
        emoji = {"critico": "🔴", "moderado": "🟡", "baixo": "🟢"}.get(urgencia, "⚪")
        linhas_dias += (
            f"<tr>"
            f"<td style='font-family:Arial,sans-serif;font-size:12px;color:{_TINTA};"
            f"padding:5px 0;border-bottom:1px solid {_BORDA};min-width:70px;'>{data_br}</td>"
            f"<td style='font-size:14px;padding:5px 14px;border-bottom:1px solid {_BORDA};'>{emoji}</td>"
            f"<td style='font-family:Arial,sans-serif;font-size:12px;color:{_TINTA_SUAVE};"
            f"padding:5px 0;border-bottom:1px solid {_BORDA};'>{total_dia} publicações filtradas</td>"
            f"</tr>"
        )

    tabela_dias = f"""
  <tr><td style="background:{_CARD};border-left:1px solid {_BORDA};
       border-right:1px solid {_BORDA};padding:20px 34px 12px 34px;">
    <div style="font-family:Arial,sans-serif;font-size:11px;font-weight:bold;
         letter-spacing:2px;text-transform:uppercase;color:{_TINTA_SUAVE};
         border-bottom:2px solid {_BORDA};padding-bottom:6px;margin-bottom:10px;">
      Semana em números
    </div>
    <table role="presentation" cellpadding="0" cellspacing="0">
      {linhas_dias}
      <tr>
        <td style="font-family:Arial,sans-serif;font-size:12px;font-weight:bold;
            color:{_TINTA};padding:8px 0 0 0;">Total</td>
        <td style="padding:8px 14px 0 14px;"></td>
        <td style="font-family:Arial,sans-serif;font-size:12px;font-weight:bold;
            color:{_AZUL_FUNDO};padding:8px 0 0 0;">{total_semana} publicações</td>
      </tr>
    </table>
  </td></tr>"""

    if resumo_ia:
        bloco_ia = _bloco_resumo_ia(resumo_ia)
        bloco_cta_final = f"""
  <tr><td style="background:{_CARD};border-left:1px solid {_BORDA};
       border-right:1px solid {_BORDA};padding:0 34px 28px 34px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
           style="background:#fffbeb;border:1px solid #fde68a;border-radius:6px;">
      <tr><td style="padding:14px 20px;">
        <div style="font-family:Arial,sans-serif;font-size:12px;color:#78350f;line-height:1.6;">
          ⚠️ <strong>Digest gerado por IA — pode conter erros ou omissões.</strong>
          Confirme sempre nos atos oficiais antes de qualquer decisão.
        </div>
        <div style="margin-top:14px;text-align:center;">
          <a href="{_e(_URL_APP)}"
             style="display:inline-block;background:{_AZUL_FUNDO};color:#ffffff;
                    font-family:Arial,sans-serif;font-size:13px;font-weight:bold;
                    letter-spacing:0.5px;text-decoration:none;
                    padding:12px 28px;border-radius:5px;">
            Abrir o Vigília &rarr;
          </a>
        </div>
      </td></tr>
    </table>
  </td></tr>"""
    else:
        bloco_ia = ""
        bloco_cta_final = f"""
  <tr><td style="background:{_CARD};border-left:1px solid {_BORDA};
       border-right:1px solid {_BORDA};padding:20px 34px 28px 34px;text-align:center;">
    <a href="{_e(_URL_APP)}"
       style="display:inline-block;background:{_AZUL_FUNDO};color:#ffffff;
              font-family:Arial,sans-serif;font-size:13px;font-weight:bold;
              letter-spacing:0.5px;text-decoration:none;
              padding:12px 28px;border-radius:5px;">
      Abrir o Vigília &rarr;
    </a>
    <div style="font-family:Arial,sans-serif;font-size:10px;color:#94a3b8;margin-top:10px;">
      Ative o Resumo por IA no relatório diário para enriquecer o digest semanal.
    </div>
  </td></tr>"""

    corpo = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:{_PAPEL};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{_PAPEL};">
<tr><td align="center" style="padding:28px 12px;">
<table role="presentation" width="640" cellpadding="0" cellspacing="0" style="max-width:640px;width:100%;">

  <!-- CABEÇALHO DIGEST -->
  <tr><td style="background:{_TINTA};padding:0;border-top:4px solid {_AZUL};">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
      <tr><td style="padding:26px 34px 8px 34px;">
        <div style="font-family:Arial,sans-serif;font-size:10px;letter-spacing:3px;
             text-transform:uppercase;color:#7dd3fc;">
          Secretaria Municipal da Saúde · Joinville/SC
        </div>
      </td></tr>
      <tr><td style="padding:0 34px 4px 34px;">
        <div style="font-family:Georgia,'Times New Roman',serif;font-size:36px;
             font-weight:bold;color:#f8fafc;letter-spacing:-1px;line-height:1.1;">
          Vigília<span style="color:{_AZUL};">.</span>
          <span style="font-size:16px;font-weight:400;color:{_AZUL};letter-spacing:0;">
            &nbsp;digest semanal
          </span>
        </div>
      </td></tr>
      <tr><td style="padding:0 34px 22px 34px;">
        <div style="font-family:Arial,sans-serif;font-size:12px;color:#cbd5e1;
             border-top:1px solid rgba(148,163,184,0.25);padding-top:12px;">
          Semana de <strong style="color:#f8fafc;">{_e(semana_inicio)}</strong>
          a <strong style="color:#f8fafc;">{_e(semana_fim)}</strong>
          &nbsp;·&nbsp; termos: <strong style="color:#7dd3fc;">{termos_txt}</strong>
        </div>
      </td></tr>
    </table>
  </td></tr>

  {tabela_dias}

  {bloco_ia}

  {bloco_cta_final}

  <!-- RODAPÉ -->
  <tr><td style="background:{_TINTA};padding:24px 34px;text-align:center;
       border-bottom-left-radius:4px;border-bottom-right-radius:4px;">
    <div style="width:60px;height:3px;background:{_AZUL};margin:0 auto 16px auto;"></div>
    <div style="font-family:Georgia,serif;font-size:15px;font-weight:bold;
         color:#f8fafc;margin-bottom:6px;">Plataforma Vigília</div>
    <div style="font-family:Arial,sans-serif;font-size:12px;color:#94a3b8;line-height:1.7;">
      Unidade de Convênios e Parcerias · SMS Joinville<br>
      <a href="{_URL_APP}" style="color:#7dd3fc;text-decoration:none;">vigiliasms.web.app</a>
    </div>
    <div style="font-family:Arial,sans-serif;font-size:10px;color:#475569;
         letter-spacing:2px;margin-top:14px;">DOU · DOE-SC · FHIR R4 · HL7</div>
  </td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""
    return assunto, corpo
