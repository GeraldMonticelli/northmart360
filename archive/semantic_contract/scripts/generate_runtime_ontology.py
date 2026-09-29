from pathlib import Path
from rdflib import Graph

ROOT = Path(__file__).resolve().parent.parent

sources = [
    ROOT / "governance" / "enterprise.ttl",
    ROOT / "domains" / "crm" / "1_ontology.jsonld",
    ROOT / "domains" / "crm" / "2_alignment.jsonld",
]

output = ROOT / "generated" / "runtime_ontology.ttl"

graph = Graph()

for source in sources:
    print(f"Loading {source.relative_to(ROOT)}")
    graph.parse(source)

graph.serialize(destination=output, format="turtle")

print(f"\nGenerated: {output.relative_to(ROOT)}")
print(f"Triples: {len(graph)}")