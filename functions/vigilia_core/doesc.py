"""
Busca no Diário Oficial de Santa Catarina (DOE-SC).

Integração direta com o endpoint oficial do portal:
    POST https://portal.doe.sea.sc.gov.br/apis/busca-materia

Payload confirmado por inspeção de rede (21/05/2026):
    {
        "busca": "",            # vazio = todas as publicações do dia
        "dtIni": "YYYY-MM-DD",
        "dtFim": "YYYY-MM-DD",
        "tipoBusca": 2,
        "pagination": {"from": 0, "size": 1000},
        "resumo": false,
        "aCdAssunto": [],
        "aCdCategoria": []
    }

Correções incorporadas (auditoria de 09/06/2026):
  - Logger nomeado por módulo (antes os logs saíam com prefixo "[DOU API]").
  - Sessão HTTP com retry e fallback SSL controlado (vigilia_core.filtros).
  - Retorna list[dict] no esquema padronizado (sem dependência de pandas).
"""

from __future__ import annotations

import logging
import re
from datetime import date

import requests

from .filtros import (
    criar_sessao,
    filtrar_publicacoes,
    normalizar_registro,
    requisitar,
)

logger = logging.getLogger("vigilia.doesc")

ENDPOINT = "https://portal.doe.sea.sc.gov.br/apis/busca-materia"

PAGE_SIZE = 1000

_RE_TIPO = re.compile(
    r"\b(PORTARIA|DECRETO|RESOLUÇÃO|EDITAL|EXTRATO|AVISO|ATA|LEI|INSTRUÇÃO)\b",
    re.IGNORECASE,
)


def extrair_tipo(titulo: str, assunto: str) -> str:
    """Extrai o tipo do ato a partir do título ou do assunto."""
    for texto in (titulo, assunto):
        if not texto:
            continue
        m = _RE_TIPO.search(texto)
        if m:
            return m.group(1).upper()
    return "ATO"


def _mapear_materia(mat: dict, data_br: str) -> dict:
    """Converte uma matéria do JSON do DOE-SC para o esquema padronizado."""
    resumo_texto = mat.get("resumo") or ""
    assunto = mat.get("assunto") or ""
    categoria = mat.get("categoria") or ""

    linhas = [l.strip() for l in resumo_texto.split("\n") if l.strip()]
    titulo = linhas[0] if linhas else assunto
    if len(titulo) > 200:
        titulo = titulo[:197] + "..."

    link = mat.get("extrato") or ""
    if not link:
        cd_jornal = mat.get("cdJornal")
        mat_id = mat.get("id")
        if cd_jornal and mat_id:
            link = (
                f"https://portal.doe.sea.sc.gov.br"
                f"/#/portal/edicao/{cd_jornal}/materia/{mat_id}"
            )

    return normalizar_registro({
        "origem": "DOE-SC",
        "hierarquia": f"DOE-SC › {categoria} › {assunto}",
        "titulo": titulo,
        "link": link,
        "descricao": resumo_texto,
        "resumo": resumo_texto,
        "tipo": extrair_tipo(titulo, assunto),
        "orgao": categoria or "Estado de Santa Catarina",
        "data": data_br,
    })


def buscar_doesc(
    data_publicacao: date,
    palavras_chave: list[str],
    operador: str = "OU",
) -> list[dict]:
    """
    Busca publicações do dia no DOE-SC (paginação automática) e filtra
    localmente por palavras-chave (insensível a acentos e maiúsculas).

    Retorna list[dict] no esquema padronizado; lista vazia em caso de falha.
    """
    dt_str = data_publicacao.strftime("%Y-%m-%d")
    data_br = data_publicacao.strftime("%d/%m/%Y")
    logger.info("Consultando DOE-SC para %s", data_br)

    sessao = criar_sessao()
    sessao.headers.update({"Content-Type": "application/json"})

    materias_total: list[dict] = []
    from_idx = 0
    pagina = 1

    while True:
        payload = {
            "busca": "",
            "dtIni": dt_str,
            "dtFim": dt_str,
            "tipoBusca": 2,
            "pagination": {"from": from_idx, "size": PAGE_SIZE},
            "resumo": False,
            "aCdAssunto": [],
            "aCdCategoria": [],
        }

        try:
            r = requisitar(sessao, "POST", ENDPOINT, json=payload, timeout=25)
        except requests.exceptions.RequestException as e:
            logger.error("Erro de rede no DOE-SC (página %d): %s", pagina, e)
            break

        if r.status_code != 200:
            logger.error(
                "Endpoint DOE-SC retornou status %d. Resposta: %s",
                r.status_code, r.text[:200],
            )
            break

        try:
            data_json = r.json()
        except ValueError:
            logger.error("Resposta não-JSON do DOE-SC: %s", r.text[:200])
            break

        materias = data_json.get("materias", [])
        if not materias:
            logger.info("Página %d sem registros — fim da paginação.", pagina)
            break

        materias_total.extend(materias)
        total_servidor = data_json.get("total", 0)
        logger.info("Página %d carregada com %d registros", pagina, len(materias))

        if len(materias_total) >= total_servidor or len(materias) < PAGE_SIZE:
            break

        from_idx += PAGE_SIZE
        pagina += 1

    logger.info("Total consolidado DOE-SC: %d publicações", len(materias_total))
    if not materias_total:
        return []

    registros = [_mapear_materia(mat, data_br) for mat in materias_total]
    # Comportamento histórico do DOE-SC: busca em resumo + assunto + categoria
    # (assunto/categoria compõem hierarquia e orgao no esquema padronizado).
    return filtrar_publicacoes(
        registros, palavras_chave, operador,
        campos_busca=("resumo", "hierarquia", "orgao"),
    )
