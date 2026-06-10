"""
Utilitários compartilhados de filtragem, normalização e HTTP do Vigília.

Correções incorporadas (auditoria de 09/06/2026):
  - Filtragem por palavras-chave unificada e SEMPRE insensível a acentos e
    maiúsculas nas duas fontes (antes o DOU era sensível a acentos).
  - Operador lógico inválido gera aviso explícito em log (fallback para OU).
  - Sessão HTTP com retry automático (backoff exponencial) para falhas
    transitórias de rede.
  - Fallback de SSL sem verificação NÃO acontece mais silenciosamente:
    só é permitido com a variável de ambiente VIGILIA_SSL_FALLBACK=1,
    e mesmo assim com aviso em log.
"""

from __future__ import annotations

import logging
import os
import unicodedata

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger("vigilia.filtros")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

OPERADORES_VALIDOS = {"OU", "E"}

# Esquema padronizado: todo registro retornado pelas buscas possui
# exatamente estas chaves, sempre como str (exceto palavras_encontradas).
# Isso elimina a classe de bugs de "coluna ausente" (ex.: cards do DOU
# exibindo "nan" quando combinados com o DOE-SC).
SCHEMA_CAMPOS = [
    "origem",
    "secao",
    "hierarquia",
    "titulo",
    "link",
    "descricao",
    "resumo",
    "tipo",
    "orgao",
    "data",
    "palavras_encontradas",
]


def normalizar_registro(parcial: dict) -> dict:
    """Garante que o registro tenha todas as chaves do esquema padronizado."""
    registro = {campo: "" for campo in SCHEMA_CAMPOS}
    registro["palavras_encontradas"] = []
    registro.update({k: v for k, v in parcial.items() if k in SCHEMA_CAMPOS})
    return registro


def remover_acentos(texto: str) -> str:
    """Normaliza texto para comparação: sem acentos, minúsculas."""
    if not isinstance(texto, str):
        return ""
    return (
        unicodedata.normalize("NFKD", texto)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )


def normalizar_operador(operador: str) -> str:
    """Valida o operador lógico. Valor inválido vira 'OU' com aviso em log."""
    op = str(operador or "").strip().upper()
    if op not in OPERADORES_VALIDOS:
        if op:
            logger.warning(
                "Operador lógico inválido %r — usando 'OU'. Valores aceitos: OU, E.",
                operador,
            )
        return "OU"
    return op


def limpar_palavras(palavras_chave: list[str] | None) -> list[str]:
    """Remove termos vazios e espaços excedentes, preservando a grafia original."""
    if not palavras_chave:
        return []
    return [p.strip() for p in palavras_chave if isinstance(p, str) and p.strip()]


def filtrar_publicacoes(
    registros: list[dict],
    palavras_chave: list[str] | None,
    operador: str = "OU",
    campos_busca: tuple[str, ...] = ("titulo", "descricao", "resumo", "hierarquia"),
) -> list[dict]:
    """
    Filtra registros por palavras-chave, insensível a acentos e maiúsculas.

    - OU: mantém o registro se QUALQUER termo for encontrado.
    - E:  mantém o registro somente se TODOS os termos forem encontrados.
    - Sem palavras-chave: retorna todos os registros.

    Preenche `palavras_encontradas` em cada registro mantido.
    """
    palavras = limpar_palavras(palavras_chave)
    if not palavras:
        return registros

    op = normalizar_operador(operador)
    modo_and = op == "E"
    pares = [(p, remover_acentos(p)) for p in palavras]

    filtrados: list[dict] = []
    for registro in registros:
        texto = remover_acentos(
            " ".join(str(registro.get(campo, "")) for campo in campos_busca)
        )
        matches = [original for original, limpa in pares if limpa in texto]
        aceito = len(matches) == len(pares) if modo_and else bool(matches)
        if aceito:
            registro["palavras_encontradas"] = matches
            filtrados.append(registro)

    logger.info(
        "Filtro por palavras-chave %s (modo %s): %d de %d registros mantidos",
        [p for p, _ in pares],
        "E" if modo_and else "OU",
        len(filtrados),
        len(registros),
    )
    return filtrados


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

def criar_sessao(total_retries: int = 2, backoff: float = 0.5) -> requests.Session:
    """Sessão requests com User-Agent institucional e retry com backoff."""
    sessao = requests.Session()
    sessao.headers.update({"User-Agent": USER_AGENT})
    retry = Retry(
        total=total_retries,
        backoff_factor=backoff,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "POST"),
    )
    adapter = HTTPAdapter(max_retries=retry)
    sessao.mount("https://", adapter)
    sessao.mount("http://", adapter)
    return sessao


def ssl_fallback_permitido() -> bool:
    """
    Fallback para verify=False só é permitido com opt-in explícito via
    variável de ambiente — nunca silenciosamente (ver SECURITY.md).
    """
    return os.environ.get("VIGILIA_SSL_FALLBACK", "") == "1"


def requisitar(sessao: requests.Session, metodo: str, url: str, **kwargs) -> requests.Response:
    """
    Executa a requisição com verificação SSL estrita. Se a verificação falhar
    e VIGILIA_SSL_FALLBACK=1 estiver definido, repete sem verificação com
    aviso em log; caso contrário, propaga o erro.
    """
    try:
        return sessao.request(metodo, url, **kwargs)
    except requests.exceptions.SSLError:
        if not ssl_fallback_permitido():
            logger.error(
                "Falha de verificação SSL em %s. Defina VIGILIA_SSL_FALLBACK=1 "
                "apenas se você entender o risco (ver SECURITY.md).",
                url,
            )
            raise
        logger.warning(
            "Verificação SSL falhou em %s — repetindo SEM verificação "
            "(VIGILIA_SSL_FALLBACK=1 ativo).",
            url,
        )
        kwargs["verify"] = False
        return sessao.request(metodo, url, **kwargs)
