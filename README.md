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
├── streamlit_app.py            # Ponto de entrada da aplicação
├── requirements.txt            # Dependências do projeto
├── .streamlit/
│   └── config.toml             # Configuração do tema (Light Mode forçado)
├── assets/                     # Imagens e recursos estáticos
├── components/                 # Componentes de UI reutilizáveis
│   ├── hero.py                 # Banner de cabeçalho
│   ├── sidebar.py              # Barra lateral de navegação
│   ├── cards.py                # Cards informativos
│   └── footer.py               # Rodapé
├── pages/
│   └── home.py                 # Página principal com filtros, orquestração e resultados
├── services/
│   ├── dou_service.py          # Motor de busca do DOU via Liferay Script
│   └── doesc_service.py        # Motor de busca do DOE-SC via API REST CKAN pública
├── styles/
│   └── main.css                # Folha de estilos principal (Light Theme)
└── utils/
    └── helpers.py              # Funções utilitárias (ex: load_css)
```

---

## Fontes de Pesquisa Disponíveis

| Fonte                            | Status             |
|----------------------------------|--------------------|
| Diário Oficial da União (DOU)    | Disponível         |
| Diário Oficial de Santa Catarina (DOE-SC) | Disponível  |
| Diário Oficial de Joinville      | Em desenvolvimento |

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

O portal de dados abertos de Santa Catarina disponibiliza a base de publicações oficiais estruturada em formato CKAN. Abandonamos o uso do Playwright e da raspagem do portal Angular do DOE-SC para consumir diretamente essa API, garantindo performance e estabilidade.

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
buscar_dou(
    data_publicacao: date,       # Data da edição
    palavras_chave: list[str],   # Termos de filtragem (case-insensitive)
    secao: str = "do1",          # Seção: do1 | do2 | do3
    orgao: str = "Ministério da Saúde",
    tipo_ato: str = "Portaria",
) -> pd.DataFrame

# DOE-SC
buscar_doesc(
    data_publicacao: date,       # Data da edição
    palavras_chave: list[str],   # Termos de filtragem (case-insensitive)
) -> pd.DataFrame
# Categorias internas pesquisadas: "Saúde" e "Joinville"
# Assuntos pesquisados: todos que começam com "PORTARIA"
```

---

*Secretaria Municipal de Saúde de Joinville — Unidade de Convênios e Parcerias*

---

## Regras Visuais de Exibição e Interface

A interface da Plataforma Vigília foi refatorada e harmonizada seguindo diretrizes visuais unificadas:

1. **Cards Selecionáveis na Barra Lateral (Sidebar)**:
   - Substituição do seletor multiselect por cards informativos verticais (`st.container(border=True)`) com checkbox de seleção.
   - Textos explicativos para cada Diário Oficial indicando as regras de varredura executadas pelo robô Vigília.

2. **Exibição Harmonizada**:
   - Todo resultado é renderizado em um card padronizado (`st.container(border=True)`).
   - Metadados exibidos no cabeçalho: Hierarquia da publicação, data e um badge colorido que indica a origem (DOU, DOE-SC, etc.).

3. **Links e Texto Integral**:
   - **Diário Oficial da União (DOU)**: Título clicável com link externo de redirecionamento.
   - **Diário Oficial de Santa Catarina (DOE-SC)**: Texto integral ocultado por padrão e exibido sob demanda através de um componente expansível (`st.expander`), mantendo o layout limpo e legível.

4. **Identificação de Município**:
   - Varredura de texto simples no ato da renderização dos resultados do DOE-SC. Se houver menção à cidade de **Joinville**, um badge estilizado azul destacado é adicionado ao lado do título: `📍 Município: Joinville`.
