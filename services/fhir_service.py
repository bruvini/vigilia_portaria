"""
Serviço de Interoperabilidade e Padrões de Saúde do Vigília.

Este módulo realiza o mapeamento dos atos normativos extraídos para o padrão FHIR R4
(Fast Healthcare Interoperability Resources) através do recurso DocumentReference.
Além disso, estrutura a mensageria compatível com barramentos HL7 através de FHIR Message Bundles
e define as diretrizes para codificação clínica com o SNOMED CT.
"""

from __future__ import annotations

import base64
import uuid
from datetime import datetime, date
import pandas as pd
from typing import Any, Optional


def to_fhir_document_reference(act_data: dict | pd.Series) -> dict:
    """
    Mapeia um ato normativo/portaria para um recurso FHIR DocumentReference (R4).

    Este recurso descreve um documento administrativo ou clínico e facilita a
    interoperabilidade semântica e estrutural entre o sistema Vigília e plataformas
    como o e-SUS ou PEP municipal da Secretaria da Saúde de Joinville.
    """
    if isinstance(act_data, pd.Series):
        act_data = act_data.to_dict()

    tipo = str(act_data.get("tipo", "ATO")).upper()
    origem = str(act_data.get("origem", "DOU"))
    titulo = str(act_data.get("titulo", ""))
    descricao = str(act_data.get("descricao", act_data.get("resumo", "")))
    link = str(act_data.get("link", ""))
    hierarquia = str(act_data.get("hierarquia", ""))

    # -------------------------------------------------------------------------
    # CODIFICAÇÃO CLÍNICA E SEMÂNTICA (SNOMED CT)
    # -------------------------------------------------------------------------
    # Para conformidade com a portaria municipal e interoperabilidade do SUS,
    # associamos o tipo do ato a conceitos estruturados do SNOMED CT.
    # Em uma futura implementação de IA/NLP de processamento de linguagem natural:
    # 1. Utilizar um servidor de terminologia (ex: Ontoserver, Snowstorm) via API REST:
    #    GET /fhir/ValueSet/$expand?url=http://snomed.info/sct?fhir_vs=ecl/<expressao-ecl>
    # 2. Rastrear no 'descricao' menções a termos clínicos e mapear a IDs SNOMED CT, por exemplo:
    #    - "Dengue" -> SNOMED CT: 38362002 (Dengue)
    #    - "COVID-19" -> SNOMED CT: 840539006 (Disease caused by Severe acute respiratory syndrome coronavirus 2)
    #    - "Vacina" -> SNOMED CT: 787859002 (Vaccine product)
    #    - "Atenção Primária" -> SNOMED CT: 102002003 (Primary health care service)
    # -------------------------------------------------------------------------

    # Mapeamento do tipo de documento geral para código SNOMED CT correspondente
    # 308910008 | Clinical guidelines policy document (Portarias de saúde, protocolos clínicos)
    # 713426002 | Legal document (Decretos, resoluções executivas)
    snomed_code = "308910008"
    snomed_display = "Clinical guidelines policy document"

    if "DECRETO" in tipo:
        snomed_code = "713426002"
        snomed_display = "Legal document"
    elif "EDITAL" in tipo:
        snomed_code = "308912000"
        snomed_display = "Administrative policy document"

    # Geração do ID do recurso de forma determinística ou via UUID
    resource_id = f"docref-{uuid.uuid5(uuid.NAMESPACE_DNS, link or titulo)}"

    # Estruturação FHIR DocumentReference R4
    resource = {
        "resourceType": "DocumentReference",
        "id": resource_id,
        "status": "current",
        "docStatus": "final",
        "type": {
            "coding": [
                {
                    "system": "http://snomed.info/sct",
                    "code": snomed_code,
                    "display": snomed_display
                }
            ],
            "text": f"Ato Normativo Oficial - {tipo}"
        },
        "category": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/v3-ActClass",
                        "code": "DOC",
                        "display": "document"
                    }
                ],
                "text": f"Publicação Oficial - {origem}"
            }
        ],
        "subject": {
            # Vinculado ao contexto institucional da SMS Joinville
            "identifier": {
                "system": "https://sms.joinville.sc.gov.br",
                "value": "SMS-JOINVILLE"
            },
            "display": "Secretaria Municipal da Saúde de Joinville"
        },
        "date": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "author": [
            {
                "display": act_data.get("orgao") or act_data.get("hierarquia") or "Gestão Pública de Saúde"
            }
        ],
        "description": titulo,
        "content": [
            {
                "attachment": {
                    "contentType": "text/html",
                    "url": link,
                    "title": titulo
                }
            }
        ],
        "context": {
            "practiceSetting": {
                "coding": [
                    {
                        "system": "http://snomed.info/sct",
                        "code": "394802001",
                        "display": "General medicine"
                    }
                ],
                "text": "Gestão de Saúde Pública e Convênios"
            }
        }
    }

    # Se houver descrição, salvamos como anexo codificado em Base64 (padrão FHIR para inline data)
    if descricao:
        encoded_data = base64.b64encode(descricao.encode("utf-8")).decode("utf-8")
        resource["content"][0]["attachment"]["data"] = encoded_data

    # -------------------------------------------------------------------------
    # FUTURA INTEGRAÇÃO SNOMED CT: ANÁLISE DE CONCEITOS CLÍNICOS
    # -------------------------------------------------------------------------
    # Podemos estender este dicionário FHIR mapeando termos clínicos encontrados
    # na descrição. Um exemplo de extension em FHIR para codificação secundária:
    #
    # resource["extension"] = [{
    #     "url": "https://sms.joinville.sc.gov.br/fhir/StructureDefinition/snomed-clinical-finding",
    #     "valueCodeableConcept": {
    #         "coding": [{
    #             "system": "http://snomed.info/sct",
    #             "code": "38362002",
    #             "display": "Dengue"
    #         }]
    #     }
    # }]
    # -------------------------------------------------------------------------

    return resource


def create_hl7_fhir_message_bundle(fhir_resources: list[dict]) -> dict:
    """
    Cria uma mensagem FHIR baseada no padrão HL7 v3 / Messaging.
    Agrupa recursos DocumentReference em um Bundle do tipo 'message'
    com cabeçalho MessageHeader.
    """
    bundle_id = str(uuid.uuid4())
    message_header_id = str(uuid.uuid4())

    # MessageHeader define a origem, destino e evento da mensagem HL7/FHIR
    message_header = {
        "resourceType": "MessageHeader",
        "id": message_header_id,
        "eventUri": "urn:hl7-org:event:notification:document-published",
        "source": {
            "name": "Sistema Vigilia Portaria",
            "software": "Vigilia",
            "version": "1.0.0",
            "endpoint": "https://vigilia.joinville.sc.gov.br/fhir"
        },
        "destination": [
            {
                "name": "Prontuário Eletrônico Joinville (E-SUS / PEP)",
                "endpoint": "https://pep.joinville.sc.gov.br/fhir-listener"
            }
        ],
        "focus": [
            {
                "reference": f"DocumentReference/{res.get('id')}"
            }
            for res in fhir_resources
        ]
    }

    # Montagem do Bundle de Mensagem
    bundle = {
        "resourceType": "Bundle",
        "id": bundle_id,
        "type": "message",
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "entry": [
            {
                "fullUrl": f"urn:uuid:{message_header_id}",
                "resource": message_header
            }
        ]
    }

    # Adicionar cada recurso FHIR DocumentReference ao Bundle
    for res in fhir_resources:
        bundle["entry"].append({
            "fullUrl": f"urn:uuid:{res.get('id')}",
            "resource": res
        })

    return bundle
