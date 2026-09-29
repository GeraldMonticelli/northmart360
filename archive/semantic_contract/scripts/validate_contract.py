from pathlib import Path
import sys

from rdflib import Graph, RDF, OWL, RDFS, URIRef
from pyshacl import validate

ROOT = Path(__file__).resolve().parents[1]
CRM = ROOT / "domains" / "crm"
GOV = ROOT / "governance"

data = Graph()
for path, fmt in [
    (CRM / "1_ontology.jsonld", "json-ld"),
    (CRM / "2_alignment.jsonld", "json-ld"),
    (CRM / "3_physical-model.jsonld", "json-ld"),
    (GOV / "enterprise.ttl", "turtle"),
]:
    data.parse(path, format=fmt)

shapes = Graph().parse(GOV / "governance-shapes.ttl", format="turtle")

conforms, _, report_text = validate(
    data_graph=data,
    shacl_graph=shapes,
    inference="rdfs",
    abort_on_first=False,
)

print(report_text)

DP = "https://northmart.example/ontology/dataproduct#"
CRM_NS = "https://northmart.example/crm/"
ENT_NS = "https://northmart.example/enterprise/"
semantic_binding = URIRef(DP + "semanticBinding")

local_resources = (
    set(data.subjects(RDF.type, OWL.Class))
    | set(data.subjects(RDF.type, OWL.DatatypeProperty))
    | set(data.subjects(RDF.type, OWL.ObjectProperty))
)

errors = []

for physical, semantic in data.subject_objects(semantic_binding):
    if str(semantic).startswith(CRM_NS) and semantic not in local_resources:
        errors.append(
            f"Binding target does not exist in local ontology: "
            f"{physical} -> {semantic}"
        )

for local, target in data.subject_objects(RDFS.subClassOf):
    if str(local).startswith(CRM_NS) and str(target).startswith(ENT_NS):
        if (target, RDF.type, OWL.Class) not in data:
            errors.append(f"Enterprise class target does not exist: {target}")

for local, target in data.subject_objects(RDFS.subPropertyOf):
    if str(local).startswith(CRM_NS) and str(target).startswith(ENT_NS):
        if not any(data.triples((target, RDF.type, None))):
            errors.append(f"Enterprise property target does not exist: {target}")

if errors:
    print("\nCross-graph consistency errors:")
    for error in errors:
        print(f" - {error}")

if not conforms or errors:
    sys.exit(1)

print("\nCONTRACT VALID")
