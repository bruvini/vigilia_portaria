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
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import TimeoutError as FuturesTimeout
from datetime import date
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .filtros import (
    criar_sessao,
    filtrar_por_grupos,
    normalizar_registro,
    remover_acentos,
    requisitar,
)

logger = logging.getLogger("vigilia.dou")

URL_BASE = "https://www.in.gov.br/leiturajornal"
DOMAIN = "https://www.in.gov.br"

SECOES = ["do1", "do2", "do3"]

ORGAO_PADRAO = "Ministério da Saúde"

# --- Busca de TEXTO COMPLETO (a leiturajornal entrega só ~400 chars de prévia) ---
# A página de cada ato traz o corpo inteiro em <div class="texto-dou">.
MAX_WORKERS_SCRAPE = 8       # conexões em paralelo (limite rígido)
DEADLINE_SCRAPE_S = 45       # tempo máximo total do scraping profundo
TIMEOUT_ARTIGO_S = 8         # timeout por requisição de artigo

# Cache por edição (chave = URL do ato). Persiste enquanto a instância da
# function estiver "quente", evitando refazer o scraping no mesmo dia.
_CACHE_TEXTO: dict[str, str] = {}
_CACHE_MAX = 4000


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


# ---------------------------------------------------------------------------
# Triagem prévia e busca de texto completo (full-text)
# ---------------------------------------------------------------------------

def _triagem_materia(mat: dict) -> bool:
    """
    Decide, a partir dos METADADOS e da prévia, se vale buscar o texto completo
    do ato (para não raspar todas as ~4.000 publicações da edição):
      - órgão é da área da Saúde (hierarquia contém "saúde" — cobre MS, SAES,
        SGTES, ANVISA, etc.), OU
      - a prévia (título + ~400 chars) já menciona "Joinville".
    """
    hier = remover_acentos(mat.get("hierarchyStr", "") or "")
    previa = remover_acentos(
        (mat.get("title", "") or "") + " " + (mat.get("content", "") or "")
    )
    return ("saude" in hier) or ("joinville" in previa)


def _extrair_texto_artigo(html: str) -> str:
    """Extrai o corpo completo do ato a partir do HTML da sua página."""
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        return ""
    el = soup.select_one("div.texto-dou")
    if el:
        return el.get_text(" ", strip=True)
    # Fallback: o JSON embarcado da própria página do ato.
    script = soup.find("script", id="params")
    if script and script.string:
        try:
            arr = json.loads(script.string).get("jsonArray", [])
            if arr:
                return _limpar_html(arr[0].get("content", "") or "")
        except Exception:
            pass
    return ""


def _buscar_texto(sessao: requests.Session, link: str) -> str:
    """Busca (com cache por edição) o texto completo de um ato pela sua URL."""
    if not link:
        return ""
    if link in _CACHE_TEXTO:
        return _CACHE_TEXTO[link]
    try:
        r = requisitar(sessao, "GET", link, timeout=TIMEOUT_ARTIGO_S)
        if r.status_code == 200:
            texto = _extrair_texto_artigo(r.text)
            if texto:
                if len(_CACHE_TEXTO) > _CACHE_MAX:
                    _CACHE_TEXTO.clear()
                _CACHE_TEXTO[link] = texto
                return texto
    except Exception:
        pass
    return ""


def _enriquecer_textos(
    candidatos: list[dict],
    sessao: requests.Session,
    deadline: float,
) -> tuple[int, bool]:
    """
    Substitui a `descricao` (prévia) pelo TEXTO COMPLETO dos candidatos, em
    paralelo (ThreadPoolExecutor com no máx. MAX_WORKERS_SCRAPE conexões).

    Respeita um deadline absoluto (time.monotonic): ao estourar, devolve o que
    já foi obtido e sinaliza timeout=True; os atos não enriquecidos seguem com a
    prévia. Retorna (qtde_enriquecida, houve_timeout).
    """
    pendentes = [r for r in candidatos if r.get("link", "").startswith("http")]
    if not pendentes:
        return 0, False

    enriquecidos = 0
    timeout = False
    executor = ThreadPoolExecutor(max_workers=MAX_WORKERS_SCRAPE)
    try:
        futuros = {executor.submit(_buscar_texto, sessao, r["link"]): r for r in pendentes}
        restante = max(0.1, deadline - time.monotonic())
        try:
            for fut in as_completed(futuros, timeout=restante):
                registro = futuros[fut]
                try:
                    texto = fut.result()
                    if texto:
                        registro["descricao"] = texto
                        enriquecidos += 1
                except Exception:
                    pass
        except FuturesTimeout:
            timeout = True
    finally:
        # Não bloqueia esperando as requisições em voo (cada uma tem timeout).
        executor.shutdown(wait=False, cancel_futures=True)

    logger.info(
        "Texto completo do DOU: %d/%d atos enriquecidos%s",
        enriquecidos, len(pendentes), " (deadline atingido)" if timeout else "",
    )
    return enriquecidos, timeout


def _coletar_candidatos_secao(
    data_publicacao: date,
    secao: str,
    sessao: requests.Session,
) -> list[dict]:
    """
    Baixa a edição da seção e devolve os CANDIDATOS (atos de saúde ou que já
    citam Joinville na prévia), mapeados com a prévia de ~400 chars. A busca por
    texto completo é feita depois, em lote, por `buscar_dou_completo`.
    """
    data_fmt = data_publicacao.strftime("%d-%m-%Y")
    data_br = data_publicacao.strftime("%d/%m/%Y")
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
            return []

        candidatos = [
            _mapear_materia(mat, secao, data_br)
            for mat in materias if _triagem_materia(mat)
        ]
        logger.info(
            "Seção %s: %d atos, %d candidatos (saúde ou Joinville na prévia)",
            secao, len(materias), len(candidatos),
        )
        return candidatos

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
    avisos: Optional[list] = None,
) -> list[dict]:
    """
    Varre as três seções do DOU (do1, do2, do3), enriquece os candidatos com o
    TEXTO COMPLETO de cada ato (em paralelo, com deadline) e aplica os kits +
    filtro de ruído sobre o texto completo.

    `grupos`: modelo de kits (DNF) — ver vigilia_core.filtros.filtrar_por_grupos.
    `avisos`: se fornecido, recebe um aviso caso o scraping atinja o deadline.
    """
    sessao = criar_sessao(pool_maxsize=MAX_WORKERS_SCRAPE + 4)

    # 1) Triagem: coleta candidatos (saúde ou Joinville na prévia) das 3 seções.
    candidatos: list[dict] = []
    for secao in SECOES:
        candidatos.extend(_coletar_candidatos_secao(data_publicacao, secao, sessao))
    candidatos = _deduplicar_por_link(candidatos)
    logger.info("DOU: %d candidatos para texto completo", len(candidatos))

    # 2) Texto completo em paralelo, limitado pelo deadline.
    deadline = time.monotonic() + DEADLINE_SCRAPE_S
    _, timeout = _enriquecer_textos(candidatos, sessao, deadline)
    if timeout and avisos is not None:
        avisos.append(
            "A varredura em texto completo do DOU atingiu o tempo limite; alguns "
            "atos podem ter sido analisados apenas pela prévia."
        )

    # 3) Kits + ruído sobre o texto completo (título + corpo).
    resultado = filtrar_por_grupos(
        candidatos, grupos, campos_busca=("titulo", "descricao"),
    )
    logger.info("Total consolidado DOU (texto completo): %d publicações", len(resultado))
    return resultado
