import sys
from rdflib import Graph

if len(sys.argv) != 2:
    print("Usage: python scripts/sparql.py <query.sparql>")
    sys.exit(1)

g = Graph()

files = [
    "ontology/oscal-ontology.ttl",
    "ontology/cyfun-ontology.ttl",
    "ontology/cyfun-mapping-ontology.ttl",
    "instances/cyfun-2025.ttl",
    "instances/cis-controls-v8.1.ttl",
    "mappings/cyfun-crosswalk-operational.ttl",
]

for file in files:
    g.parse(file, format="turtle")

print(f"Graph loaded: {len(g):,} triples")

with open(sys.argv[1], encoding="utf-8") as f:
    query = f.read()

results = g.query(query)

print()

for row in results:
    print(" | ".join(str(v) for v in row))