from pathlib import Path

from rdflib import Graph, Namespace, RDF, URIRef
from owlrl import DeductiveClosure, OWLRL_Semantics

ROOT = Path(__file__).resolve().parent.parent

GUFO = Namespace("http://purl.org/nemo/gufo#")
DOMAIN = ROOT / "src/ontology/semantic_poc_gufo.ttl"
INSTANCES = ROOT / "src/instances/northmart-instances.ttl"

NM = Namespace("https://example.com#")

graph = Graph()

graph.parse(DOMAIN, format="turtle")
graph.parse(INSTANCES, format="turtle")

print(f"Triples before reasoning: {len(graph)}")

DeductiveClosure(OWLRL_Semantics).expand(graph)

print(f"Triples after reasoning: {len(graph)}")

print("\nTypes inferred for Alice:")

gufo_categories = {
    GUFO.Kind,
    GUFO.Role,
    GUFO.RoleMixin,
    GUFO.Phase,
    GUFO.Category,
    GUFO.Mixin,
    GUFO.SubKind,
    GUFO.Relator,
}

for object_type in graph.objects(NM.Alice, RDF.type):

    # Cherche les rdf:type gUFO de la classe elle-même
    class_gufo_types = [
        gufo_type
        for gufo_type in graph.objects(object_type, RDF.type)
        if gufo_type in gufo_categories
    ]

    name = graph.namespace_manager.normalizeUri(object_type)

    if class_gufo_types:
        gufo_names = ", ".join(
            graph.namespace_manager.normalizeUri(t)
            for t in class_gufo_types
        )
        print(f"  - {name:<30} [{gufo_names}]")
    else:
        print(f"  - {name}")