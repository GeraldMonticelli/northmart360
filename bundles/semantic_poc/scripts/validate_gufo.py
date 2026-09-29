from pathlib import Path

from pyshacl import validate
from rdflib import Graph

ROOT = Path(__file__).resolve().parent.parent

GUFO_MODEL = ROOT / "src/ontology/ontology_example1.ttl"
GUFO_SHAPES = ROOT / "src/shapes/gufoshapes.ttl"

model = Graph()
model.parse(GUFO_MODEL, format="turtle")

shapes = Graph()
shapes.parse(GUFO_SHAPES, format="turtle")

conforms, results_graph, results_text = validate(
    data_graph=model,
    shacl_graph=shapes,
    inference="rdfs",
    advanced=True,
)

print(f"Conforms: {conforms}")
print()
print(results_text)