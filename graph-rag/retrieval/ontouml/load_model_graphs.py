from pathlib import Path
from urllib.parse import quote

import requests
from rdflib import Graph


MODELS_DIR = Path("corpus/ontouml-models/models")
FUSEKI_DATASET = "http://localhost:3030/ontouml"


def graph_iri(model_name: str) -> str:
    return f"urn:ontouml:model:{quote(model_name, safe='-_')}"


def upload_model(model_dir: Path) -> tuple[str, int]:
    ontology_file = model_dir / "ontology.ttl"

    if not ontology_file.exists():
        raise FileNotFoundError(ontology_file)

    # Parse first: we don't upload invalid Turtle.
    graph = Graph()
    graph.parse(ontology_file, format="turtle")

    target_graph = graph_iri(model_dir.name)

    # N-Triples is convenient inside INSERT DATA.
    triples = graph.serialize(format="nt")

    # Idempotent replacement of this model only.
    update = f"""
    DROP SILENT GRAPH <{target_graph}>;

    INSERT DATA {{
      GRAPH <{target_graph}> {{
        {triples}
      }}
    }}
    """

    response = requests.post(
        FUSEKI_DATASET,
        data={"update": update},
        timeout=120,
    )
    response.raise_for_status()

    return target_graph, len(graph)


def main():
    loaded = 0
    missing = 0
    errors = 0
    total_triples = 0

    for model_dir in sorted(MODELS_DIR.iterdir()):
        if not model_dir.is_dir():
            continue

        ontology_file = model_dir / "ontology.ttl"

        if not ontology_file.exists():
            print(f"[MISSING] {model_dir.name}/ontology.ttl")
            missing += 1
            continue

        try:
            target_graph, count = upload_model(model_dir)

            print(
                f"[OK] {model_dir.name:<40} "
                f"{count:>6} triples -> {target_graph}"
            )

            loaded += 1
            total_triples += count

        except Exception as exc:
            print(f"[ERROR] {model_dir.name}: {exc}")
            errors += 1

    print()
    print("Model graph loading complete")
    print("----------------------------")
    print(f"Models loaded : {loaded}")
    print(f"Missing       : {missing}")
    print(f"Errors        : {errors}")
    print(f"RDF triples   : {total_triples}")


if __name__ == "__main__":
    main()