"""
Busca no Diário Oficial da União (DOU).

Estratégia: o portal Liferay do IN injeta todos os metadados da edição em
formato JSON na tag <script id="params"> de https://www.in.gov.br/leiturajornal.
Capturamos esse JSON via HTTP simples — sem navegador, sem Playwright.

Correções incorporadas (auditoria de 09/06/2026):
  - Filtragem por palavras-chave insensível a acentos (via vigilia_core.filtros).
  - Deduplicação por link NÃO descarta mais matérias com link vazio.
  - Sessão HTTP única com retry para as três seções.
  - Logger nomeado por módulo (sem logging.basicConfig em import).
  - Retorna list[dict] no esquema padronizado (sem dependência de pandas).
"""

from __future__ import annotations

import json
import logging
from datetime import date
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .filtros import (
    criar_sessao,
    filtrar_por_grupos,
    normalizar_registro,
    requisitar,
)

logger = logging.getLogger("vigilia.dou")

URL_BASE = "https://www.in.gov.br/leiturajornal"
DOMAIN = "https://www.in.gov.br"

SECOES = ["do1", "do2", "do3"]

ORGAO_PADRAO = "Ministério da Saúde"


def _limpar_html(texto_html: str) -> str:
    """Remove marcação HTML retornando o texto puro."""
    if not texto_html:
        return ""
    try:
        soup = BeautifulSoup(texto_html, "html.parser")
        return soup.get_text(separator=" ", strip=True)
    except Exception:
        return texto_html


def _mapear_materia(mat: dict, secao: str, data_str: str) -> dict:
    """Converte uma matéria do JSON do Liferay para o esquema padronizado."""
    url_title = mat.get("urlTitle", "")
    link = f"{DOMAIN}/en/web/dou/-/{url_title}" if url_title else ""

    content_html = mat.get("content", "")
    descricao = _limpar_html(content_html) if content_html else mat.get("subTitulo", "")

    return normalizar_registro({
        "origem": "DOU",
        "secao": secao.upper(),
        "hierarquia": mat.get("hierarchyStr", "") or "",
        "titulo": mat.get("title", "") or "",
        "link": link,
        "descricao": descricao or "",
        "tipo": (mat.get("artType", "") or "ATO").upper(),
        "orgao": mat.get("hierarchyStr", "") or "",
        "data": data_str,
    })


def _deduplicar_por_link(registros: list[dict]) -> list[dict]:
    """
    Remove duplicatas pelo link, MANTENDO todos os registros sem link
    (matérias sem urlTitle não são duplicatas entre si).
    """
    vistos: set[str] = set()
    unicos: list[dict] = []
    for registro in registros:
        link = registro.get("link", "")
        if link:
            if link in vistos:
                continue
            vistos.add(link)
        unicos.append(registro)
    return unicos


def buscar_dou(
    data_publicacao: date,
    grupos: list,
    secao: str = "do1",
    orgao: Optional[str] = ORGAO_PADRAO,
    tipo_ato: Optional[str] = None,
    sessao: Optional[requests.Session] = None,
) -> list[dict]:
    """
    Busca uma seção do DOU e aplica os filtros (kits + ruído) em memória.

    `grupos`: modelo de kits (DNF) — ver vigilia_core.filtros.filtrar_por_grupos.
    Retorna list[dict] no esquema padronizado; lista vazia em caso de falha.
    """
    data_fmt = data_publicacao.strftime("%d-%m-%Y")
    data_br = data_publicacao.strftime("%d/%m/%Y")
    sessao = sessao or criar_sessao()
    logger.info("Buscando DOU (%s) para %s", secao, data_fmt)

    try:
        r = requisitar(
            sessao, "GET", URL_BASE,
            params={"data": data_fmt, "secao": secao},
            timeout=20,
        )
        r.raise_for_status()

        soup = BeautifulSoup(r.text, "html.parser")
        script_params = soup.find("script", id="params")
        if not script_params or not script_params.string:
            logger.warning("Script JSON 'params' não encontrado para %s (%s).", data_fmt, secao)
            return []

        materias = json.loads(script_params.string).get("jsonArray", [])
        if not materias:
            logger.info("Edição %s de %s sem matérias.", secao, data_fmt)
            return []

        logger.info("Total de atos na edição %s em %s: %d", secao, data_fmt, len(materias))

        registros: list[dict] = []
        orgao_norm = (orgao or "").lower()
        tipo_norm = (tipo_ato or "").lower()
        for mat in materias:
            if orgao_norm and orgao_norm not in (mat.get("hierarchyStr", "") or "").lower():
                continue
            if tipo_norm and tipo_norm not in (mat.get("artType", "") or "").lower():
                continue
            registros.append(_mapear_materia(mat, secao, data_br))

        logger.info("Após filtros de órgão/tipo: %d registros", len(registros))
        # A busca NÃO inclui a hierarquia: ela sempre contém o nome do órgão
        # (ex.: "Ministério da Saúde"), o que tornaria termos como "saúde"
        # verdadeiros para todos os registros.
        return filtrar_por_grupos(
            registros, grupos,
            campos_busca=("titulo", "descricao"),
        )

    except requests.exceptions.RequestException as e:
        logger.error("Erro de rede ao acessar DOU (%s): %s", secao, e)
    except json.JSONDecodeError as e:
        logger.error("Erro ao decodificar JSON do DOU (%s): %s", secao, e)
    except Exception:
        logger.exception("Erro inesperado no DOU (%s)", secao)

    return []


def buscar_dou_completo(
    data_publicacao: date,
    grupos: list,
    orgao: Optional[str] = ORGAO_PADRAO,
    tipo_ato: Optional[str] = None,
) -> list[dict]:
    """
    Busca nas três seções do DOU (do1, do2, do3) com sessão HTTP única
    e retorna resultados consolidados e deduplicados.

    `grupos`: modelo de kits (DNF) — ver vigilia_core.filtros.filtrar_por_grupos.
    """
    sessao = criar_sessao()
    consolidado: list[dict] = []
    for secao in SECOES:
        consolidado.extend(
            buscar_dou(
                data_publicacao=data_publicacao,
                grupos=grupos,
                secao=secao,
                orgao=orgao,
                tipo_ato=tipo_ato,
                sessao=sessao,
            )
        )

    consolidado = _deduplicar_por_link(consolidado)
    logger.info("Total consolidado DOU (todas as seções): %d publicações", len(consolidado))
    return consolidado
