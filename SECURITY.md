# Diretrizes de Segurança - Sistema Vigília

Este documento descreve as políticas de segurança e privacidade aplicadas ao sistema **Vigília**, com foco especial no tratamento e armazenamento de dados extraídos de portarias públicas, rastreamento de dados de saúde e mitigação de vulnerabilidades.

## 1. Proteção de Dados Extraídos

Embora as portarias e diários oficiais consultados sejam de domínio público, o sistema Vigília consolida essas informações de maneira estratégica para a **Secretaria Municipal da Saúde de Joinville**.

*   **Minimização de Dados Sensíveis:** O sistema Vigília **não** processa dados pessoais identificáveis (PII) de pacientes ou prontuários médicos. Em caso de portarias contendo dados sensíveis, as rotinas de NLP deverão anonimizar nomes e CPFs.
*   **Tratamento de Credenciais:** Nenhuma chave de API, credencial de banco de dados ou token de serviço deve ser exposta no código-fonte ou enviada para repositórios públicos. Utilize o arquivo `.env` para gerenciar variáveis de ambiente e configure o `.gitignore` adequadamente.
*   **Integridade do Schema FHIR/HL7:** Os dados exportados em formato FHIR/HL7 utilizam codificações criptográficas (ex: hashes UUID determinísticos a partir dos links oficiais dos atos) para garantir integridade e unicidade dos recursos documentais.

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

*   **Prevenção de Injeção de Código HTML:** Ao renderizar strings HTML com `st.markdown(..., unsafe_allow_html=True)`, garanta que o texto vindo das fontes (DOU/DOE) seja previamente limpo e higienizado para evitar injeção de scripts (XSS).
*   **Controle de TLS/SSL:** Todas as requisições feitas por serviços externos em `services/dou_service.py` e `services/doesc_service.py` devem, em ambientes de homologação e produção, validar os certificados SSL/TLS (`verify=True`).
*   **Atualização de Dependências:** Execute auditorias de dependências regularmente para assegurar a ausência de bibliotecas vulneráveis:
    ```bash
    pip install pip-audit
    pip-audit
    ```
