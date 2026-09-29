from pathlib import Path

from owlrl import DeductiveClosure, OWLRL_Semantics
from rdflib import Graph, Namespace, RDF, URIRef


ROOT = Path(__file__).resolve().parent.parent

ONTOLOGY = ROOT / "src/ontology/semantic_poc_gufo.ttl"
CRM = ROOT / "src/instances/crm.ttl"
ERP = ROOT / "src/instances/erp.ttl"

NM = Namespace("https://example.com#")


def short(graph: Graph, uri) -> str:
    return graph.namespace_manager.normalizeUri(uri)


def main() -> None:

    graph = Graph()

    # --------------------------------------------------------
    # Load semantic ontology
    # --------------------------------------------------------

    graph.parse(ONTOLOGY, format="turtle")

    # --------------------------------------------------------
    # Load the two independent source systems
    # --------------------------------------------------------

    graph.parse(CRM, format="turtle")
    graph.parse(ERP, format="turtle")

    graph.bind("nm", NM)

    print()
    print("TEST A — Semantic interoperability")
    print("=" * 70)

    print(f"Triples before reasoning: {len(graph)}")

    # --------------------------------------------------------
    # OWL/RDFS reasoning
    # --------------------------------------------------------

    DeductiveClosure(
        OWLRL_Semantics
    ).expand(graph)

    print(f"Triples after reasoning : {len(graph)}")

    print()
    print("Explicit/inferred semantic classification:")

    for entity in [
        URIRef("https://crm.example.com#P100"),
        URIRef("https://erp.example.com#ACME"),
    ]:
        print()
        print(short(graph, entity))

        for entity_type in graph.objects(entity, RDF.type):
            print(f"    rdf:type {short(graph, entity_type)}")
    # --------------------------------------------------------
    # One semantic query across both systems
    # --------------------------------------------------------

    queries = {
        "Customer": NM.Customer,
        "PersonCustomer": NM.PersonCustomer,
        "OrganizationCustomer": NM.OrganizationCustomer,
    }

    for label, semantic_type in queries.items():

        print()
        print(f"{label}:")

        for entity in graph.subjects(
            RDF.type,
            semantic_type,
        ):
            print(f"  - {short(graph, entity)}")


if __name__ == "__main__":
    main()