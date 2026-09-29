import json
import sys

from openai import OpenAI
from rdflib import Graph, Namespace, RDF

# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------

MODEL = "gpt-5.6"

OSCAL = Namespace("https://example.org/oscal#")
POC = Namespace("https://example.org/cyfun-poc#")
STIB = Namespace("https://example.org/stib/")

client = OpenAI()

# ------------------------------------------------------------------
# Load the complete knowledge graph
# ------------------------------------------------------------------

g = Graph()

g.parse("ontology/oscal-ontology.ttl")
g.parse("instances/cyfun-essential.ttl")
g.parse("mappings/cyfun-poc.ttl")
g.parse("instances/stib-poc.ttl")

print(f"Knowledge graph loaded: {len(g)} triples")


# ------------------------------------------------------------------
# STEP 1 — LLM understands the question
# ------------------------------------------------------------------

def understand_question(question: str) -> dict:

    prompt = f"""
You are a query planner for a cybersecurity knowledge graph.

Extract the entities and cybersecurity concepts mentioned or implied
by the user's question.

Return ONLY valid JSON with this structure:

{{
  "entities": [],
  "concepts": []
}}

Possible concepts include:
InformationFlow
DataFlowMapping
Encryption
Monitoring
NetworkSecurity
NetworkSegmentation
Authentication
IdentityAccessManagement
VulnerabilityManagement
Logging
IncidentManagement
Recovery
Backup
DataProtection

Examples of entities:
Payment Backend
API Management Gateway
Payment PostgreSQL Database

QUESTION:
{question}
"""

    response = client.responses.create(
        model=MODEL,
        input=prompt,
    )

    return json.loads(response.output_text)


# ------------------------------------------------------------------
# STEP 2 — find matching STIB resources
# ------------------------------------------------------------------

def find_entities(entity_names: list[str]) -> set:

    resources = set()

    for name in entity_names:

        name_lower = name.lower()

        for subject, _, label in g.triples((None, POC.name, None)):

            if (
                name_lower in str(label).lower()
                or str(label).lower() in name_lower
            ):
                resources.add(subject)

    return resources


# ------------------------------------------------------------------
# STEP 3 — retrieve neighbourhood around STIB entities
# ------------------------------------------------------------------

def expand_neighbourhood(resources: set, depth: int = 2) -> set:

    triples = set()
    frontier = set(resources)
    visited = set()

    for _ in range(depth):

        new_frontier = set()

        for resource in frontier:

            if resource in visited:
                continue

            visited.add(resource)

            # outgoing edges
            for triple in g.triples((resource, None, None)):
                triples.add(triple)

                obj = triple[2]

                if hasattr(obj, "startswith"):
                    if str(obj).startswith(
                        (
                            "https://example.org/stib/",
                            "https://cyfun.eu/control/",
                            "https://example.org/cyfun-poc#",
                        )
                    ):
                        new_frontier.add(obj)

            # incoming edges
            for triple in g.triples((None, None, resource)):
                triples.add(triple)

                subject = triple[0]

                if str(subject).startswith(
                    (
                        "https://example.org/stib/",
                        "https://cyfun.eu/control/",
                    )
                ):
                    new_frontier.add(subject)

        frontier = new_frontier

    return triples


# ------------------------------------------------------------------
# STEP 4 — retrieve CyFun controls through semantic concepts
# ------------------------------------------------------------------

def retrieve_controls(concept_names: list[str]) -> set:

    controls = set()

    for concept_name in concept_names:

        concept = POC[concept_name]

        # direct semantic mappings
        for control, _, _ in g.triples((None, POC.concerns, concept)):
            controls.add(control)

        # also retrieve controls mapped to child concepts
        for child in g.subjects(
            predicate=None,
            object=concept,
        ):
            for control, _, _ in g.triples(
                (None, POC.concerns, child)
            ):
                controls.add(control)

    return controls


# ------------------------------------------------------------------
# STEP 5 — retrieve useful CyFun information
# ------------------------------------------------------------------

def retrieve_control_context(controls: set) -> set:

    triples = set()

    for control in controls:

        for triple in g.triples((control, None, None)):

            triples.add(triple)

            obj = triple[2]

            # Follow OSCAL parts containing the actual requirement text
            if str(obj).startswith("https://cyfun.eu/"):
                for child_triple in g.triples((obj, None, None)):
                    triples.add(child_triple)

    return triples


# ------------------------------------------------------------------
# Convert RDF context into compact text for the LLM
# ------------------------------------------------------------------

def compact_uri(value):

    value = str(value)

    replacements = {
        "https://example.org/stib/": "stib:",
        "https://cyfun.eu/control/": "cyfun:",
        "https://example.org/cyfun-poc#": "poc:",
        "https://example.org/oscal#": "oscal:",
        "http://www.w3.org/1999/02/22-rdf-syntax-ns#": "rdf:",
    }

    for base, prefix in replacements.items():
        if value.startswith(base):
            return value.replace(base, prefix)

    return value


def format_context(triples: set) -> str:

    rows = []

    for s, p, o in sorted(
        triples,
        key=lambda t: (
            str(t[0]),
            str(t[1]),
            str(t[2]),
        ),
    ):

        rows.append(
            f"{compact_uri(s)} "
            f"{compact_uri(p)} "
            f"{compact_uri(o)}"
        )

    return "\n".join(rows)


# ------------------------------------------------------------------
# STEP 6 — grounded answer
# ------------------------------------------------------------------

def generate_answer(question: str, context: str) -> str:

    prompt = f"""
You are analysing a cybersecurity knowledge graph.

Answer the user's question using ONLY the RDF context below.

Rules:

- Do not invent infrastructure facts.
- Do not invent CyFun requirements.
- Clearly distinguish explicit graph facts from your interpretation.
- Mention CyFun control IDs when relevant.
- A FAIL assessment is a finding in this fictitious PoC.
- If the graph does not contain enough information, say so.
- Answer in French.

USER QUESTION:

{question}

RDF CONTEXT:

{context}
"""

    response = client.responses.create(
        model=MODEL,
        input=prompt,
    )

    return response.output_text


# ------------------------------------------------------------------
# MAIN
# ------------------------------------------------------------------

if len(sys.argv) < 2:
    print(
        'Usage: python scripts/graphrag.py '
        '"Quels problèmes existent sur le Payment Backend ?"'
    )
    sys.exit(1)

question = " ".join(sys.argv[1:])

print("\nQUESTION")
print(question)

# LLM planning
plan = understand_question(question)

print("\nLLM QUERY PLAN")
print(json.dumps(plan, indent=2, ensure_ascii=False))

# Entity retrieval
entities = find_entities(plan.get("entities", []))

print("\nMATCHED GRAPH ENTITIES")

for entity in entities:
    print("-", compact_uri(entity))

# Graph traversal
context_triples = expand_neighbourhood(
    entities,
    depth=3,
)

# Semantic CyFun retrieval
controls = retrieve_controls(
    plan.get("concepts", [])
)

context_triples.update(
    retrieve_control_context(controls)
)

print("\nRETRIEVED CYFUN CONTROLS")

for control in sorted(controls, key=str):
    print("-", compact_uri(control))

# Build LLM context
context = format_context(context_triples)

print("\nGRAPH CONTEXT")
print("-------------")
print(context)

# Final generation
answer = generate_answer(
    question,
    context,
)

print("\nGRAPH-RAG ANSWER")
print("----------------")
print(answer)