from pathlib import Path
import sys

from rdflib import Graph, RDF, RDFS, OWL, URIRef


ROOT = Path(__file__).resolve().parent.parent

LOCAL_ONTOLOGY = ROOT / "domains/crm/1_ontology.jsonld"
ALIGNMENT = ROOT / "domains/crm/2_alignment.jsonld"
PHYSICAL_MODEL = ROOT / "domains/crm/3_physical-model.jsonld"
ENTERPRISE_ONTOLOGY = ROOT / "governance/enterprise.ttl"


def load(path: Path) -> Graph:
    graph = Graph()
    graph.parse(path)
    return graph


def declared_resources(graph: Graph) -> set[URIRef]:
    """Classes and properties explicitly declared in an ontology."""
    accepted_types = {
        OWL.Class,
        RDFS.Class,
        OWL.ObjectProperty,
        OWL.DatatypeProperty,
        RDF.Property,
    }

    return {
        subject
        for subject, _, resource_type in graph.triples((None, RDF.type, None))
        if isinstance(subject, URIRef)
        and resource_type in accepted_types
    }


def main() -> None:
    local = load(LOCAL_ONTOLOGY)
    alignment = load(ALIGNMENT)
    physical = load(PHYSICAL_MODEL)
    enterprise = load(ENTERPRISE_ONTOLOGY)

    local_resources = declared_resources(local)
    enterprise_resources = declared_resources(enterprise)

    errors = []

    # ---------------------------------------------------------
    # 1. Alignment:
    #    every source must exist in the local ontology
    #    every target must exist in the enterprise ontology
    # ---------------------------------------------------------

    alignment_predicates = {
        RDFS.subClassOf,
        RDFS.subPropertyOf,
        OWL.equivalentClass,
        OWL.equivalentProperty,
    }

    for source, predicate, target in alignment:
        if predicate not in alignment_predicates:
            continue

        if source not in local_resources:
            errors.append(
                f"Alignment source not declared locally: {source}"
            )

        if not isinstance(target, URIRef):
            errors.append(
                f"Alignment target is not an IRI: {target}"
            )
        elif target not in enterprise_resources:
            errors.append(
                f"Alignment target not declared in enterprise ontology: "
                f"{target}"
            )

    # ---------------------------------------------------------
    # 2. Physical semanticBinding:
    #    every binding must resolve to a local semantic resource
    # ---------------------------------------------------------

    semantic_binding = URIRef(
        "https://northmart.example/ontology/dataproduct#semanticBinding"
    )

    for physical_resource, _, semantic_resource in physical.triples(
        (None, semantic_binding, None)
    ):
        if not isinstance(semantic_resource, URIRef):
            errors.append(
                f"semanticBinding of {physical_resource} is not an IRI"
            )
        elif semantic_resource not in local_resources:
            errors.append(
                f"semanticBinding target not declared locally: "
                f"{physical_resource} -> {semantic_resource}"
            )

    # ---------------------------------------------------------
    # Result
    # ---------------------------------------------------------

    if errors:
        print("\nSEMANTIC REFERENCE VALIDATION FAILED\n")

        for error in errors:
            print(f"✗ {error}")

        sys.exit(1)

    print("Semantic references valid.")
    print(f"Local declared resources:      {len(local_resources)}")
    print(f"Enterprise declared resources: {len(enterprise_resources)}")
    print("✓ SEMANTIC REFERENCES VALID")


if __name__ == "__main__":
    main()