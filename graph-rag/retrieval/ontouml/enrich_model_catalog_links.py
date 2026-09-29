from pathlib import Path

import requests
from rdflib import Graph, URIRef, Namespace
from rdflib.namespace import RDF


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

MODELS_DIR = Path("corpus/ontouml-models/models")

FUSEKI_DATASET = "http://localhost:3030/ontouml"
CATALOG_GRAPH = "urn:ontouml:models"

DCAT = Namespace("http://www.w3.org/ns/dcat#")
OK = Namespace("https://w3id.org/ontouml/knowledge#")


# ---------------------------------------------------------------------
# Build enrichment triples
# ---------------------------------------------------------------------

def build_links() -> Graph:
    """
    Build links between each official OntoUML catalog model URI
    and the local Fuseki named graph containing its ontology.
    """

    links = Graph()

    models_found = 0
    errors = 0

    for model_dir in sorted(MODELS_DIR.iterdir()):

        if not model_dir.is_dir():
            continue

        metadata_file = model_dir / "metadata.ttl"

        if not metadata_file.exists():
            print(f"[MISSING] {model_dir.name}/metadata.ttl")
            continue

        try:
            metadata = Graph()
            metadata.parse(metadata_file, format="turtle")

            datasets = list(
                metadata.subjects(RDF.type, DCAT.Dataset)
            )

            if not datasets:
                print(
                    f"[WARNING] {model_dir.name}: "
                    "no dcat:Dataset found"
                )
                continue

            local_graph = URIRef(
                f"urn:ontouml:model:{model_dir.name}"
            )

            for model_uri in datasets:
                links.add(
                    (model_uri, OK.localGraph, local_graph)
                )

                print(
                    f"[OK] {model_dir.name:<40} "
                    f"{model_uri} -> {local_graph}"
                )

                models_found += 1

        except Exception as exc:
            print(f"[ERROR] {model_dir.name}: {exc}")
            errors += 1

    print()
    print("Link generation complete")
    print("------------------------")
    print(f"Links generated : {len(links)}")
    print(f"Models found    : {models_found}")
    print(f"Errors          : {errors}")

    return links


# ---------------------------------------------------------------------
# Upload enrichment
# ---------------------------------------------------------------------

def upload_links(links: Graph) -> None:
    """
    Add localGraph links to the existing catalog graph.

    INSERT DATA is intentionally used: existing catalog metadata
    and model graphs are left untouched.
    """

    nt_data = links.serialize(format="nt")

    update = f"""
    INSERT DATA {{
        GRAPH <{CATALOG_GRAPH}> {{
            {nt_data}
        }}
    }}
    """

    response = requests.post(
        FUSEKI_DATASET,
        data={"update": update},
        timeout=120,
    )

    response.raise_for_status()

    print()
    print(
        f"Inserted {len(links)} localGraph links "
        f"into <{CATALOG_GRAPH}>"
    )


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

if __name__ == "__main__":

    if not MODELS_DIR.exists():
        raise RuntimeError(
            f"Models directory not found: {MODELS_DIR.resolve()}"
        )

    links = build_links()

    if not links:
        raise RuntimeError("No catalog links generated.")

    upload_links(links)