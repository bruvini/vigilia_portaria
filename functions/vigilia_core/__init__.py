"""
Núcleo compartilhado do Vigília.

Este pacote é a única fonte de verdade da lógica de varredura (DOU e DOE-SC),
do mapeamento FHIR e do relatório por e-mail. É consumido por:

  - functions/main.py        → API HTTP e função agendada (Firebase Cloud Functions)
  - views/home.py            → interface legada em Streamlit (execução local)
  - tests/                   → suíte pytest

Não depende de pandas nem de streamlit: todas as funções trabalham com
list[dict] usando o esquema padronizado descrito em `filtros.SCHEMA_CAMPOS`.
"""
