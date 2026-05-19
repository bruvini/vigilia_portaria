# Plataforma Vigília

Sistema institucional de inteligência e monitoramento automatizado de publicações
em diários oficiais — com varredura, filtragem por palavras-chave e geração de relatórios.

---

## Como executar localmente

### 1. Instale as dependências Python

```bash
pip install -r requirements.txt
```

### 2. Instale os navegadores do Playwright

O módulo de raspagem utiliza o Playwright para navegar dinamicamente no site do Diário
Oficial da União. Após instalar as dependências, execute obrigatoriamente:

```bash
python -m playwright install chromium
```

> Isso baixa o binário do Chromium necessário para a automação headless.

### 3. Execute a aplicação

```bash
streamlit run streamlit_app.py
```

---

## Tecnologias Utilizadas

| Biblioteca       | Finalidade                                               |
|------------------|----------------------------------------------------------|
| **Streamlit**    | Interface de usuário web interativa                      |
| **Pandas**       | Estruturação e filtragem dos dados extraídos             |
| **Playwright**   | Automação de navegador para raspagem de sites dinâmicos  |
| **BeautifulSoup4** | Suporte auxiliar a parsing HTML estático               |

---

## Estrutura do Projeto

```
vigilia_portaria/
├── streamlit_app.py        # Ponto de entrada da aplicação
├── requirements.txt        # Dependências do projeto
├── .streamlit/
│   └── config.toml         # Configuração do tema (Light Mode forçado)
├── assets/                 # Imagens e recursos estáticos
├── components/             # Componentes de UI reutilizáveis
│   ├── hero.py             # Banner de cabeçalho
│   ├── sidebar.py          # Barra lateral de navegação
│   ├── cards.py            # Cards informativos
│   └── footer.py           # Rodapé
├── pages/
│   └── home.py             # Página principal com filtros e resultados
├── services/
│   └── dou_service.py      # Motor de raspagem do DOU via Playwright
├── styles/
│   └── main.css            # Folha de estilos principal (Light Theme)
└── utils/
    └── helpers.py          # Funções utilitárias (ex: load_css)
```

---

## Como Funciona a Busca no DOU

### Fluxo de Execução

```
Usuário define:
  ├── Data da publicação
  ├── Palavras-chave (separadas por vírgula)
  └── Fontes de pesquisa

         ↓

services/dou_service.py
  ├── Acessa: https://www.in.gov.br/leiturajornal?data=DD-MM-YYYY&secao=do1
  ├── Aguarda carregamento dinâmico (JavaScript)
  ├── Aplica filtro de Órgão  → <select id="slcOrgs">  (Ministério da Saúde)
  ├── Aplica filtro de Tipo   → <select id="slcTipo">  (Portaria)
  ├── Extrai cada <div class="resultado">:
  │     ├── hierarquia  → <ol class="dou-hierarquia"> <li>
  │     ├── titulo      → <h5 class="title-marker"> <a>
  │     ├── link        → atributo href do <a>
  │     └── descricao   → <p class="abstract-marker">
  └── Cruza resultados com as palavras-chave fornecidas

         ↓

pages/home.py
  └── Exibe resultados em cards com palavras-chave destacadas em amarelo
```

### Parâmetros da Função Principal

```python
buscar_dou(
    data_publicacao: date,      # Data da edição
    palavras_chave: list[str],  # Termos de filtragem (case-insensitive)
    secao: str = "do1",         # Seção do DOU: do1 | do2 | do3
    orgao: str = "Ministério da Saúde",
    tipo_ato: str = "Portaria",
) -> pd.DataFrame
```

---

## Fontes de Pesquisa Disponíveis

| Fonte                          | Status           |
|--------------------------------|------------------|
| Diário Oficial da União (DOU)  | Disponível       |
| Diário Oficial de Santa Catarina | Em desenvolvimento |
| Diário Oficial de Joinville    | Em desenvolvimento |

---

*Secretaria Municipal de Saúde de Joinville — Unidade de Convênios e Parcerias*
