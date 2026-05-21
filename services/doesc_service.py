from __future__ import annotations
import logging
import re
import unicodedata
from datetime import date
import pandas as pd
import requests
import urllib3

# Desabilita avisos de SSL se necessário
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="[DOE-SC API] %(levelname)s: %(message)s")

# ---------------------------------------------------------------------------
# Configurações e Constantes
# ---------------------------------------------------------------------------
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Content-Type": "application/json",
    "Accept": "application/json, text/plain, */*"
}

COLUNAS = [
    "origem",
    "hierarquia",
    "titulo",
    "link",
    "link_certified",
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
    if not isinstance(texto, str):
        return ""
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("utf-8").lower()

# ---------------------------------------------------------------------------
# Função de Busca Principal
# ---------------------------------------------------------------------------
def buscar_doesc_direto(data_publicacao: date, palavras_chave: list[str]) -> pd.DataFrame:
    """Busca publicações diretamente na API ativa do Portal do DOE-SC para qualquer data sem cache."""
    
    # Formata a data para o padrão esperado pela query do portal (DD/MM/YYYY)
    dt_str = data_publicacao.strftime("%d/%m/%Y")
    logger.info(f"Buscando diretamente no Portal DOE-SC para a data: {dt_str} (Sem Cache/Fallback)")
    
    # CORREÇÃO: URL do microsserviço de busca da Imprensa Oficial de Santa Catarina
    url_api = "https://sea.sc.gov.br"
    
    # Payload para filtrar estritamente pela data solicitada no motor deles
    payload = {
        "dataPublicacaoInicio": dt_str,
        "dataPublicacaoFim": dt_str,
        "pagina": 1,
        "quantidadeRegistros": 500,  # Coleta até 500 registros do dia de uma vez
        "ordenacao": "DESC"
    }
    
    try:
        # Faz o POST diretamente no barramento do Estado
        r = requests.post(url_api, json=payload, headers=HEADERS, verify=False, timeout=25)
        r.raise_for_status()
        
        dados_retorno = r.json()
        
        # Mapeia as possíveis chaves que o portal retorna
        materias = dados_retorno.get("resultado", [])
        if not materias and isinstance(dados_retorno.get("registros"), list):
            materias = dados_retorno.get("registros", [])
        
        if not materias:
            logger.info(f"Nenhuma publicação oficial localizada para a data {dt_str}")
            return pd.DataFrame(columns=COLUNAS)
            
        resultados = []
        palabras_limpas = [remover_acentos(p.strip()) for p in palavras_chave if p.strip()]
        
        for mat in materias:
            # Captura os campos nativos retornados pela API estruturada
            texto_bruto = str(mat.get("textoMateria", mat.get("titulo", ""))).strip()
            categoria = str(mat.get("categoriaMateriaDescricao", mat.get("categoria", ""))).strip()
            assunto = str(mat.get("subCategoriaMateriaDescricao", mat.get("assunto", ""))).strip()
            edicao = str(mat.get("idEdicao", mat.get("edicao", ""))).strip()
            publicacao = str(mat.get("idMateria", mat.get("id", ""))).strip()
            
            # Divide título curto do corpo pelo padrão de duplo espaço comum nos diários
            partes = texto_bruto.split("  ", 1)
            titulo_extraido = partes[0].strip() if partes else "Ato Normativo"
            corpo = partes[1].strip() if len(partes) > 1 else texto_bruto
            
            # Filtro dinâmico de palavra-chave na memória
            palavra_encontrada = ""
            if palabras_limpas:
                texto_norm = remover_acentos(texto_bruto)
                assunto_norm = remover_acentos(assunto)
                match_detectado = False
                
                for original_p, limpa_p in zip(palavras_chave, palabras_limpas):
                    if limpa_p in texto_norm or limpa_p in assunto_norm:
                        palavra_encontrada = original_p
                        match_detectado = True
                        break
                if not match_detectado:
                    continue  # Pula o loop caso não dê match com nenhum termo
            
            # CORREÇÃO: Monta o link oficial dinâmico baseado na rota SPA do portal oficial (#/)
            link_url = ""
            if edicao and publicacao:
                link_url = f"https://sea.sc.gov.br{edicao}/materia/{publicacao}"
                
            # Identificação de tipo e órgão emissor
            tipo = _extrair_tipo(titulo_extraido)
            orgao = _extrair_orgao(categoria)
            
            resultados.append({
                "origem": "DOE-SC",
                "hierarquia": f"DOE-SC › {categoria} › {assunto}",
                "titulo": titulo_extraido,
                "link": link_url,
                "link_certified": link_url,
                "descricao": texto_bruto,
                "resumo": corpo,
                "tipo": tipo,
                "orgao": orgao,
                "pagina": str(mat.get("pagina", "")),
                "palavra_encontrada": palavra_encontrada,
            })
            
        df_final = pd.DataFrame(resultados, columns=COLUNAS)
        logger.info(f"DOE-SC: {len(df_final)} resultado(s) retornado(s).")
        return df_final

    except Exception as e:
        logger.error(f"Erro ao consultar a API oficial do DOE-SC: {e}", exc_info=True)
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
    """Usa a categoria da publicação como identificação do órgão emissor."""
    return categoria if categoria else "Estado de Santa Catarina"
