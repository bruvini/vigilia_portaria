# Diretrizes de Segurança - Sistema Vigília

Este documento descreve as políticas de segurança e privacidade aplicadas ao sistema **Vigília**, com foco especial no tratamento e armazenamento de dados extraídos de portarias públicas, rastreamento de dados de saúde e mitigação de vulnerabilidades.

## 1. Proteção de Dados Extraídos

Embora as portarias e diários oficiais consultados sejam de domínio público, o sistema Vigília consolida essas informações de maneira estratégica para a **Secretaria Municipal da Saúde de Joinville**.

*   **Minimização de Dados Sensíveis:** O sistema Vigília **não** processa dados pessoais identificáveis (PII) de pacientes ou prontuários médicos. Em caso de portarias contendo dados sensíveis, as rotinas de NLP deverão anonimizar nomes e CPFs.
*   **Tratamento de Credenciais:** Nenhuma chave de API, credencial de banco de dados ou token de serviço deve ser exposta no código-fonte ou enviada para repositórios públicos. Utilize o arquivo `.env` para gerenciar variáveis de ambiente e configure o `.gitignore` adequadamente.
*   **Integridade do Schema FHIR/HL7:** Os dados exportados em formato FHIR/HL7 utilizam UUIDs determinísticos (uuid5 sobre link + título + descrição + data do ato) para garantir integridade e unicidade dos recursos documentais, sem colisões entre atos distintos.

## 2. Reporte de Vulnerabilidades

Se você identificar uma vulnerabilidade de segurança neste projeto:

1.  **Não** abra uma Issue pública no GitHub.
2.  Envie um e-mail detalhado para a equipe de segurança da SMS Joinville: `seguranca.ti@joinville.sc.gov.br` (exemplo).
3.  Inclua no reporte:
    *   Descrição da vulnerabilidade.
    *   Passos para reproduzir o problema (PoC).
    *   Possível impacto.

Garantimos um retorno inicial em até 48 horas úteis e trabalharemos para lançar um hotfix em modo privado antes da divulgação pública.

## 3. Práticas de Codificação Segura

*   **Prevenção de Injeção de Código HTML (XSS):** Todo texto vindo das fontes (DOU/DOE) é higienizado antes da renderização: a SPA (`public/app.js`) monta o DOM exclusivamente via `textContent` (nunca `innerHTML` com dado bruto) e a interface Streamlit (`views/home.py`) aplica `html.escape` em todos os campos antes do `st.markdown(..., unsafe_allow_html=True)`. Mantenha esse padrão em qualquer nova view.
*   **Controle de TLS/SSL:** Todas as requisições de `functions/vigilia_core` validam certificados SSL/TLS (`verify=True`). Não há mais fallback silencioso: a repetição sem verificação só ocorre com a variável de ambiente `VIGILIA_SSL_FALLBACK=1` definida explicitamente, e gera aviso em log. Não defina essa variável em produção.
*   **Atualização de Dependências:** Execute auditorias de dependências regularmente para assegurar a ausência de bibliotecas vulneráveis:
    ```bash
    pip install pip-audit
    pip-audit
    ```

## 4. Conformidade LGPD e Bundle FHIR

*   **Download Local Apenas:** O Bundle FHIR gerado pelo sistema (arquivo `vigilia_fhir_bundle_DD-MM-YYYY.json`) é disponibilizado **exclusivamente para download local** pelo usuário autenticado. Na versão atual, nenhum dado é enviado automaticamente a servidores externos ou ao endpoint FHIR configurado no `MessageHeader` (`https://pep.joinville.sc.gov.br/fhir-listener`).
*   **Dados de Domínio Público:** As portarias e atos normativos contidos no Bundle são de domínio público (DOU/DOE-SC). O Bundle FHIR não deve ser distribuído em canais não autorizados caso contenha referências a dados pessoais identificáveis extraídos de portarias de pessoal.
*   **Minimização de Dados no FHIR:** O mapeamento `to_fhir_document_reference()` utiliza apenas metadados estruturais (título, hierarquia, link, tipo) e o texto da publicação codificado em Base64. Nenhum dado de paciente, CPF ou prontuário é processado.
*   **Retenção e Descarte:** O sistema não mantém mais cache local de edições (a antiga pasta `data/` foi descontinuada). Os resumos de execução gravados em `relatorios/` no Firestore contêm apenas contagens e metadados, sem dados pessoais.
*   **Firestore:** As regras (`firestore.rules`) negam todo acesso direto de clientes; leitura e escrita passam exclusivamente pela Cloud Function `api` (Admin SDK). A API pública não exige autenticação — caso o uso institucional exija restrição de acesso, implementar Firebase Authentication antes de expandir o escopo de dados.
*   **Base Legal LGPD (Lei 13.709/2018):** O processamento se enquadra no Art. 7º, II (cumprimento de obrigação legal) e Art. 7º, III (execução de políticas públicas de saúde), dispensando consentimento explícito para os dados de natureza pública.
