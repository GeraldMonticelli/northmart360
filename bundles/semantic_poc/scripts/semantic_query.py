from pathlib import Path
from collections import deque

import yaml
from rdflib import Graph, Namespace, RDF, RDFS


ROOT = Path(__file__).resolve().parent.parent

ONTOLOGY = ROOT / "src/ontology/semantic_poc_gufo.ttl"
MAPPING = ROOT / "src/semantic/mappings.yml"

DOMAIN = Namespace("https://example.com#")
GUFO = Namespace("http://purl.org/nemo/gufo#")


# ---------------------------------------------------------
# Load ontology
# ---------------------------------------------------------

g = Graph()
g.parse(ONTOLOGY, format="turtle")

with MAPPING.open(encoding="utf-8") as f:
    mapping = yaml.safe_load(f)


# ---------------------------------------------------------
# Build a semantic graph FROM OWL
# ---------------------------------------------------------

edges = {}


def add_edge(a, b, reason):
    edges.setdefault(a, []).append((b, reason))
    edges.setdefault(b, []).append((a, reason))


# 1. Generalizations
#
# PersonCustomer rdfs:subClassOf Person
# PersonCustomer rdfs:subClassOf Customer
#
for child, parent in g.subject_objects(RDFS.subClassOf):

    if not (
        str(child).startswith(str(DOMAIN))
        and str(parent).startswith(str(DOMAIN))
    ):
        continue

    child_name = str(child).split("#")[-1]
    parent_name = str(parent).split("#")[-1]

    add_edge(
        child_name,
        parent_name,
        "rdfs:subClassOf",
    )


# 2. gUFO mediations
#
# Find ObjectProperties that are subproperties of gufo:mediates
#
for prop in g.subjects(
    RDFS.subPropertyOf,
    GUFO.mediates,
):

    domain = g.value(prop, RDFS.domain)
    range_ = g.value(prop, RDFS.range)

    if domain is None or range_ is None:
        continue

    domain_name = str(domain).split("#")[-1]
    range_name = str(range_).split("#")[-1]

    add_edge(
        domain_name,
        range_name,
        "gufo:mediates",
    )


# ---------------------------------------------------------
# Find semantic path
# ---------------------------------------------------------

def find_path(start, target):

    queue = deque([
        (start, [])
    ])

    visited = set()

    while queue:

        current, path = queue.popleft()

        if current == target:
            return path

        if current in visited:
            continue

        visited.add(current)

        for neighbour, reason in edges.get(current, []):

            queue.append(
                (
                    neighbour,
                    path + [
                        (current, neighbour, reason)
                    ],
                )
            )

    return None


path = find_path("Card", "Person")


print("\nSEMANTIC GRAPH EXTRACTED FROM OWL")
print("---------------------------------")

for source in sorted(edges):
    for target, reason in edges[source]:
        if source < target:
            print(
                f"{source:20} --[{reason}]--> {target}"
            )


print("\nPATH DISCOVERED BY THE ONTOLOGY")
print("--------------------------------")

if path is None:
    print("NO PATH")
else:
    print(path[0][0], end="")

    for source, target, reason in path:
        print(
            f" --[{reason}]--> {target}",
            end="",
        )

    print()