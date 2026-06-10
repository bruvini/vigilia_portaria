"""
Relatório institucional de varredura (e-mail HTML).

Gera um e-mail no estilo "Gazeta Oficial" — coerente com a SPA — usando apenas
estilos inline e tabelas (máxima compatibilidade com clientes de e-mail, que
ignoram <style> externo e fl/grid modernos).

Usado por:
  - functions/main.py → função agendada `relatorio_diario` e envio de teste.
  - tests/test_relatorio.py.

A seção de resumo por IA é renderizada apenas quando um texto de resumo é
fornecido (preparado para integração futura com o Google AI Studio / Gemini).
"""

from __future__ import annotations

import html
from datetime import date

NOMES_FONTES = {
    "DOU": "Diário Oficial da União",
    "DOE-SC": "Diário Oficial de Santa Catarina",
    "DOE-JOI": "Diário Oficial de Joinville",
}

CORES_ORIGEM = {
    "DOU": "#1d4ed8",
    "DOE-SC": "#15803d",
    "DOE-JOI": "#92400e",
}

# Paleta coerente com a SPA
_TINTA = "#101a2e"
_TINTA_SUAVE = "#3d4a61"
_PAPEL = "#f6f3ec"
_CARD = "#ffffff"
_BORDA = "#d8d2c4"
_AZUL = "#0ea5e9"
_AZUL_FUNDO = "#0a6da4"


def _e(texto) -> str:
    return html.escape(str(texto or ""))


def gerar_relatorio_html(
    resultados: list[dict],
    data_publicacao: date,
    palavras_chave: list[str],
    operador: str = "OU",
    resumo_ia: str | None = None,
) -> tuple[str, str]:
    """
    Gera (assunto, corpo_html) do relatório diário.

    resumo_ia: se fornecido, renderiza um bloco de "Síntese por IA" no topo
               (preparado para uso futuro — ver vigilia_core.ia).
    """
    data_br = data_publicacao.strftime("%d/%m/%Y")
    data_ext = _data_extenso(data_publicacao)
    total = len(resultados)
    assunto = f"Vigília · {total} publicação(ões) nos diários de {data_br}"

    por_origem: dict[str, list[dict]] = {}
    for r in resultados:
        por_origem.setdefault(r.get("origem", "DOU"), []).append(r)

    blocos = []
    for origem in ("DOU", "DOE-SC"):
        grupo = por_origem.pop(origem, [])
        if grupo:
            blocos.append(_bloco_origem(origem, grupo))
    for origem, grupo in por_origem.items():
        blocos.append(_bloco_origem(origem, grupo))

    termos = ", ".join(palavras_chave) if palavras_chave else "todas as publicações do dia"

    corpo_central = (
        "".join(blocos)
        if blocos
        else (
            f"<tr><td style='padding:40px 32px;text-align:center;'>"
            f"<div style=\"font-family:Georgia,serif;font-style:italic;font-size:22px;"
            f"color:{_TINTA_SUAVE};\">Nada consta.</div>"
            f"<div style='font-family:Arial,sans-serif;font-size:13px;color:#94a3b8;"
            f"margin-top:8px;'>Nenhuma publicação correspondeu aos critérios "
            f"configurados nesta edição.</div></td></tr>"
        )
    )

    bloco_ia = _bloco_resumo_ia(resumo_ia) if resumo_ia else ""

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

  <!-- RESUMO DOS PARÂMETROS -->
  <tr><td style="background:{_CARD};border-left:1px solid {_BORDA};
       border-right:1px solid {_BORDA};padding:22px 34px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
      <tr>
        <td style="font-family:Georgia,serif;font-size:40px;font-weight:bold;
            color:{_AZUL_FUNDO};line-height:1;width:90px;vertical-align:top;">{total}</td>
        <td style="font-family:Arial,sans-serif;font-size:13px;color:{_TINTA_SUAVE};
            line-height:1.6;vertical-align:top;padding-top:4px;">
          publicação(ões) encontrada(s)<br>
          <span style="color:#94a3b8;">termos:</span> <strong>{_e(termos)}</strong> ·
          <span style="color:#94a3b8;">operador:</span> <strong>{_e(operador)}</strong>
        </td>
      </tr>
    </table>
  </td></tr>

  {bloco_ia}

  <!-- CORPO -->
  <tr><td style="background:{_CARD};border-left:1px solid {_BORDA};
       border-right:1px solid {_BORDA};padding:8px 34px 28px 34px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
      {corpo_central}
    </table>
  </td></tr>

  <!-- RODAPÉ -->
  <tr><td style="background:{_TINTA};padding:24px 34px;text-align:center;
       border-bottom-left-radius:4px;border-bottom-right-radius:4px;">
    <div style="width:60px;height:3px;background:{_AZUL};margin:0 auto 16px auto;"></div>
    <div style="font-family:Georgia,serif;font-size:15px;font-weight:bold;color:#f8fafc;margin-bottom:6px;">
      Plataforma Vigília
    </div>
    <div style="font-family:Arial,sans-serif;font-size:12px;color:#94a3b8;line-height:1.7;">
      Unidade de Convênios e Parcerias · SMS Joinville<br>
      <a href="https://vigiliasms.web.app" style="color:#7dd3fc;text-decoration:none;">vigiliasms.web.app</a>
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


_ROTULOS_IA = ("PANORAMA", "DESTAQUES PARA JOINVILLE", "DESTAQUES", "RECOMENDAÇÃO")


def _bloco_resumo_ia(resumo: str) -> str:
    """
    Bloco de síntese por IA. Reconhece os rótulos estruturados do prompt
    (PANORAMA / DESTAQUES / RECOMENDAÇÃO) e os formata como subtítulos; trata
    linhas iniciadas por '•' como itens de lista.
    """
    corpo = []
    for linha_bruta in str(resumo).split("\n"):
        linha = linha_bruta.strip()
        if not linha:
            continue

        rotulo = next(
            (r for r in _ROTULOS_IA
             if linha.upper().startswith(r) and (
                 len(linha) == len(r) or linha[len(r):len(r) + 2] in (":", " :", ": ")
                 or linha[len(r)] == ":")),
            None,
        )
        if rotulo:
            texto = linha[len(rotulo):].lstrip(": ").strip()
            corpo.append(
                f"<div style='font-family:Arial,sans-serif;font-size:10px;font-weight:bold;"
                f"letter-spacing:1.5px;text-transform:uppercase;color:{_AZUL_FUNDO};"
                f"margin:12px 0 4px 0;'>{_e(rotulo)}</div>"
            )
            if texto:
                corpo.append(
                    f"<p style='margin:0 0 6px 0;'>{_e(texto)}</p>"
                )
        elif linha.startswith(("•", "-", "*")):
            item = linha.lstrip("•-* ").strip()
            corpo.append(
                f"<table role='presentation' cellpadding='0' cellspacing='0' style='margin:0 0 6px 0;'>"
                f"<tr><td style='color:{_AZUL};font-size:14px;vertical-align:top;"
                f"padding-right:8px;line-height:1.5;'>&#9656;</td>"
                f"<td style='font-family:Georgia,serif;font-size:14px;color:{_TINTA};"
                f"line-height:1.6;'>{_e(item)}</td></tr></table>"
            )
        else:
            corpo.append(f"<p style='margin:0 0 8px 0;'>{_e(linha)}</p>")

    return f"""
  <tr><td style="background:{_CARD};border-left:1px solid {_BORDA};
       border-right:1px solid {_BORDA};padding:4px 34px 20px 34px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
           style="background:#f0f9ff;border:1px solid #bae6fd;border-radius:6px;">
      <tr><td style="height:4px;background:{_AZUL};line-height:4px;font-size:0;">&nbsp;</td></tr>
      <tr><td style="padding:16px 22px 18px 22px;">
        <div style="font-family:Arial,sans-serif;font-size:11px;font-weight:bold;
             letter-spacing:2px;text-transform:uppercase;color:{_AZUL_FUNDO};margin-bottom:4px;">
          &#10022; Síntese por Inteligência Artificial
        </div>
        <div style="font-family:Georgia,serif;font-size:14px;color:{_TINTA};line-height:1.7;">
          {''.join(corpo)}
        </div>
        <div style="font-family:Arial,sans-serif;font-size:10px;color:#94a3b8;
             margin-top:12px;border-top:1px solid #bae6fd;padding-top:8px;">
          Resumo gerado automaticamente por IA a partir das publicações abaixo.
          Confira sempre o ato oficial antes de decisões.
        </div>
      </td></tr>
    </table>
  </td></tr>"""


def _bloco_origem(origem: str, grupo: list[dict]) -> str:
    nome = NOMES_FONTES.get(origem, origem)
    cor = CORES_ORIGEM.get(origem, _TINTA)
    itens = "".join(_item(r, cor) for r in grupo)
    return f"""
      <tr><td style="padding:18px 0 10px 0;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td style="font-family:Arial,sans-serif;font-size:12px;font-weight:bold;
                letter-spacing:2px;text-transform:uppercase;color:{_TINTA};
                border-bottom:2px solid {_TINTA};padding-bottom:6px;">{_e(nome)}</td>
            <td align="right" style="font-family:Arial,sans-serif;font-size:11px;
                color:#94a3b8;border-bottom:2px solid {_TINTA};padding-bottom:6px;">
                {len(grupo)} registro(s)</td>
          </tr>
        </table>
      </td></tr>
      {itens}"""


def _item(r: dict, cor: str) -> str:
    titulo = _e(r.get("titulo", "(sem título)"))
    link = str(r.get("link", "") or "")
    corpo = _e((r.get("resumo") or r.get("descricao") or "")[:380])
    hierarquia = _e(r.get("hierarquia", ""))
    secao = _e(r.get("secao", ""))
    etiqueta = " · ".join(p for p in [_e(r.get("origem", "")), f"Seção {secao.replace('DO','')}" if secao else ""] if p)

    titulo_html = (
        f"<a href='{_e(link)}' style='color:{_TINTA};text-decoration:none;'>{titulo}</a>"
        if link.startswith("http") else titulo
    )
    link_html = (
        f"<a href='{_e(link)}' style='font-family:Arial,sans-serif;font-size:11px;"
        f"font-weight:bold;letter-spacing:0.5px;text-transform:uppercase;"
        f"color:{_AZUL_FUNDO};text-decoration:none;'>Acessar publicação oficial &rarr;</a>"
        if link.startswith("http") else ""
    )
    return f"""
      <tr><td style="padding:0 0 14px 0;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
               style="border-left:3px solid {cor};background:#f8fafc;">
          <tr><td style="padding:12px 16px;">
            <div style="font-family:Arial,sans-serif;font-size:10px;letter-spacing:1px;
                 text-transform:uppercase;color:{cor};font-weight:bold;margin-bottom:5px;">
                 {etiqueta}</div>
            <div style="font-family:Arial,sans-serif;font-size:10px;color:#94a3b8;
                 margin-bottom:6px;">{hierarquia}</div>
            <div style="font-family:Georgia,serif;font-size:16px;font-weight:bold;
                 line-height:1.35;margin-bottom:6px;color:{_TINTA};">{titulo_html}</div>
            <div style="font-family:Arial,sans-serif;font-size:13px;color:{_TINTA_SUAVE};
                 line-height:1.6;margin-bottom:8px;">{corpo}</div>
            {link_html}
          </td></tr>
        </table>
      </td></tr>"""


def _data_extenso(d: date) -> str:
    meses = ["janeiro", "fevereiro", "março", "abril", "maio", "junho",
             "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
    return f"{d.day} de {meses[d.month - 1]} de {d.year}"
