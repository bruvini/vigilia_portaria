"""
Interoperabilidade FHIR R4 / HL7 do Vigília.

Mapeia atos normativos para recursos DocumentReference (FHIR R4) e os agrupa
em um Bundle do tipo `message` com MessageHeader, para futura integração com
barramentos de saúde do SUS e o PEP municipal de Joinville.

Correções incorporadas (auditoria de 09/06/2026):
  - IDs de recurso são UUIDs puros (válidos em fullUrl `urn:uuid:`); o prefixo
    "docref-" foi removido por violar a RFC 4122.
  - Colisão de IDs eliminada: a semente do uuid5 combina link, título,
    descrição e data; sem nenhum desses, usa uuid4 (aleatório).
  - `DocumentReference.date` continua sendo o instante de criação do registro
    (semântica correta do FHIR), mas a data de publicação do ato agora é
    registrada em `content.attachment.creation`.
  - `datetime.utcnow()` (deprecado) substituído por datetime timezone-aware.
"""

from __future__ import annotations

import base64
import uuid
from datetime import datetime, timezone


def _instante_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _data_publicacao_iso(data_br: str) -> str:
    """Converte dd/mm/aaaa para aaaa-mm-dd; string vazia se inválida."""
    try:
        return datetime.strptime(data_br.strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
    except (ValueError, AttributeError):
        return ""


def _gerar_resource_id(link: str, titulo: str, descricao: str, data: str) -> str:
    """
    UUID determinístico a partir dos metadados do ato (estável entre execuções,
    sem colisões entre atos distintos). Sem metadados, UUID aleatório.
    """
    semente = "|".join([link or "", titulo or "", (descricao or "")[:300], data or ""])
    if semente.strip("|"):
        return str(uuid.uuid5(uuid.NAMESPACE_URL, semente))
    return str(uuid.uuid4())


def to_fhir_document_reference(ato: dict) -> dict:
    """
    Mapeia um ato normativo (esquema padronizado do Vigília) para um recurso
    FHIR DocumentReference (R4).
    """
    tipo = str(ato.get("tipo", "ATO")).upper()
    origem = str(ato.get("origem", "DOU"))
    titulo = str(ato.get("titulo", ""))
    descricao = str(ato.get("descricao") or ato.get("resumo") or "")
    link = str(ato.get("link", ""))
    data_pub = _data_publicacao_iso(str(ato.get("data", "")))

    # ----------------------------------------------------------------------
    # Codificação semântica (SNOMED CT)
    #   308910008 | Clinical guidelines policy document (portarias/protocolos)
    #   713426002 | Legal document (decretos, resoluções executivas)
    #   308912000 | Administrative policy document (editais)
    # Futura extensão com IA/NLP: mapear termos clínicos da descrição via
    # servidor de terminologia (Ontoserver/Snowstorm) — ver README.
    # ----------------------------------------------------------------------
    snomed_code, snomed_display = "308910008", "Clinical guidelines policy document"
    if "DECRETO" in tipo:
        snomed_code, snomed_display = "713426002", "Legal document"
    elif "EDITAL" in tipo:
        snomed_code, snomed_display = "308912000", "Administrative policy document"

    resource_id = _gerar_resource_id(link, titulo, descricao, data_pub)

    attachment: dict = {
        "contentType": "text/html",
        "url": link,
        "title": titulo,
    }
    if data_pub:
        attachment["creation"] = data_pub
    if descricao:
        attachment["data"] = base64.b64encode(descricao.encode("utf-8")).decode("ascii")

    return {
        "resourceType": "DocumentReference",
        "id": resource_id,
        "status": "current",
        "docStatus": "final",
        "type": {
            "coding": [{
                "system": "http://snomed.info/sct",
                "code": snomed_code,
                "display": snomed_display,
            }],
            "text": f"Ato Normativo Oficial - {tipo}",
        },
        "category": [{
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/v3-ActClass",
                "code": "DOC",
                "display": "document",
            }],
            "text": f"Publicação Oficial - {origem}",
        }],
        "subject": {
            "identifier": {
                "system": "https://sms.joinville.sc.gov.br",
                "value": "SMS-JOINVILLE",
            },
            "display": "Secretaria Municipal da Saúde de Joinville",
        },
        "date": _instante_utc(),
        "author": [{
            "display": ato.get("orgao") or ato.get("hierarquia") or "Gestão Pública de Saúde",
        }],
        "description": titulo,
        "content": [{"attachment": attachment}],
        "context": {
            "practiceSetting": {
                "coding": [{
                    "system": "http://snomed.info/sct",
                    "code": "394802001",
                    "display": "General medicine",
                }],
                "text": "Gestão de Saúde Pública e Convênios",
            },
        },
    }


def create_hl7_fhir_message_bundle(fhir_resources: list[dict]) -> dict:
    """
    Agrupa recursos DocumentReference em um Bundle FHIR do tipo `message`
    com MessageHeader (primeiro entry, conforme exige o padrão).
    """
    bundle_id = str(uuid.uuid4())
    message_header_id = str(uuid.uuid4())

    message_header = {
        "resourceType": "MessageHeader",
        "id": message_header_id,
        "eventUri": "urn:hl7-org:event:notification:document-published",
        "source": {
            "name": "Sistema Vigilia",
            "software": "Vigilia",
            "version": "2.0.0",
            "endpoint": "https://vigiliasms.web.app/fhir",
        },
        "destination": [{
            "name": "Prontuário Eletrônico Joinville (E-SUS / PEP)",
            "endpoint": "https://pep.joinville.sc.gov.br/fhir-listener",
        }],
        "focus": [
            {"reference": f"DocumentReference/{res.get('id')}"}
            for res in fhir_resources
        ],
    }

    bundle = {
        "resourceType": "Bundle",
        "id": bundle_id,
        "type": "message",
        "timestamp": _instante_utc(),
        "entry": [
            {"fullUrl": f"urn:uuid:{message_header_id}", "resource": message_header},
        ],
    }
    for res in fhir_resources:
        bundle["entry"].append({
            "fullUrl": f"urn:uuid:{res.get('id')}",
            "resource": res,
        })
    return bundle


def montar_bundle(registros: list[dict]) -> dict:
    """Atalho: converte registros do Vigília e devolve o Bundle completo."""
    recursos = [to_fhir_document_reference(r) for r in registros]
    return create_hl7_fhir_message_bundle(recursos)
