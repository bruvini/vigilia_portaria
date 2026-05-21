"""
Serviço de busca do Diário Oficial de Santa Catarina (DOE-SC).

Integração via API REST pública CKAN (dados.sc.gov.br).
O CSV é lido DIRETAMENTE NA MEMÓRIA via pd.read_csv(url) — sem cache local.
Filtragem dinâmica e flexível de palavras-chave (acento e case-insensitive).
Links oficiais gerados sem versão hardcoded do portal.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from datetime import date
from io import StringIO

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
    """Busca publicações no DOE-SC via API CKAN lendo o CSV direto na memória."""
    dt_str = data_publicacao.strftime("%Y-%m-%d")
    logger.info(f"Buscando DOE-SC para {dt_str} via API CKAN (sem cache)")

    try:
        # Passo A: Obter o pacote do Diário Oficial no CKAN
        url_package = "https://dados.sc.gov.br/api/3/action/package_show?id=diario-oficial-sc-publicacoes"
        r = requests.get(url_package, headers=HEADERS, verify=False, timeout=15)
        r.raise_for_status()

        resources = r.json().get("result", {}).get("resources", [])
        if not resources:
            logger.warning("Nenhum recurso encontrado na API do CKAN.")
            return pd.DataFrame(columns=COLUNAS)

        # Passo B: Localizar o recurso CSV do ano correspondente
        ano_alvo = str(data_publicacao.year)
        resource = None

        csv_resources = [res for res in resources if str(res.get("format", "")).upper() == "CSV"]

        for res in csv_resources:
            name = str(res.get("name", "")).lower()
            url = str(res.get("url", "")).lower()
            if ano_alvo in name or ano_alvo in url:
                resource = res
                break

        # Fallback: CSV mais recente disponível
        if not resource and csv_resources:
            resource = csv_resources[-1]
            logger.info(f"Recurso para o ano {ano_alvo} não encontrado. Fallback: {resource.get('name')}")

        if not resource:
            logger.warning("Nenhum recurso CSV disponível.")
            return pd.DataFrame(columns=COLUNAS)

        resource_url = resource.get("url")
        logger.info(f"Recurso selecionado: {resource.get('name')} — lendo direto na memória")

        # Passo C: Ler CSV diretamente na memória (sem salvar no disco)
        r_file = requests.get(resource_url, headers=HEADERS, verify=False, timeout=90)
        r_file.raise_for_status()

        conteudo = r_file.content.decode("utf-8-sig", errors="replace")
        df = pd.read_csv(
            StringIO(conteudo),
            sep=";",
            on_bad_lines="skip",
            dtype=str,
        )

        # 1. Filtro de data — retorna vazio silenciosamente se a data não existir
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
            titulo_norm = (
                df["TITULO_PUBLICACAO"].astype(str)
                .str.normalize("NFKD")
                .str.encode("ascii", errors="ignore")
                .str.decode("utf-8")
                .str.lower()
            )
            assunto_norm = (
                df["ASSUNTO"].astype(str)
                .str.normalize("NFKD")
                .str.encode("ascii", errors="ignore")
                .str.decode("utf-8")
                .str.lower()
            )

            padrao = "|".join(re.escape(p) for p in palabras_limpas)
            mask = titulo_norm.str.contains(padrao, na=False) | assunto_norm.str.contains(padrao, na=False)
            df = df[mask]

            if df.empty:
                logger.info("Nenhuma publicação correspondente às palavras-chave encontradas.")
                return pd.DataFrame(columns=COLUNAS)

        # 3. Mapeamento de Colunas — texto integral, sem truncamentos
        resultados = []
        for _, row in df.iterrows():
            texto_bruto = str(row["TITULO_PUBLICACAO"]).strip()

            # Separar título curto do corpo pelo primeiro duplo espaço
            partes = texto_bruto.split("  ", 1)
            titulo_extraido = partes[0].strip() if partes else "Ato Normativo"
            corpo = partes[1].strip() if len(partes) > 1 else texto_bruto

            categoria = str(row.get("CATEGORIA", "")).strip()
            assunto = str(row.get("ASSUNTO", "")).strip()

            orgao = _extrair_orgao(categoria)
            tipo = _extrair_tipo(titulo_extraido)

            # URL sem versão hardcoded — formato oficial estável
            edicao = str(row.get("EDICAO", "")).strip()
            publicacao = str(row.get("PUBLICACAO", "")).strip()
            link_url = ""
            if edicao and publicacao:
                link_url = f"https://portal.doe.sea.sc.gov.br/#/portal/edicao/{edicao}/materia/{publicacao}"

            # Palavra-chave que gerou o match
            palavra_encontrada = ""
            if palabras_limpas:
                texto_norm = remover_acentos(texto_bruto)
                assunto_norm_str = remover_acentos(assunto)
                for original_p, limpa_p in zip(palavras_chave, palabras_limpas):
                    if limpa_p in texto_norm or limpa_p in assunto_norm_str:
                        palavra_encontrada = original_p
                        break

            resultados.append({
                "origem": "DOE-SC",
                "hierarquia": f"DOE-SC › {categoria} › {assunto}",
                "titulo": titulo_extraido,
                "link": link_url,
                "link_certificado": link_url,
                # descricao = texto integral da publicação sem qualquer corte
                "descricao": texto_bruto,
                # resumo = corpo após o título, também sem corte
                "resumo": corpo,
                "tipo": tipo,
                "orgao": orgao,
                "pagina": "",
                "palavra_encontrada": palavra_encontrada,
            })

        df_final = pd.DataFrame(resultados, columns=COLUNAS)
        logger.info(f"DOE-SC: {len(df_final)} resultado(s) retornado(s).")
        return df_final

    except Exception as e:
        logger.error(f"Erro ao buscar publicações do DOE-SC via API CKAN: {e}", exc_info=True)
        return pd.DataFrame(columns=COLUNAS)


# ---------------------------------------------------------------------------
# Helpers de Metadados
# ---------------------------------------------------------------------------

def _extrair_tipo(titulo: str) -> str:
    """Extrai tipo do ato a partir do início do título."""
    match = re.search(r"^(PORTARIA|DECRETO|RESOLUÇÃO|EDITAL|EXTRATO|AVISO|ATA)", titulo, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return "ATO"


def _extrair_orgao(categoria: str) -> str:
    """Usa a categoria do CSV como órgão emissor diretamente."""
    return categoria if categoria else "Estado de Santa Catarina"
