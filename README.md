# Plataforma Vigília

Sistema institucional de inteligência e monitoramento automatizado de publicações
em diários oficiais — com varredura automática, filtragem por palavras-chave e geração de relatórios.

---

## Como executar localmente

### 1. Instale as dependências Python

```bash
pip install -r requirements.txt
```

### 2. Execute a aplicação

```bash
streamlit run streamlit_app.py
```

---

## Tecnologias Utilizadas

| Biblioteca         | Finalidade                                               |
|--------------------|----------------------------------------------------------|
| **Streamlit**      | Interface de usuário web interativa                      |
| **Pandas**         | Estruturação e filtragem dos dados extraídos             |
| **Requests**       | Integração HTTP com APIs públicas (DOU e CKAN DOE-SC)    |
| **BeautifulSoup4** | Suporte auxiliar a parsing HTML estático (DOU)           |

---

## Estrutura do Projeto

```
vigilia_portaria/
├── .github/
│   └── workflows/
│       └── ci.yml              # Pipeline de CI/CD (GitHub Actions)
├── streamlit_app.py            # Ponto de entrada da aplicação
├── requirements.txt            # Dependências do projeto
├── GOVERNANCE.md               # Políticas de ramificação, PR e hooks Git
├── SECURITY.md                 # Políticas de segurança, PII e LGPD
├── verify.py                   # Script de verificação sintática e linter local
├── .streamlit/
│   └── config.toml             # Configuração do tema (Light Mode forçado)
├── assets/                     # Imagens e recursos estáticos
├── components/                 # Componentes de UI reutilizáveis
│   ├── hero.py                 # Banner de cabeçalho (CSS separado do HTML base64)
│   ├── sidebar.py              # Barra lateral de navegação
│   ├── cards.py                # Cards informativos
│   └── footer.py               # Rodapé
├── pages/
│   └── home.py                 # Página principal: filtros, varredura e resultados
├── services/
│   ├── dou_service.py          # Motor de busca do DOU via Liferay Script
│   ├── doesc_service.py        # Motor de busca do DOE-SC via API REST CKAN pública
│   └── fhir_service.py         # Serviço de interoperabilidade de saúde (FHIR/HL7)
├── styles/
│   └── main.css                # Folha de estilos principal (Light Theme)
└── utils/
    └── helpers.py              # Funções utilitárias (ex: load_css)
```

---

## Fontes de Pesquisa Disponíveis

| Fonte                                     | Status             |
|-------------------------------------------|--------------------|
| Diário Oficial da União (DOU)             | Disponível         |
| Diário Oficial de Santa Catarina (DOE-SC) | Disponível         |
| Diário Oficial de Joinville               | Em desenvolvimento |

---

## Como Funciona a Busca — DOU

### Fluxo de Execução

```
services/dou_service.py
  ├── URL: https://www.in.gov.br/leiturajornal?data=DD-MM-YYYY&secao=do1
  ├── Aguarda carregamento dinâmico do JavaScript
  ├── Aplica filtro de Órgão  → <select id="slcOrgs">  (Ministério da Saúde)
  ├── Aplica filtro de Tipo   → <select id="slcTipo">  (Portaria)
  ├── Extrai cada <div class="resultado">:
  │     ├── hierarquia  → <ol class="dou-hierarquia"> <li>
  │     ├── titulo      → <h5 class="title-marker"> <a>
  │     ├── link        → atributo href do <a>
  │     └── descricao   → <p class="abstract-marker">
  └── Filtra resultados pelas palavras-chave fornecidas
```

---

## Como Funciona a Busca — DOE-SC

### Integração via API REST CKAN

O portal de dados abertos de Santa Catarina disponibiliza a base de publicações oficiais estruturada em formato CKAN. A API é consumida diretamente, garantindo performance e estabilidade.

### Fluxo de Execução (API CKAN + Pandas)

```
services/doesc_service.py
  ├── 1. GET: https://dados.sc.gov.br/api/3/action/package_show?id=diario-oficial-sc-publicacoes
  ├── 2. Identifica recurso CSV correspondente ao ano da data_publicacao
  │      └── Fallback: mais recente se o ano atual não possuir recurso cadastrado
  ├── 3. Baixa e cacheia localmente o arquivo CSV em data/ se:
  │      └── O arquivo local não existir
  │      └── O last_modified retornado na API for mais recente que o arquivo local
  ├── 4. Lê o CSV usando Pandas com encoding utf-8-sig e sep=;
  └── 5. Aplica filtros em memória (Pandas):
         ├── DATA_PUBLICACAO == data_publicacao (DD/MM/YYYY)
         ├── CATEGORIA ou TITULO_PUBLICACAO contém "saúde" (case-insensitive)
         ├── ASSUNTO ou TITULO_PUBLICACAO contém "PORTARIA" (case-insensitive)
         └── TITULO_PUBLICACAO contém regex r'(?i)munic[ií]pio:\s*joinville'
```

### Otimizações e Estrutura dos Dados

- **Cache Inteligente:** Os arquivos anuais possuem ~7MB. O download só é realizado sob demanda caso ocorram atualizações pelo governo de SC, reduzindo a latência da busca para milissegundos.
- **Parsing de Título e Corpo:** A coluna `TITULO_PUBLICACAO` contém o texto oficial com limite de 199 caracteres. Os metadados de título curto e descrição (corpo) são extraídos com base no separador de duplo espaço (`"  "`), fornecendo uma exibição limpa nos cards do Streamlit.

---

## Parâmetros das Funções Principais

```python
# DOU
buscar_dou_completo(
    data_publicacao: date,       # Data da edição
    palavras_chave: list[str],   # Termos de filtragem (case-insensitive)
    operador: str = "OU",        # "OU" | "E"
) -> pd.DataFrame

# DOE-SC
buscar_doesc_direto(
    data_publicacao: date,       # Data da edição
    palavras_chave: list[str],   # Termos de filtragem (case-insensitive)
    operador: str = "OU",
) -> pd.DataFrame
```

---

*Secretaria Municipal de Saúde de Joinville — Unidade de Convênios e Parcerias*

---

## Regras Visuais de Exibição e Interface

A interface da Plataforma Vigília foi refatorada e harmonizada seguindo diretrizes visuais unificadas:

1. **Cards Selecionáveis na Barra Lateral (Sidebar)**:
   - Cards informativos verticais com checkbox de seleção para cada Diário Oficial.
   - Textos explicativos para cada Diário indicando as regras de varredura executadas pelo robô Vigília.

2. **Exibição Harmonizada**:
   - Todo resultado é renderizado em um card padronizado com estilo consistente.
   - Metadados exibidos no cabeçalho: Hierarquia da publicação, data e badge colorido indicando a origem (DOU, DOE-SC, etc.).

3. **Links e Texto Integral**:
   - **Diário Oficial da União (DOU)**: Título clicável com link externo de redirecionamento.
   - **Diário Oficial de Santa Catarina (DOE-SC)**: Texto integral exibido diretamente no card.

4. **Identificação de Município**:
   - Badge estilizado é adicionado quando há menção à cidade de **Joinville** nos resultados.

---

## Interoperabilidade e Padrões de Saúde (FHIR, HL7 e SNOMED CT)

Para garantir que a plataforma atenda aos requisitos de integração e saúde digital, a plataforma implementa uma camada dedicada de interoperabilidade:

1. **Mapeamento FHIR R4 (`DocumentReference`)**:
   - Cada portaria, decreto ou ato normativo filtrado é convertido programaticamente em um recurso `DocumentReference` do FHIR R4.
   - Os metadados como título, hierarquia, link e data da publicação são organizados seguindo o esquema padrão internacional. O texto da portaria é anexado via codificação Base64 no próprio recurso (`content.attachment.data`).

2. **Mensageria HL7 (FHIR Message Bundle)**:
   - Para envio de notificações a barramentos de saúde do SUS ou do Prontuário Eletrônico do município (PEP), a plataforma agrupa os recursos em um `Bundle` do tipo `message` com cabeçalho `MessageHeader`.

3. **Codificação Semântica com SNOMED CT**:
   - A taxonomia dos atos normativos é mapeada a códigos padronizados do SNOMED CT:
     - `308910008` (Clinical guidelines policy document) para portarias e protocolos.
     - `713426002` (Legal document) para decretos legislativos.
   - Comentários arquiteturais e diretrizes técnicas foram incluídos em `services/fhir_service.py` especificando como estender a plataforma com IA/NLP para identificação automática de termos clínicos (ex: Dengue, COVID-19) e integração com servidores de terminologia (ex: Ontoserver, Snowstorm).

---

## Arquitetura de UI Não-Bloqueante (2026)

A partir da versão atual, o processamento FHIR **não bloqueia** mais a renderização dos resultados da busca:

### Ordem de Renderização em `pages/home.py`

```
render_home()
  └── _render_intro()          # Hero institucional
  └── _render_filtros()        # Painel de filtros
  └── _executar_varredura()    # Busca DOU + DOE-SC (com st.status())
  └── _render_resultados()
        ├── Cabeçalho + contador de resultados
        ├── Cards de resultado (renderizados IMEDIATAMENTE)
        └── Expander FHIR (ao final, não-bloqueante)
              └── _build_fhir_bundle()  # @st.cache_data
```

### Função `_build_fhir_bundle()` com Cache

```python
@st.cache_data(show_spinner=False)
def _build_fhir_bundle(df_json: str) -> tuple[list, dict, str]:
    """
    Constrói FHIR Bundle com cache por DataFrame.
    - Prévia: primeiros 50 registros (exibido nos JSONs interativos)
    - Download: Bundle completo com todos os registros
    - Re-renders do Streamlit não reprocessam o Bundle se os dados não mudaram
    """
```

### Garantia de Isolamento FHIR

O `st.expander` FHIR é renderizado **após** todos os cards de resultado. Qualquer falha no processamento FHIR é capturada por um bloco `try-except` e exibida como `st.warning()` — **nunca bloqueando ou ocultando os resultados da busca**.

---

## Diretrizes de Desenvolvimento e Interface

### Correção de Renderização de HTML/CSS (Streamlit Markdown)

Ao injetar elementos HTML ou estilos CSS na interface utilizando `st.markdown(..., unsafe_allow_html=True)`, o parser de Markdown do Streamlit interpreta qualquer recuo de 4 ou mais espaços como uma instrução para renderizar texto literal (`<pre><code>`), quebrando o layout visual.

**Regra obrigatória**: Utilizar `textwrap.dedent()` em **todas** as strings multilinha HTML/CSS injetadas dentro de funções/condicionais Python. Para f-strings com interpolação de dados variáveis (como base64), usar string achatada (0 espaços de recuo) em chamada separada de `st.markdown()`.

```python
# ✅ CORRETO — CSS com dedent
st.markdown(textwrap.dedent("""\
    <style>
    .meu-card { padding: 1rem; }
    </style>"""), unsafe_allow_html=True)

# ✅ CORRETO — HTML com dado variável em string achatada
st.markdown(
f"""<div class="meu-card">
<img src="data:image/png;base64,{base64_data}">
</div>""", unsafe_allow_html=True)
```

Essa diretriz deve ser estritamente seguida em todas as views e componentes da aplicação.
