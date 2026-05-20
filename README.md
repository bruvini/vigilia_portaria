# Plataforma Vigília

Sistema institucional de inteligência e monitoramento automatizado de publicações
em diários oficiais — com varredura automática, filtragem por palavras-chave e geração de relatórios.

---

## Como executar localmente

### 1. Instale as dependências Python

```bash
pip install -r requirements.txt
```

### 2. Instale os navegadores do Playwright

O Playwright utiliza um navegador Chromium headless para automação dos portais dinâmicos.
Execute obrigatoriamente **uma vez** após a instalação:

```bash
python -m playwright install chromium
```

### 3. Execute a aplicação

```bash
streamlit run streamlit_app.py
```

---

## Tecnologias Utilizadas

| Biblioteca         | Finalidade                                               |
|--------------------|----------------------------------------------------------|
| **Streamlit**      | Interface de usuário web interativa                      |
| **Pandas**         | Estruturação e filtragem dos dados extraídos             |
| **Playwright**     | Automação de navegador para portais dinâmicos (DOU e DOE-SC) |
| **BeautifulSoup4** | Suporte auxiliar a parsing HTML estático                 |

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
│   ├── dou_service.py          # Motor de raspagem do DOU (Playwright)
│   └── doesc_service.py        # Motor de raspagem do DOE-SC (Playwright + Angular)
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

### Complexidade Técnica

O portal do Diário Oficial de Santa Catarina é uma aplicação **Angular + PrimeNG** altamente dinâmica.
Não existe uma API pública ou endpoint REST simples — toda interação ocorre via manipulação
de componentes Angular renderizados no cliente.

### Fluxo de Automação (Playwright Headless)

```
services/doesc_service.py
  ├── URL: https://portal.doe.sea.sc.gov.br/v2.43.01/#/portal
  ├── Aguarda Angular bootstrap (networkidle + buffer)
  │
  ├── [ETAPA 1] Navegar até Buscar Edições
  │     └── Clica em <a:has-text('Buscar Edições')>
  │
  ├── [ETAPA 2] Aplicar Filtro de Data
  │     ├── Abre modal: button:has(.pi-filter)
  │     ├── Preenche Data Início → p-dialog p-calendar:first-of-type input
  │     ├── Preenche Data Fim   → p-dialog p-calendar:last-of-type input
  │     └── Clica em Aplicar   → .p-dialog-footer button:last-of-type
  │
  ├── [ETAPA 3] Listar Edições (Ordinária + Extra)
  │     └── Cards em .p-dataview-content .col-12
  │
  └── [ETAPA 4] Para cada edição:
        ├── Clica em "Abrir"   → button:has-text('Abrir')
        ├── Seleciona formato  → button.btn-extrato (Extrato de Publicação Certificada)
        │
        └── Para cada categoria-alvo ("Saúde", "Joinville"):
              ├── Seleciona no p-dropdown (.p-dropdown-label)
              ├── Lista assuntos começando com "PORTARIA"
              ├── Para cada assunto:
              │     ├── Seleciona o assunto
              │     ├── Extrai atos da lista de <section>
              │     ├── Abre detalhe via "Saiba mais" (se disponível)
              │     ├── Extrai texto via p.white-space-pre-wrap (ou fallback)
              │     ├── Filtra pelo padrão de palavras-chave (regex)
              │     └── Retorna ao clique "Voltar"
              └── Limpa seleção de categoria ao finalizar
```

### Seletores Validados (Angular/PrimeNG)

| Elemento                  | Seletor Playwright                                      |
|---------------------------|---------------------------------------------------------|
| Buscar Edições            | `a:has-text('Buscar Edições')`                          |
| Botão de Filtros          | `button:has(.pi-filter)`                                |
| Data Início (modal)       | `p-dialog p-calendar:first-of-type input`               |
| Data Fim (modal)          | `p-dialog p-calendar:last-of-type input`                |
| Botão Aplicar (modal)     | `.p-dialog-footer button:last-of-type`                  |
| Card de Edição (Abrir)    | `button:has-text('Abrir')`                              |
| Formato Extrato           | `button.btn-extrato`                                    |
| Dropdown Categoria        | `.p-dropdown-label` com texto do placeholder            |
| Opções do Dropdown        | `.p-dropdown-item`                                      |
| Texto do Detalhe          | `p.white-space-pre-wrap`, `p.text-justify`              |
| Voltar                    | `button:has-text('Voltar')`                             |

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
