# Plataforma Vigília

Sistema institucional de inteligência e monitoramento automatizado de publicações
em diários oficiais — varredura automática do **DOU** e do **DOE-SC**, filtragem por
palavras-chave, interoperabilidade FHIR/HL7 e relatório diário por e-mail (preparado).

**Produção:** https://vigiliasms.web.app (Firebase Hosting + Cloud Functions)

---

## Arquitetura

```
vigilia_portaria/
├── firebase.json               # Hosting (site vigiliasms) + rewrites /api/** + Functions
├── .firebaserc                 # Projeto Firebase: pmj-sms
├── firestore.rules             # Acesso de clientes NEGADO (tudo passa pela API)
├── public/                     # SPA estática (Firebase Hosting)
│   ├── index.html              # Interface "Gazeta Oficial" + Firebase Analytics
│   ├── app.js                  # Busca, chips de palavras-chave, render seguro (anti-XSS)
│   └── styles.css              # Design system editorial (Fraunces/Public Sans/Spline Mono)
├── functions/                  # Cloud Functions (Python 3.12, 2ª geração)
│   ├── main.py                 # Função `api` (HTTP) + `relatorio_diario` (agendada)
│   ├── requirements.txt
│   └── vigilia_core/           # ★ NÚCLEO COMPARTILHADO (única fonte de verdade)
│       ├── dou.py              # Busca DOU via JSON embarcado do Liferay (seções 1-3)
│       ├── doesc.py            # Busca DOE-SC via endpoint oficial POST busca-materia
│       ├── filtros.py          # Filtragem unificada (acentos/case, OU/E), HTTP c/ retry
│       ├── fhir.py             # DocumentReference R4 + Message Bundle HL7
│       ├── relatorio.py        # Relatório HTML para e-mail
│       └── config_padrao.py    # Palavras-chave padrão e seeds da configuração
├── streamlit_app.py            # Interface Streamlit (execução LOCAL/legada)
├── views/home.py               # Página Streamlit (consome o mesmo vigilia_core)
├── components/                 # hero.py e footer.py (Streamlit)
├── tests/                      # Suíte pytest do núcleo (roda no CI)
└── verify.py                   # Verificação de sintaxe + marcadores de conflito
```

O núcleo de varredura vive em `functions/vigilia_core` e **não depende de pandas
nem de streamlit** — é o mesmo código que roda nas Cloud Functions, na interface
Streamlit local e nos testes.

---

## Como funciona a busca

### DOU (`vigilia_core/dou.py`)
O portal Liferay da Imprensa Nacional injeta os metadados completos da edição em
JSON na tag `<script id="params">` de `https://www.in.gov.br/leiturajornal`.
O serviço captura esse JSON via HTTP simples (sem navegador), varre as **seções
1, 2 e 3**, filtra pelo órgão (padrão: Ministério da Saúde) e aplica as
palavras-chave em memória. Deduplicação por link preserva matérias sem link.

### DOE-SC (`vigilia_core/doesc.py`)
Consome o endpoint oficial `POST https://portal.doe.sea.sc.gov.br/apis/busca-materia`
com paginação automática (todas as publicações do dia), e filtra localmente.

### Filtragem (`vigilia_core/filtros.py`)
- **Insensível a acentos e maiúsculas nas duas fontes** ("saude" ≡ "saúde").
- Operadores **OU** (qualquer termo) e **E** (todos os termos).
- Todo registro segue um esquema padronizado com todas as chaves sempre
  presentes como `str` (ver `SCHEMA_CAMPOS`).
- HTTP com retry/backoff. Fallback de SSL sem verificação **só** com a variável
  de ambiente `VIGILIA_SSL_FALLBACK=1` (ver SECURITY.md).

---

## Deploy no Firebase

### Pré-requisitos (uma única vez)

1. **Firebase CLI**: `npm install -g firebase-tools` e `firebase login`.
2. **Plano Blaze** no projeto `pmj-sms` — obrigatório porque as Cloud Functions
   fazem requisições a domínios externos (in.gov.br / doe.sea.sc.gov.br) e a
   função de relatório usa o Cloud Scheduler.
3. **Firestore** criado no projeto (modo produção; as rules deste repo negam
   acesso de clientes — todo acesso passa pela API).
4. O site `vigiliasms` já deve existir em Hosting
   (`firebase hosting:sites:create vigiliasms`, se ainda não existir).

### Comandos de deploy

```bash
# Tudo (hosting + functions + rules):
firebase deploy

# Apenas o site:
firebase deploy --only hosting:vigiliasms

# Apenas as funções:
firebase deploy --only functions
```

A SPA fica em **https://vigiliasms.web.app** e chama a API pela rota relativa
`/api/**` (rewrite do Hosting para a função `api` em `southamerica-east1`).

#### ⚠️ Windows com nome de usuário acentuado — use `deploy.ps1`

O Firebase CLI **falha ao publicar funções Python** quando o caminho do projeto
contém acentos (ex.: `C:\Users\USUÁRIO\...`): o Python informa o caminho real do
pacote e o CLI o corrompe (`USU�RIO`), resultando em
`can't open file ...serving.py`. A solução é deployar de um caminho 100% ASCII.

O script [`deploy.ps1`](deploy.ps1) automatiza isso (espelha o projeto para
`C:\vgl`, prepara o virtualenv e roda o `firebase deploy` de lá):

```powershell
./deploy.ps1                       # tudo
./deploy.ps1 -Only functions        # só funções
./deploy.ps1 -Only hosting:vigiliasms
```

> Em máquinas cujo caminho já é ASCII, o `firebase deploy` direto funciona e o
> script é dispensável. As funções também exigem um `functions/venv` com as
> dependências instaladas (o CLI usa esse venv para introspecção).

#### Acesso público da função (uma vez)

Funções de 2ª geração (Cloud Run) não nascem públicas. Conceda invocação
anônima à função `api` (necessário para o rewrite do Hosting):

```bash
gcloud run services add-iam-policy-binding api \
  --region=southamerica-east1 --member=allUsers --role=roles/run.invoker
```

> Sem `gcloud`, dá para fazer pela API REST do Cloud Run (`:setIamPolicy`) ou
> pelo console (Cloud Run → api → Permissions → add `allUsers` /
> `Cloud Run Invoker`). Já aplicado neste projeto.

---

## Configuração de palavras-chave (sem digitar toda vez)

As palavras-chave padrão ficam salvas no Firestore (`config/varredura`) e são
carregadas automaticamente na Mesa de Varredura a cada acesso:

- **Editar pela interface**: botão *Configurações* → *Palavras-chave padrão* →
  *Salvar configuração*.
- **Seed inicial**: `functions/vigilia_core/config_padrao.py`
  (atualmente: Joinville, convênio, saúde) — criado no Firestore na primeira
  chamada a `GET /api/config`.

---

## Relatório automático por e-mail

O envio usa **SMTP direto** (`vigilia_core/email_sender.py`, via `smtplib`) — sem
extensões externas, com controle total sobre o remetente. O e-mail sai com um
nome de exibição "bonito", ex.:
`Vigília · Diários Oficiais SMS Joinville <seu-email>`, e um corpo HTML
no estilo "Gazeta Oficial" (`vigilia_core/relatorio.py`).

A função agendada `relatorio_diario` roda **de hora em hora (dias úteis,
America/Sao_Paulo)** e só dispara o e-mail na **hora configurada** em
`config/relatorio.horario` — assim o horário é ajustável pela interface (dropdown
de horas) sem novo deploy. Fica **desativada por padrão** (só envia quando
`config/relatorio.ativo == true` e há destinatários), com guarda anti-reenvio no
mesmo dia. Há ainda o endpoint `POST /api/relatorio/testar` (botão **"Enviar teste
agora"** na SPA).

Regras fixas do e-mail:
- **Operador sempre `E`** (todos os termos) — independente do que estiver
  selecionado na busca manual do site.
- **Dia útil anterior**: como o envio ocorre de manhã, a edição varrida é a do
  último dia útil (segunda → sexta; pula feriados fixos). Não há envio em fins de
  semana (o cron é `1-5`).
- **Resiliente à IA**: se a síntese por IA falhar (sem cota, modelo sobrecarregado
  com `503`, etc.), o e-mail é enviado normalmente, apenas sem o bloco de síntese.
  O `vigilia_core/ia.py` ainda tenta novamente em erros transitórios (429/5xx).

### Configurar as credenciais SMTP (Firebase Secrets)

As credenciais **nunca** ficam no código — são Secrets do Firebase, injetados nas
funções em tempo de execução:

```bash
firebase functions:secrets:set VIGILIA_SMTP_HOST   # ex.: smtp.gmail.com
firebase functions:secrets:set VIGILIA_SMTP_PORT   # ex.: 587
firebase functions:secrets:set VIGILIA_SMTP_USER   # o e-mail de envio
firebase functions:secrets:set VIGILIA_SMTP_PASS   # senha SMTP / "Senha de app"
firebase functions:secrets:set VIGILIA_SMTP_FROM   # ex.: Vigília · Diários Oficiais SMS Joinville
```

> **Gmail:** ative a verificação em 2 etapas e gere uma **Senha de app**
> (https://myaccount.google.com/apppasswords) — use-a em `VIGILIA_SMTP_PASS`.
> Host `smtp.gmail.com`, porta `587`.

Depois de definir os secrets, refaça o deploy das funções (`firebase deploy
--only functions`). Na SPA: *Configurações* → adicione destinatários → *Salvar
relatório* / *Enviar teste agora*. Cada envio grava um resumo em
`relatorios/{AAAA-MM-DD}` para auditoria.

---

## API (Cloud Function `api`)

| Método | Rota          | Descrição                                              |
|--------|---------------|--------------------------------------------------------|
| GET    | /api/health   | Verificação de disponibilidade                          |
| GET    | /api/config   | Configuração atual (cria padrões na primeira chamada)   |
| POST   | /api/config   | Salva `{varredura:{...}, relatorio:{...}}`              |
| POST   | /api/buscar   | `{data:"AAAA-MM-DD", palavras:[...], operador, fontes}` |
| POST   | /api/fhir     | `{resultados:[...]}` → FHIR Message Bundle              |
| POST   | /api/relatorio/testar | `{destinatarios:[...], data}` → envia o relatório agora |

> A API não exige autenticação (mesmo nível de acesso público da versão
> anterior). Se o uso institucional exigir restrição, adicione Firebase
> Authentication na SPA e verificação de ID token na função.

---

## Execução local

### Interface Streamlit (legada)
```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

### Testes
```bash
pip install requests beautifulsoup4 pytest
python verify.py      # sintaxe + marcadores de conflito
pytest tests/ -v      # suíte do núcleo (sem rede)
```

### Emulador Firebase (SPA + funções)
```bash
firebase emulators:start --only hosting,functions,firestore
```

---

## Interoperabilidade FHIR / HL7 / SNOMED CT

Cada ato é mapeado para um `DocumentReference` (FHIR R4) com:
- **SNOMED CT** no `type`: 308910008 (portarias/protocolos), 713426002
  (decretos), 308912000 (editais);
- data de publicação do ato em `content.attachment.creation` e texto integral
  em Base64 (`content.attachment.data`);
- IDs UUID determinísticos (uuid5 de link+título+descrição+data — estáveis
  entre execuções e sem colisões).

Os recursos são agrupados em um `Bundle` tipo `message` com `MessageHeader`
(primeiro entry, `fullUrl` no formato `urn:uuid:` válido), pronto para envio a
barramentos do SUS / PEP municipal. Extensão futura com NLP + servidor de
terminologia (Ontoserver/Snowstorm) está documentada em `vigilia_core/fhir.py`.

---

## Síntese por IA (Google AI Studio / Gemini) — ATIVA

O módulo `vigilia_core/ia.py` gera um **resumo executivo** das publicações
(quantas foram encontradas, o que dizem e por que importam para Joinville),
exibido **no painel do site** e **no topo do relatório por e-mail**.

Controle: toggle *Síntese por IA* em *Configurações* (campo `resumo_ia` em
`config/relatorio`). Fica inerte se a `GEMINI_API_KEY` não estiver configurada.

- **Site:** quando a IA está ligada, os resultados só aparecem **junto com a
  síntese** — durante a espera, um loader com barra de progresso e frases de
  efeito é exibido. Se a IA falhar/sem cota, os resultados aparecem mesmo assim.
  O endpoint `POST /api/sintese` cacheia por busca na coleção `sinteses`.
- **E-mail:** a síntese entra no relatório quando `resumo_ia` está ligado.
- **Modelo:** `gemini-2.5-flash` (`ia.MODELO_PADRAO`), com *thinking* desligado
  para não truncar a resposta. Limites de volume controlam custo/latência.

Para (re)configurar a chave: `firebase functions:secrets:set GEMINI_API_KEY` e
redeploy das funções. Observação: o `gemini-2.0-flash` perdeu cota no free tier
(erro 429 `limit: 0`) — por isso o padrão é o `2.5-flash`.

---

*Secretaria Municipal de Saúde de Joinville — Unidade de Convênios e Parcerias*
*Desenvolvido por Enf. Bruno Vinícius*
