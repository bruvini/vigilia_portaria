"""
Serviço de busca do Diário Oficial de Santa Catarina (DOE-SC).

Esta versão substitui a raspagem de DOM (Playwright) pelo uso direto
das APIs internas do portal Angular do DOE-SC. 

Fluxo:
1. Localizar ID do Jornal (cdJornal) para a data solicitada.
2. Mapear categorias disponíveis para focar na "Saúde".
3. Buscar as matérias paginadas da categoria.
4. Ao encontrar a palavra-chave (ex: "Joinville"):
   - Acessar o endpoint do Extrato PDF.
   - Fazer download temporário do PDF.
   - Extrair texto oficial com pdfplumber.
   - Processar NLP (Resumo + Trecho Relevante).
5. Retornar estrutura limpa para o Streamlit.
"""

from __future__ import annotations

import logging
import re
import tempfile
import json
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import pdfplumber
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="[DOE-SC API] %(levelname)s: %(message)s")

import unicodedata

# ---------------------------------------------------------------------------
# Configurações e Regras Institucionais
# ---------------------------------------------------------------------------

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/json, text/plain, */*",
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
    "palavra_encontrada",
    "score",            # Novo campo para depuração e priorização
    "categoria_badge"   # Novo campo para UI
]

# Regra 1: Categorias Estritas
VALID_CATEGORIES = [
    "secretarias de estado / saude",
    "prefeituras municipais / joinville"
]

def normalize_text(text: str) -> str:
    """Normaliza texto removendo acentos, espaços duplos e convertendo para minúsculas."""
    if not text:
        return ""
    # Converte para minúsculo
    text = text.lower()
    # Remove acentos
    text = "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )
    # Remove espaços duplos e trailing
    text = re.sub(r"\s+", " ", text).strip()
    return text

def is_valid_category(categoria: str) -> bool:
    """Verifica se a categoria do ato pertence ao escopo institucional permitido."""
    norm_cat = normalize_text(categoria)
    # Permite pequenas variações textuais usando 'in' ou match exato
    for valid in VALID_CATEGORIES:
        if valid in norm_cat:
            return True
        # Algumas vezes vem apenas "Saúde" ou "Joinville" da API
        if "saude" in norm_cat and "secretaria" in norm_cat:
            return True
        if "joinville" in norm_cat and "prefeitura" in norm_cat:
            return True
    return False

# Regra 2: Filtrar apenas Portarias
def is_portaria_document(titulo: str, assunto: str) -> bool:
    """Valida se o documento é uma portaria válida, ignorando licitações e outros."""
    termos = f"{titulo} {assunto}"
    norm_termos = normalize_text(termos)

    # Rejeições explícitas
    rejeicoes = ["licitacao", "homologacao", "julgamento", "extrato", "edital", "aviso"]
    for rej in rejeicoes:
        # Se contiver a palavra exata de rejeição (ex: "aviso de licitação")
        if re.search(rf"\b{rej}\b", norm_termos):
            return False

    # Deve iniciar com PORTARIA de forma forte
    # r"^\s*portaria\b" aplicado ao título ou ao assunto
    if re.search(r"^\s*portaria\b", normalize_text(titulo)):
        return True
    if re.search(r"^\s*portaria\b", normalize_text(assunto)):
        return True
    
    # Fallback relaxado, se a palavra "portaria" estiver forte solta
    if "portaria" in norm_termos:
        return True
        
    return False


# ---------------------------------------------------------------------------
# Funções de Serviço Principais
# ---------------------------------------------------------------------------

def buscar_doesc(data_publicacao: date, palavras_chave: list[str]) -> pd.DataFrame:
    """Busca publicações no DOE-SC via API e processa PDFs relevantes."""
    dt_str = data_publicacao.strftime("%Y-%m-%d")
    logger.info(f"Buscando DOE-SC para {dt_str} via API")

    session = requests.Session()
    session.headers.update(HEADERS)
    session.verify = False

    try:
        # 1. Obter cdJornal
        url_jornal = f"https://portal.doe.sea.sc.gov.br/apis/jornal/?page=1&perPage=12&dtStart={dt_str}%2000:00:00&dtEnd={dt_str}%2023:59:59"
        r = session.get(url_jornal, timeout=10)
        r.raise_for_status()
        jornais = r.json().get("records", {}).get("data", [])

        if not jornais:
            logger.warning(f"Nenhum jornal encontrado para {dt_str}")
            return pd.DataFrame(columns=COLUNAS)

        cd_jornal = jornais[0].get("cdJornal")
        logger.info(f"cdJornal encontrado: {cd_jornal}")

        # 2. Obter categorias
        url_cat = f"https://portal.doe.sea.sc.gov.br/apis/input/categoria?cdJornal={cd_jornal}"
        r = session.get(url_cat, timeout=10)
        r.raise_for_status()
        categorias_api = r.json().get("data", [])

        cat_ids = []
        for cat in categorias_api:
            if is_valid_category(cat.get("label", "")):
                cat_ids.append(cat.get("value"))

        if not cat_ids:
            logger.info("Nenhuma categoria permitida encontrada para este jornal.")
            # Se não houver a categoria alvo, não adianta tentar as outras, poupa processamento
            return pd.DataFrame(columns=COLUNAS)

        # 3. Buscar matérias por categoria
        materias_encontradas = []
        
        for cid in cat_ids:
            pagina = 1
            last_page = 1
            while pagina <= last_page:
                url_mat = (
                    f"https://portal.doe.sea.sc.gov.br/apis/edicao-preview/"
                    f"?categoria={cid}&assunto=&cdJornal={cd_jornal}"
                    f"&page={pagina}&rowsPerPage=20&sortOrder=desc"
                )
                r = session.get(url_mat, timeout=15)
                r.raise_for_status()
                data_mat = r.json().get("records", {})
                
                meta = data_mat.get("meta", {})
                last_page = meta.get("last_page", 1)
                materias = data_mat.get("data", [])

                if pagina == 1 and materias:
                    logger.info(f"--- 5 PRIMEIROS REGISTROS BRUTOS (CATEGORIA {cid}) ---")
                    logger.info(json.dumps(materias[:5], ensure_ascii=False, indent=2))

                for mat in materias:
                    texto_bruto = mat.get("dsTexto", "")
                    
                    achou_kw = None
                    if "joinville" in texto_bruto.lower():
                        achou_kw = "Joinville"
                    
                    if achou_kw:
                        resultado = _processar_materia(session, cd_jornal, mat, achou_kw)
                        if resultado:
                            materias_encontradas.append(resultado)

                pagina += 1

        if not materias_encontradas:
            return pd.DataFrame(columns=COLUNAS)

        # Regra 4: Priorização institucional
        # 1 = SECRETARIAS DE ESTADO / SAÚDE + PORTARIA
        # 2 = PREFEITURAS MUNICIPAIS / JOINVILLE + PORTARIA
        # 3 = Demais
        def sort_key(item):
            norm_cat = normalize_text(item["hierarquia"])
            if "saude" in norm_cat:
                return 1
            elif "joinville" in norm_cat:
                return 2
            return 3

        materias_encontradas.sort(key=sort_key)

        df = pd.DataFrame(materias_encontradas)
        for col in COLUNAS:
            if col not in df.columns:
                df[col] = ""
        return df[COLUNAS]

    except Exception as e:
        logger.error(f"Falha na busca DOE-SC API: {e}", exc_info=True)
        return pd.DataFrame(columns=COLUNAS)


def _processar_materia(session: requests.Session, cd_jornal: str, mat: dict[str, Any], kw: str) -> dict[str, Any] | None:
    """Baixa o extrato PDF da matéria, extrai texto inteligente e retorna o dict."""
    cd_materia = mat.get("cdMateria")
    titulo = mat.get("dsTitulo", "Ato Normativo").strip()
    categoria = mat.get("dsCategoria", "")
    assunto = mat.get("dsAssunto", "")
    tipo_ato = _extrair_tipo(titulo)

    # Validar Categoria
    if not is_valid_category(categoria):
        logger.info(f"[DOE-SC] Documento ignorado: categoria inválida | Categoria: '{categoria}' | Título: '{titulo}'")
        return None

    # Validar Portaria
    if not is_portaria_document(titulo, assunto):
        logger.info(f"[DOE-SC] Documento ignorado: não é portaria | Categoria: '{categoria}' | Assunto: '{assunto}' | Título: '{titulo}'")
        return None

    try:
        # Pega a URL do PDF oficial
        url_extrato = f"https://portal.doe.sea.sc.gov.br/apis/edicao-preview/extrato/edicao/{cd_jornal}/materia/{cd_materia}"
        r = session.get(url_extrato, timeout=10)
        r.raise_for_status()
        pdf_url = r.json().get("urlExtratoArquivo")
        
        if not pdf_url:
            logger.warning(f"Matéria {cd_materia} sem URL de extrato PDF")
            return None

        # Download e extração do PDF
        texto_limpo = _extrair_texto_pdf(session, pdf_url)
        if not texto_limpo:
            # Fallback para o dsTexto caso o PDF falhe
            texto_limpo = _limpar_texto(mat.get("dsTexto", ""))
        
        # Inteligência Semântica
        resumo = _extrair_resumo(texto_limpo)
        trecho = _extrair_trecho_relevante(texto_limpo, kw)
        orgao = _extrair_orgao(texto_limpo, categoria)

        # Regra 3: Calcular Score Joinville
        score = 0
        norm_cat = normalize_text(categoria)
        if "joinville" in norm_cat:
            score += 2
            
        norm_orgao = normalize_text(orgao)
        if "joinville" in norm_orgao:
            score += 2
            
        norm_trecho = normalize_text(trecho)
        if "joinville" in norm_trecho:
            score += 1
            
        norm_resumo = normalize_text(resumo)
        if "joinville" in norm_resumo:
            score += 1

        logger.info(f"[DOE-SC] Documento aprovado (Score: {score}): {cd_materia} | Título: '{titulo}'")

        # Badge visual para UI
        categoria_badge = "🏛️ Prefeitura Joinville" if "joinville" in norm_cat else "🏥 Saúde Estadual"

        return {
            "origem": "DOE-SC",
            "hierarquia": f"DOE-SC › {categoria} › {assunto}",
            "titulo": titulo,
            "link": "",
            "link_certificado": pdf_url,
            "descricao": trecho,
            "resumo": resumo,
            "tipo": tipo_ato,
            "orgao": orgao,
            "pagina": "",
            "palavra_encontrada": kw,
            "score": score,
            "categoria_badge": categoria_badge
        }

    except Exception as e:
        logger.error(f"Falha ao processar matéria {cd_materia}: {e}")
        return None


# ---------------------------------------------------------------------------
# Extração PDF e Processamento de Texto
# ---------------------------------------------------------------------------

def _extrair_texto_pdf(session: requests.Session, url: str) -> str:
    """Faz download do PDF para um arquivo temporário e extrai o texto com pdfplumber."""
    try:
        r = session.get(url, timeout=15)
        r.raise_for_status()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(r.content)
            tmp_path = tmp.name

        texto_completo = []
        with pdfplumber.open(tmp_path) as pdf:
            for page in pdf.pages:
                t = page.extract_text(x_tolerance=2, y_tolerance=3)
                if t:
                    texto_completo.append(t)
        
        Path(tmp_path).unlink(missing_ok=True)
        texto_unido = "\n".join(texto_completo)
        
        return _limpar_texto(texto_unido)
    except Exception as e:
        logger.error(f"Erro ao extrair PDF {url}: {e}")
        return ""


# Regex para identificar lixo financeiro
_RE_LIXO = re.compile(
    r"""(
        ^\s*[0-9]{5,}\s*$                
      | ^\s*[\d.,]+\s*$                  
      | ^\s*\d+[.,]\d+\s*[.,]\d+\s*$   
      | ^\s*R\$\s*[\d.,]+               
      | ^\s*Total.*?[\d.,]+\s*$          
      | ^\s*Subtotal.*?[\d.,]+\s*$
      | ^\s*FONTE\s+DE\s+RECURSOS
      | ^\s*ELEMENTO\s+DE\s+DESPESA
      | ^\s*NATUREZA\s+DE\s+DESPESA
      | ^\s*CÓD\.?\s+SIAF
      | (CNES|SIAF).*?\d{4,}
      | \b\d{4}\s\d{4}\s\d{4}\b
    )""",
    re.VERBOSE | re.IGNORECASE | re.MULTILINE,
)

_RE_TABELA = re.compile(r"([0-9]{1,4}[\s\t]+){3,}", re.MULTILINE)


def _limpar_texto(texto: str) -> str:
    """Aplica limpeza pesada para remover características de tabela/valores financeiros."""
    if not texto:
        return ""
    
    # Remove marca d'água e cabeçalhos padrão do PDF extrato
    texto = re.sub(r"DIÁRIO OFICIAL DE SANTA CATARINA.*?\n", "", texto, flags=re.IGNORECASE)
    texto = re.sub(r"EXTRATO DIGITAL DE PUBLICAÇÃO.*?\n", "", texto, flags=re.IGNORECASE)
    texto = re.sub(r"Publicado em:.*?Matéria n[º°]:.*?\n", "", texto, flags=re.IGNORECASE)
    
    # Substitui quebras com hífen no final da linha
    texto = re.sub(r"-\s*\n\s*", "", texto)
    
    texto = _RE_TABELA.sub(" ", texto)
    
    linhas_limpas = []
    for linha in texto.splitlines():
        ls = linha.strip()
        if ls and not _RE_LIXO.search(ls):
            linhas_limpas.append(ls)
            
    texto = "\n".join(linhas_limpas)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    texto = re.sub(r" {2,}", " ", texto)
    
    return texto.strip()


def _extrair_resumo(texto: str) -> str:
    """Extrai a frase mais representativa do documento para ser o 'Resumo'."""
    if not texto:
        return "Resumo não disponível."

    # Separação bruta por pontuação final ou quebras duplas
    blocos = re.split(r"(?<=[.!?])\s+|\n{2,}", texto)
    blocos = [b.strip().replace("\n", " ") for b in blocos if len(b.strip()) > 30]

    # Heurísticas de documento oficial (Resumo costuma ter verbos de ação na 3a pessoa)
    keywords_resumo = ["fica autorizado", "designar", "conceder", "tornar público", "objeto:", "resolve:", "referente à", "dispõe sobre"]
    
    for bloco in blocos:
        # Se for um trecho de Objeto ou RESOLVE, é o melhor resumo
        lower_bloco = bloco.lower()
        if any(kw in lower_bloco for kw in keywords_resumo):
            # Limpa o "RESOLVE: Art. 1º " do começo
            bloco_limpo = re.sub(r"^(resolve:\s*)?(art\.?\s*\d+[º°]?\s*)?-?\s*", "", bloco, flags=re.IGNORECASE).strip()
            # Capitaliza primeira letra
            if bloco_limpo:
                bloco_limpo = bloco_limpo[0].upper() + bloco_limpo[1:]
                # Trunca se for muito longo
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


def _extrair_trecho_relevante(texto: str, kw: str) -> str:
    """Isola rigorosamente a sentença que contém a keyword, mais contexto mínimo."""
    if not texto:
        return ""

    frases = re.split(r"(?<=[.!?])\s+|\n", texto)
    frases = [f.strip() for f in frases if f.strip() and len(f.strip()) > 5]

    kw_lower = kw.lower()
    indices = [i for i, f in enumerate(frases) if kw_lower in f.lower()]

    if not indices:
        return ""

    # Pega o primeiro índice que contém a keyword
    idx = indices[0]
    
    # Extrai 1 frase antes, a frase com a keyword, e 1 depois (se houver)
    inicio = max(0, idx - 1)
    fim = min(len(frases), idx + 2)
    
    trecho = " ".join(frases[inicio:fim]).replace("\n", " ")
    
    if len(trecho) > 400:
        trecho = trecho[:397] + "..."
        
    if inicio > 0:
        trecho = "..." + trecho
        
    return trecho


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
