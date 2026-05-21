"""
Serviço de raspagem de dados do Diário Oficial da União (DOU).

Arquitetura Cloud-Native:
Utiliza apenas a biblioteca `requests` e `BeautifulSoup` para acessar
https://www.in.gov.br/leiturajornal. Em vez de raspar o DOM e lidar com
paginação complexa via Javascript (Playwright), este script captura a 
base de dados oficial injetada em formato JSON na tag <script id="params">.
Isso garante zero dependência de Chrome/Chromium no ambiente Cloud.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.parse
from datetime import date
from typing import Any, Optional

import pandas as pd
import requests
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------------------------------------------------------------------------
# Logger e Constantes
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="[DOU API] %(levelname)s: %(message)s")

URL_BASE = "https://www.in.gov.br/leiturajornal"
DOMAIN   = "https://www.in.gov.br"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
}

COLUNAS = ["origem", "hierarquia", "titulo", "link", "descricao"]


# ---------------------------------------------------------------------------
# Serviço Principal
# ---------------------------------------------------------------------------

def buscar_dou(
    data_publicacao: date,
    palavras_chave: list[str],
    operador: str = "OU",
    secao: str = "do1",
    orgao: Optional[str] = "Ministério da Saúde",
    tipo_ato: Optional[str] = "Portaria",
) -> pd.DataFrame:
    """
    Realiza a busca no DOU capturando o JSON embarcado e aplica filtros em memória.

    Args:
        data_publicacao: Data da edição a consultar.
        palavras_chave:  Lista de termos para filtrar os resultados (Título e Descrição).
        secao:           Seção do DOU ('do1', 'do2', 'do3').
        orgao:           Texto parcial para filtro do Órgão Emissor.
        tipo_ato:        Texto parcial para filtro de tipo de Ato.

    Returns:
        DataFrame com colunas padrão do Vigília.
    """
    data_fmt = data_publicacao.strftime("%d-%m-%Y")
    logger.info(f"Buscando DOU ({secao}) para {data_fmt} via HTTP estático")

    try:
        # Busca a página de leitura do jornal com a data e seção
        params = {"data": data_fmt, "secao": secao}
        r = requests.get(URL_BASE, params=params, headers=HEADERS, timeout=15, verify=False)
        r.raise_for_status()

        soup = BeautifulSoup(r.text, "html.parser")
        
        # O portal Liferay do IN insere todos os metadados num script ID "params"
        script_params = soup.find("script", id="params")
        if not script_params:
            logger.warning(f"Script JSON 'params' não encontrado para {data_fmt}.")
            return pd.DataFrame(columns=COLUNAS)
            
        json_data = json.loads(script_params.string)
        materias = json_data.get("jsonArray", [])
        
        if not materias:
            logger.warning(f"Array JSON de matérias vazio para {data_fmt}.")
            return pd.DataFrame(columns=COLUNAS)
            
        logger.info(f"Total de atos na edição {secao} em {data_fmt}: {len(materias)}")

        # Processar e filtrar matérias em memória
        resultados = []
        for mat in materias:
            mat_hierarquia = mat.get("hierarchyStr", "")
            mat_tipo       = mat.get("artType", "")
            mat_titulo     = mat.get("title", "")
            mat_urlTitle   = mat.get("urlTitle", "")
            
            # Limpa o HTML do content para usar na descrição
            mat_content_html = mat.get("content", "")
            mat_descricao  = _limpar_html_bs4(mat_content_html) if mat_content_html else mat.get("subTitulo", "")
            
            # Filtro de Órgão
            if orgao and orgao.lower() not in mat_hierarquia.lower():
                continue
                
            # Filtro de Tipo de Ato
            if tipo_ato and tipo_ato.lower() not in mat_tipo.lower():
                continue
                
            # Montar o Link Oficial
            link_ato = ""
            if mat_urlTitle:
                link_ato = f"{DOMAIN}/en/web/dou/-/{mat_urlTitle}"

            resultados.append({
                "origem":     "DOU",
                "hierarquia": mat_hierarquia,
                "titulo":     mat_titulo,
                "link":       link_ato,
                "descricao":  mat_descricao
            })

        logger.info(f"Total após filtros primários (Órgão/Tipo): {len(resultados)}")

        # Filtro final por Palavras-Chave (suporte AND/OR)
        return _filtrar_por_palavras_chave(resultados, palavras_chave, operador)

    except requests.exceptions.RequestException as e:
        logger.error(f"Erro de rede ao acessar DOU: {e}")
    except json.JSONDecodeError as e:
        logger.error(f"Erro ao decodificar JSON do DOU: {e}")
    except Exception as e:
        logger.error(f"Erro inesperado no DOU: {e}", exc_info=True)

    return pd.DataFrame(columns=COLUNAS)


# ---------------------------------------------------------------------------
# Funções Auxiliares
# ---------------------------------------------------------------------------

def _limpar_html_bs4(texto_html: str) -> str:
    """Remove marcação HTML retornando o texto puro formatado."""
    if not texto_html:
        return ""
    try:
        soup = BeautifulSoup(texto_html, "html.parser")
        return soup.get_text(separator=" ", strip=True)
    except Exception:
        return texto_html


def _filtrar_por_palavras_chave(
    resultados: list[dict],
    palavras_chave: list[str],
    operador: str = "OU",
) -> pd.DataFrame:
    """
    Filtra a lista de dicionários por palavras-chave com suporte a AND/OR.

    - OU (padrão): retorna se qualquer termo for encontrado (any).
    - E:            retorna somente se TODOS os termos forem encontrados (all).
    Busca case-insensitive em título + descrição concatenados.
    """
    if not resultados:
        return pd.DataFrame(columns=COLUNAS)

    df = pd.DataFrame(resultados, columns=COLUNAS)

    palavras_limpas = [p.strip().lower() for p in palavras_chave if p.strip()]
    if not palavras_limpas:
        return df

    modo_and = operador.strip().upper() == "E"
    logger.info(f"Modo de busca DOU: {'E (AND)' if modo_and else 'OU (OR)'}")

    mascara: list[bool] = []
    for _, row in df.iterrows():
        texto_completo = f"{row['titulo']} {row['descricao']}".lower()
        resultados_match = [p in texto_completo for p in palavras_limpas]
        if modo_and:
            mascara.append(all(resultados_match))
        else:
            mascara.append(any(resultados_match))

    df_filtrado = df[mascara].reset_index(drop=True)
    logger.info(f"Total após filtro por palavras-chave ({palavras_limpas}): {len(df_filtrado)}")
    return df_filtrado
