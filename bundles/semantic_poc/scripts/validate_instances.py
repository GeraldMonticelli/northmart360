from pathlib import Path

from pyshacl import validate
from rdflib import Graph


ROOT = Path(__file__).resolve().parent.parent

INSTANCES_FILE = ROOT / "src/ontology/northmart-instances.ttl"
SHAPES_FILE = ROOT / "generated/semantic_poc_shapes.ttl"
ONTOLOGY_FILE = ROOT / "generated/semantic_poc_gufo.ttl"


def main() -> None:

    data = Graph()
    data.parse(
        INSTANCES_FILE,
        format="turtle",
    )

    shapes = Graph()
    shapes.parse(
        SHAPES_FILE,
        format="turtle",
    )

    ontology = Graph()
    ontology.parse(
        ONTOLOGY_FILE,
        format="turtle",
    )

    print("NorthMart instance validation")
    print("=" * 70)
    print(f"Instance triples : {len(data)}")
    print(f"SHACL triples    : {len(shapes)}")
    print(f"Ontology triples : {len(ontology)}")
    print()

    conforms, results_graph, results_text = validate(
        data_graph=data,
        shacl_graph=shapes,
        ont_graph=ontology,
        inference="rdfs",
        advanced=True,
    )

    print("=" * 70)
    print(f"CONFORMS: {conforms}")
    print("=" * 70)

    if not conforms:
        print()
        print(results_text)


if __name__ == "__main__":
    main()
    