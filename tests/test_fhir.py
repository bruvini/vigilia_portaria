"""Testes do mapeamento FHIR (vigilia_core.fhir)."""

import base64
import re
import uuid

from vigilia_core.fhir import (
    create_hl7_fhir_message_bundle,
    montar_bundle,
    to_fhir_document_reference,
)

RE_URN_UUID = re.compile(
    r"^urn:uuid:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


def _ato(**kwargs):
    return {
        "tipo": "PORTARIA",
        "origem": "DOU",
        "titulo": "Portaria X",
        "descricao": "texto da portaria",
        "link": "https://in.gov.br/x",
        "hierarquia": "MS",
        "orgao": "Ministério da Saúde",
        "data": "09/06/2026",
        **kwargs,
    }


def test_id_e_uuid_valido():
    recurso = to_fhir_document_reference(_ato())
    uuid.UUID(recurso["id"])  # levanta ValueError se inválido


def test_ids_determinsticos_e_sem_colisao():
    r1 = to_fhir_document_reference(_ato())
    r2 = to_fhir_document_reference(_ato())
    assert r1["id"] == r2["id"]  # determinístico para o mesmo ato

    # atos distintos SEM link e SEM título não podem colidir (bug histórico)
    a3 = to_fhir_document_reference(_ato(titulo="", link="", descricao="texto A"))
    a4 = to_fhir_document_reference(_ato(titulo="", link="", descricao="texto B"))
    assert a3["id"] != a4["id"]


def test_data_publicacao_em_attachment_creation():
    recurso = to_fhir_document_reference(_ato())
    attachment = recurso["content"][0]["attachment"]
    assert attachment["creation"] == "2026-06-09"
    assert base64.b64decode(attachment["data"]).decode("utf-8") == "texto da portaria"


def test_data_invalida_nao_quebra():
    recurso = to_fhir_document_reference(_ato(data="não-é-data"))
    assert "creation" not in recurso["content"][0]["attachment"]


def test_snomed_por_tipo():
    assert to_fhir_document_reference(_ato())["type"]["coding"][0]["code"] == "308910008"
    assert to_fhir_document_reference(_ato(tipo="DECRETO"))["type"]["coding"][0]["code"] == "713426002"
    assert to_fhir_document_reference(_ato(tipo="EDITAL"))["type"]["coding"][0]["code"] == "308912000"


def test_bundle_message_header_primeiro_e_fullurls_validos():
    recursos = [to_fhir_document_reference(_ato()),
                to_fhir_document_reference(_ato(titulo="Portaria Y", link="https://in.gov.br/y"))]
    bundle = create_hl7_fhir_message_bundle(recursos)
    assert bundle["type"] == "message"
    assert bundle["entry"][0]["resource"]["resourceType"] == "MessageHeader"
    assert len(bundle["entry"]) == 3
    for entry in bundle["entry"]:
        assert RE_URN_UUID.match(entry["fullUrl"]), entry["fullUrl"]


def test_montar_bundle_atalho():
    bundle = montar_bundle([_ato()])
    assert bundle["resourceType"] == "Bundle"
    assert len(bundle["entry"]) == 2
