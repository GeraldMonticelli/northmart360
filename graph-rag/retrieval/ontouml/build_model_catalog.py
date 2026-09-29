from pathlib import Path
from rdflib import Graph
import requests

# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

MODELS_DIR = Path("corpus/ontouml-models/models")

FUSEKI_DATASET = "http://localhost:3030/ontouml"
CATALOG_GRAPH = "urn:ontouml:models"


def build_catalog() -> Graph:
    """
    Scan every OntoUML model directory and merge its metadata.ttl
    into one RDF graph.

    Invalid or missing metadata files are reported and skipped.
    """
    catalog = Graph()

    model_count = 0
    missing_count = 0
    error_count = 0

    for model_dir in sorted(MODELS_DIR.iterdir()):

        if not model_dir.is_dir():
            continue

        metadata_file = model_dir / "metadata.ttl"

        if not metadata_file.exists():
            print(f"[MISSING] {model_dir.name}/metadata.ttl")
            missing_count += 1
            continue

        try:
            model_graph = Graph()
            model_graph.parse(metadata_file, format="turtle")

            before = len(catalog)

            for triple in model_graph:
                catalog.add(triple)

            added = len(catalog) - before

            print(
                f"[OK] {model_dir.name:<40} "
                f"{len(model_graph):>4} triples "
                f"({added:>4} new)"
            )

            model_count += 1

        except Exception as exc:
            print(f"[ERROR] {model_dir.name}: {exc}")
            error_count += 1

    print()
    print("Catalog build complete")
    print("----------------------")
    print(f"Models loaded : {model_count}")
    print(f"Missing       : {missing_count}")
    print(f"Errors        : {error_count}")
    print(f"RDF triples   : {len(catalog)}")

    return catalog


def upload_catalog(catalog: Graph) -> None:
    """
    Replace <urn:ontouml:models> in Fuseki using SPARQL Update.
    """

    update_endpoint = FUSEKI_DATASET

    # 1. Remove the previous catalog
    response = requests.post(
        update_endpoint,
        data={"update": f"DROP SILENT GRAPH <{CATALOG_GRAPH}>"},
        timeout=120,
    )
    response.raise_for_status()

    # 2. Serialize the new catalog as N-Triples
    nt_data = catalog.serialize(format="nt")

    # 3. Insert into the named graph
    update = f"""
    INSERT DATA {{
        GRAPH <{CATALOG_GRAPH}> {{
            {nt_data}
        }}
    }}
    """

    response = requests.post(
        update_endpoint,
        data={"update": update},
        timeout=120,
    )
    response.raise_for_status()

    print()
    print(
        f"Uploaded {len(catalog)} triples "
        f"to <{CATALOG_GRAPH}>"
    )


if __name__ == "__main__":

    if not MODELS_DIR.exists():
        raise RuntimeError(
            f"Models directory not found: {MODELS_DIR.resolve()}"
        )

    catalog = build_catalog()
    upload_catalog(catalog)