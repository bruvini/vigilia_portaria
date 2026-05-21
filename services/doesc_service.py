"""
Serviço de busca do Diário Oficial de Santa Catarina (DOE-SC).

Esta versão consome os dados diretamente da API REST do CKAN, salvando cache
local de arquivos CSV anuais, e realizando filtragem dinâmica e flexível de
palavras-chave (sem acentos e case-insensitive) e links oficiais clicáveis.
"""

from __future__ import annotations

import logging
import os
import re
import unicodedata
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="[DOE-SC API] %(levelname)s: %(message)s")

# ---------------------------------------------------------------------------
# Configurações e Constantes
# ---------------------------------------------------------------------------

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
}

COLUNAS = [
    "origem",
    "hierarquia",
    "titulo",
    "link",
    "link_certificado",
    "descricao",
    "resumo",
    "tipo",
    "orgao",
    "pagina",
    "palavra_encontrada"
]

CACHE_DIR = Path("data")

# ---------------------------------------------------------------------------
# Helpers de Texto
# ---------------------------------------------------------------------------

def remover_acentos(texto: str) -> str:
    """Remove acentos e converte para minúsculas de forma robusta."""
    if not isinstance(texto, str):
        return ""
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("utf-8").lower()


# ---------------------------------------------------------------------------
# Função de Busca Principal
# ---------------------------------------------------------------------------

def buscar_doesc(data_publicacao: date, palavras_chave: list[str]) -> pd.DataFrame:
    """Busca publicações no DOE-SC via API CKAN e processa dados locais."""
    dt_str = data_publicacao.strftime("%Y-%m-%d")
    logger.info(f"Buscando DOE-SC para {dt_str} via API CKAN")

    try:
        # Passo A: Obter o pacote do Diário Oficial no CKAN
        url_package = "https://dados.sc.gov.br/api/3/action/package_show?id=diario-oficial-sc-publicacoes"
        r = requests.get(url_package, headers=HEADERS, verify=False, timeout=15)
        r.raise_for_status()
        
        resources = r.json().get("result", {}).get("resources", [])
        if not resources:
            logger.warning("Nenhum recurso encontrado na API do CKAN.")
            return pd.DataFrame(columns=COLUNAS)

        # Passo B: Localizar o recurso correto (CSV do ano correspondente)
        ano_alvo = str(data_publicacao.year)
        resource = None
        
        # Filtra recursos em formato CSV
        csv_resources = [res for res in resources if str(res.get("format", "")).upper() == "CSV"]
        
        # Procura um recurso cuja URL ou nome contenha o ano alvo
        for res in csv_resources:
            name = str(res.get("name", "")).lower()
            url = str(res.get("url", "")).lower()
            if ano_alvo in name or ano_alvo in url:
                resource = res
                break
        
        # Fallback: Se não encontrou do ano correspondente, pega o mais recente (último CSV da lista)
        if not resource and csv_resources:
            resource = csv_resources[-1]
            logger.info(f"Recurso para o ano {ano_alvo} não encontrado. Usando fallback mais recente: {resource.get('name')}")
            
        if not resource:
            logger.warning("Nenhum recurso CSV disponível.")
            return pd.DataFrame(columns=COLUNAS)

        resource_url = resource.get("url")
        resource_name = resource.get("name", f"publicacoes_{data_publicacao.year}.csv")
        logger.info(f"Recurso selecionado: {resource_name} | ID: {resource.get('id')}")

        # Passo C: Baixar e carregar o arquivo bruto
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_path = CACHE_DIR / resource_name
        
        need_download = True
        if cache_path.exists():
            last_mod_str = resource.get("last_modified") or resource.get("created")
            if last_mod_str:
                try:
                    api_mtime = datetime.fromisoformat(last_mod_str[:19])
                    local_mtime = datetime.fromtimestamp(os.path.getmtime(cache_path))
                    if local_mtime >= api_mtime:
                        need_download = False
                        logger.info(f"Usando arquivo em cache: {cache_path}")
                except Exception as e:
                    logger.warning(f"Erro ao comparar datas de modificação: {e}")

        if need_download:
            logger.info(f"Baixando dados brutos de: {resource_url}")
            r_file = requests.get(resource_url, headers=HEADERS, verify=False, timeout=60)
            r_file.raise_for_status()
            with open(cache_path, "wb") as f:
                f.write(r_file.content)
            logger.info(f"Salvo em cache: {cache_path}")

        # Carrega o arquivo usando pandas
        df = pd.read_csv(cache_path, sep=";", encoding="utf-8-sig", dtype=str)
        
        # 1. Filtro de data
        dt_jornal_str = data_publicacao.strftime("%d/%m/%Y")
        if "DATA_PUBLICACAO" not in df.columns:
            logger.warning("Coluna DATA_PUBLICACAO não encontrada no CSV.")
            return pd.DataFrame(columns=COLUNAS)

        df["DATA_PUBLICACAO"] = df["DATA_PUBLICACAO"].astype(str).str.strip()
        df = df[df["DATA_PUBLICACAO"] == dt_jornal_str]
        
        if df.empty:
            logger.info(f"Nenhuma publicação encontrada para a data {dt_jornal_str}")
            return pd.DataFrame(columns=COLUNAS)

        # 2. Filtro de Palavras-Chave Dinâmico (Acento e Case Insensitive)
        palabras_limpas = [remover_acentos(p.strip()) for p in palavras_chave if p.strip()]
        
        if palabras_limpas:
            # Normalização unicode conforme dica do Pandas
            titulo_norm = df["TITULO_PUBLICACAO"].astype(str).str.normalize('NFKD').str.encode('ascii', errors='ignore').str.decode('utf-8').str.lower()
            assunto_norm = df["ASSUNTO"].astype(str).str.normalize('NFKD').str.encode('ascii', errors='ignore').str.decode('utf-8').str.lower()
            
            # Concatena as keywords com OR regex
            padrao = "|".join(re.escape(p) for p in palabras_limpas)
            mask = titulo_norm.str.contains(padrao, na=False) | assunto_norm.str.contains(padrao, na=False)
            df = df[mask]
            
            if df.empty:
                logger.info("Nenhuma publicação correspondente às palavras-chave encontradas.")
                return pd.DataFrame(columns=COLUNAS)

        # 3. Processamento dos dados e Mapeamento de Colunas
        resultados = []
        for _, row in df.iterrows():
            texto_bruto = str(row["TITULO_PUBLICACAO"]).strip()
            
            # Separar título e corpo pelo caractere de duplo espaço
            partes = texto_bruto.split("  ", 1)
            titulo_extraido = partes[0].strip() if partes else "Ato Normativo"
            corpo = partes[1].strip() if len(partes) > 1 else texto_bruto
            
            categoria = str(row.get("CATEGORIA", "")).strip()
            assunto = str(row.get("ASSUNTO", "")).strip()
            
            # Extrair resumo do corpo
            resumo = _extrair_resumo(corpo)
            orgao = _extrair_orgao(corpo, categoria)
            tipo = _extrair_tipo(titulo_extraido)
            
            # Montar a URL oficial concatenando EDICAO e PUBLICACAO
            edicao = str(row.get("EDICAO", "")).strip()
            publicacao = str(row.get("PUBLICACAO", "")).strip()
            link_url = ""
            if edicao and publicacao:
                link_url = f"https://portal.doe.sea.sc.gov.br/v2.43.01/#/portal/edicao/{edicao}/materia/{publicacao}"
            
            # Identificar dinamicamente qual palavra-chave deu match
            palavra_encontrada = ""
            if palabras_limpas:
                texto_bruto_norm = remover_acentos(texto_bruto)
                assunto_norm_str = remover_acentos(assunto)
                for original_p, limpa_p in zip(palavras_chave, palabras_limpas):
                    if limpa_p in texto_bruto_norm or limpa_p in assunto_norm_str:
                        palavra_encontrada = original_p
                        break
            
            resultados.append({
                "origem": "DOE-SC",
                "hierarquia": f"DOE-SC › {categoria} › {assunto}",
                "titulo": titulo_extraido,
                "link": link_url,
                "link_certificado": link_url,
                "descricao": texto_bruto,
                "resumo": resumo,
                "tipo": tipo,
                "orgao": orgao,
                "pagina": "",
                "palavra_encontrada": palavra_encontrada
            })

        df_final = pd.DataFrame(resultados, columns=COLUNAS)
        return df_final

    except Exception as e:
        logger.error(f"Erro ao buscar publicações do DOE-SC via API CKAN: {e}", exc_info=True)
        return pd.DataFrame(columns=COLUNAS)


# ---------------------------------------------------------------------------
# Extração de Metadados e Processamento de Texto
# ---------------------------------------------------------------------------

def _extrair_resumo(texto: str) -> str:
    """Extrai a frase mais representativa do documento para ser o 'Resumo'."""
    if not texto:
        return "Resumo não disponível."

    # Separação bruta por pontuação final ou quebras duplas
    blocos = re.split(r"(?<=[.!?])\s+|\n{2,}", texto)
    blocos = [b.strip().replace("\n", " ") for b in blocos if len(b.strip()) > 20]

    # Heurísticas de documento oficial (Resumo costuma ter verbos de ação na 3a pessoa)
    keywords_resumo = ["fica autorizado", "designar", "conceder", "tornar público", "objeto:", "resolve:", "referente à", "dispõe sobre"]
    
    for bloco in blocos:
        lower_bloco = bloco.lower()
        if any(kw in lower_bloco for kw in keywords_resumo):
            bloco_limpo = re.sub(r"^(resolve:\s*)?(art\.?\s*\d+[º°]?\s*)?-?\s*", "", bloco, flags=re.IGNORECASE).strip()
            if bloco_limpo:
                bloco_limpo = bloco_limpo[0].upper() + bloco_limpo[1:]
                if len(bloco_limpo) > 250:
                    return bloco_limpo[:247] + "..."
                return bloco_limpo

    # Fallback: pega o primeiro bloco substantivo
    if blocos:
        bloco = blocos[0]
        if len(bloco) > 250:
            return bloco[:247] + "..."
        return bloco
        
    return "Resumo não disponível."


def _extrair_tipo(titulo: str) -> str:
    """Extrai tipo do ato."""
    match = re.search(r"^(PORTARIA|DECRETO|RESOLUÇÃO|EDITAL|EXTRATO)", titulo, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return "ATO"


def _extrair_orgao(texto: str, categoria: str) -> str:
    """Extrai órgão emissor (usando categoria como fallback primário)."""
    if "Saúde" in categoria:
        return "Secretaria de Estado da Saúde"
        
    padroes = [
        r"(Secretaria[^\n,.]{3,80})",
        r"(Prefeitura[^\n,.]{3,60})",
        r"(Município de[^\n,.]{3,60})",
    ]
    for padrao in padroes:
        match = re.search(padrao, texto, re.IGNORECASE)
        if match:
            return match.group(1).strip()
            
    return categoria if categoria else "Estado de Santa Catarina"
