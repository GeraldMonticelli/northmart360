from mcp.server import MCPServer
import httpx
import os
import re
from rdflib import Graph
from pyshacl import validate as shacl_validate
from pyshacl.errors import ValidationFailure

from working_model import (
    create_model,
    get_model,
    apply_changes,
    WorkingModelError,
)

MODEL_GRAPH_PREFIX = "urn:ontouml:model:"
CATALOG_GRAPH = "urn:ontouml:models"

OK_NS = "https://w3id.org/ontouml/knowledge#"
ONTOUML_NS = "https://w3id.org/ontouml#"

FUSEKI_QUERY_URL = os.getenv(
    "FUSEKI_QUERY_URL",
    "http://localhost:3030/ontouml",
)
ELASTICSEARCH_URL = os.getenv(
    "ELASTICSEARCH_URL",
    "http://localhost:9200",
)

ELASTICSEARCH_INDEX = os.getenv(
    "ELASTICSEARCH_INDEX",
    "ontouml",
)

mcp = MCPServer("generic-knowledge-graph")

async def _get_structural_neighborhood(
    element_iri: str,
    graph: str,
) -> dict:

    element = element_iri.replace(">", "%3E").replace("<", "%3C")

    query = f"""
    PREFIX ontouml: <{ONTOUML_NS}>

    SELECT DISTINCT
      ?direction
      ?relation
      ?relationName
      ?relationStereotype
      ?other
      ?otherName
      ?otherStereotype
    WHERE {{
      {{
        GRAPH <{graph}> {{
          ?relation a ontouml:Relation ;
                    ontouml:sourceEnd ?sourceEnd ;
                    ontouml:targetEnd ?targetEnd .

          ?sourceEnd ontouml:propertyType <{element}> .
          ?targetEnd ontouml:propertyType ?other .

          OPTIONAL {{ ?relation ontouml:name ?relationName }}
          OPTIONAL {{ ?relation ontouml:stereotype ?relationStereotype }}
          OPTIONAL {{ ?other ontouml:name ?otherName }}
          OPTIONAL {{ ?other ontouml:stereotype ?otherStereotype }}

          BIND("outgoing" AS ?direction)
        }}
      }}
      UNION
      {{
        GRAPH <{graph}> {{
          ?relation a ontouml:Relation ;
                    ontouml:sourceEnd ?sourceEnd ;
                    ontouml:targetEnd ?targetEnd .

          ?targetEnd ontouml:propertyType <{element}> .
          ?sourceEnd ontouml:propertyType ?other .

          OPTIONAL {{ ?relation ontouml:name ?relationName }}
          OPTIONAL {{ ?relation ontouml:stereotype ?relationStereotype }}
          OPTIONAL {{ ?other ontouml:name ?otherName }}
          OPTIONAL {{ ?other ontouml:stereotype ?otherStereotype }}

          BIND("incoming" AS ?direction)
        }}
      }}
    }}
    """

    result = await _query_fuseki(query)

    relations = []

    for b in result.get("results", {}).get("bindings", []):
        relations.append({
            "direction": _binding_value(b, "direction"),
            "relation": _binding_value(b, "relation"),
            "relation_name": _binding_value(b, "relationName"),
            "relation_stereotype": _local_name(
                _binding_value(b, "relationStereotype")
            ),
            "other_element": _binding_value(b, "other"),
            "other_name": _binding_value(b, "otherName"),
            "other_stereotype": _local_name(
                _binding_value(b, "otherStereotype")
            ),
        })

    return {"relations": relations}

def _stereotype_iri(stereotype: str) -> str:
    """
    Convert a short OntoUML stereotype such as 'role'
    into its canonical vocabulary IRI.
    """
    value = stereotype.strip()

    if value.startswith("http://") or value.startswith("https://"):
        return value

    return f"{ONTOUML_NS}{value}"


async def _catalog_graph_count() -> int:
    query = f"""
    SELECT (COUNT(DISTINCT ?g) AS ?count)
    WHERE {{
      GRAPH ?g {{ ?s ?p ?o }}
      FILTER(STRSTARTS(STR(?g), "{MODEL_GRAPH_PREFIX}"))
    }}
    """

    result = await _query_fuseki(query)
    bindings = result.get("results", {}).get("bindings", [])

    if not bindings:
        return 0

    return int(_binding_value(bindings[0], "count", "0"))

def _sparql_escape(value: str) -> str:
    """Escape a Python string for use inside a SPARQL string literal."""
    return (
        value
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
    )


def _binding_value(binding: dict, key: str, default=None):
    item = binding.get(key)
    return item.get("value", default) if item else default


def _local_name(iri: str | None) -> str | None:
    if not iri:
        return None

    if "#" in iri:
        return iri.rsplit("#", 1)[1]

    return iri.rstrip("/").rsplit("/", 1)[-1]


def _validate_model_graph(graph: str) -> str:
    graph = graph.strip()

    if not graph.startswith(MODEL_GRAPH_PREFIX):
        raise ValueError(
            f"Catalog model graph must start with {MODEL_GRAPH_PREFIX}"
        )

    if not re.fullmatch(r"urn:ontouml:model:[A-Za-z0-9._~%-]+", graph):
        raise ValueError("Invalid catalog model graph IRI.")

    return graph

async def execute_sparql(query: str) -> dict:
    """
    Execute a SPARQL query against Fuseki and return parsed JSON.
    """

    async with httpx.AsyncClient() as client:
        response = await client.get(
            FUSEKI_QUERY_URL,
            params={"query": query},
            headers={"Accept": "application/sparql-results+json"},
            timeout=30.0,
        )

        response.raise_for_status()
        return response.json()

# Helper pour charger les shapes depuis Fuseki
async def _get_shacl_shapes() -> str:
    """
    Retrieve the executable OntoUML SHACL shapes from Fuseki.
    """

    query = """
    CONSTRUCT {
        ?s ?p ?o .
    }
    WHERE {
        GRAPH <urn:ontouml:shapes> {
            ?s ?p ?o .
        }
    }
    """

    async with httpx.AsyncClient() as client:
        response = await client.post(
            FUSEKI_QUERY_URL,
            data={"query": query},
            headers={"Accept": "text/turtle"},
            timeout=30.0,
        )
        response.raise_for_status()
        return response.text


#  Validation SHACL
async def _validate_shacl(model_turtle: str) -> dict:

    data_graph = Graph()
    data_graph.parse(
        data=model_turtle,
        format="turtle",
    )

    shapes_turtle = await _get_shacl_shapes()

    shapes_graph = Graph()
    shapes_graph.parse(
        data=shapes_turtle,
        format="turtle",
    )

    conforms, results_graph, results_text = shacl_validate(
        data_graph=data_graph,
        shacl_graph=shapes_graph,
        inference="none",
        abort_on_first=False,
        allow_infos=True,
        allow_warnings=True,
        meta_shacl=False,
        advanced=True,
    )

    if isinstance(results_graph, ValidationFailure):
        return {
            "conforms": False,
            "validation_failure": True,
            "failure_message": str(results_graph),
            "report": results_text,
            "report_rdf": None,
        }

    return {
        "conforms": bool(conforms),
        "validation_failure": False,
        "failure_message": None,
        "report": results_text,
        "report_rdf": results_graph.serialize(format="turtle"),
    }


# fonction d’accès Elasticsearch
async def execute_elasticsearch_search(
    query: str,
    top_k: int = 5,
) -> dict:
    """
    Search the indexed official OntoUML documentation using
    Elasticsearch BM25 retrieval.
    """

    top_k = min(max(top_k, 1), 20)

    body = {
        "size": top_k,
        "_source": [
            "source",
            "domain",
            "element",
            "section",
            "unit_type",
            "unit_id",
            "provenance",
            "text",
        ],
        "query": {
            "match": {
                "text": query
            }
        },
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{ELASTICSEARCH_URL}/{ELASTICSEARCH_INDEX}/_search",
            json=body,
            timeout=10.0,
        )

        response.raise_for_status()
        return response.json()

def validate_iri(iri: str) -> None:
    """
    Minimal validation before inserting an IRI into generated SPARQL.
    """

    if not iri.startswith(("http://", "https://", "urn:")):
        raise ValueError(f"Invalid IRI: {iri}")

    if any(c in iri for c in "<>\"{}|\\^`"):
        raise ValueError(f"Invalid IRI: {iri}")


@mcp.tool()
async def list_classes(limit: int = 100) -> dict:
    """
    List RDF classes actually used by instances in the knowledge graph.
    """

    query = f"""
    SELECT DISTINCT ?class
    WHERE {{
        ?instance a ?class .
    }}
    ORDER BY ?class
    LIMIT {min(max(limit, 1), 1000)}
    """

    return await execute_sparql(query)


@mcp.tool()
async def list_predicates(limit: int = 100) -> dict:
    """
    List predicates used in the knowledge graph, ordered by usage count.
    """

    query = f"""
    SELECT ?predicate (COUNT(*) AS ?count)
    WHERE {{
        ?subject ?predicate ?object .
    }}
    GROUP BY ?predicate
    ORDER BY DESC(?count)
    LIMIT {min(max(limit, 1), 1000)}
    """

    return await execute_sparql(query)


@mcp.tool()
async def list_named_graphs(limit: int = 100) -> dict:
    """
    List named graphs available in the RDF dataset.
    """

    query = f"""
    SELECT DISTINCT ?graph
    WHERE {{
        GRAPH ?graph {{
            ?subject ?predicate ?object .
        }}
    }}
    ORDER BY ?graph
    LIMIT {min(max(limit, 1), 1000)}
    """

    return await execute_sparql(query)


@mcp.tool()
async def sample_of_type(class_iri: str, limit: int = 10) -> dict:
    """
    Return example resources that are instances of a given RDF class.
    """

    validate_iri(class_iri)

    query = f"""
    SELECT DISTINCT ?instance
    WHERE {{
        ?instance a <{class_iri}> .
    }}
    LIMIT {min(max(limit, 1), 100)}
    """

    return await execute_sparql(query)


@mcp.tool()
async def describe_resource(resource_iri: str, limit: int = 100) -> dict:
    """
    Describe an RDF resource by returning its outgoing and incoming
    relationships.
    """

    validate_iri(resource_iri)
    limit = min(max(limit, 1), 500)

    query = f"""
    SELECT ?direction ?predicate ?value
    WHERE {{
        {{
            <{resource_iri}> ?predicate ?value .
            BIND("outgoing" AS ?direction)
        }}
        UNION
        {{
            ?value ?predicate <{resource_iri}> .
            BIND("incoming" AS ?direction)
        }}
    }}
    LIMIT {limit}
    """

    return await execute_sparql(query)


@mcp.tool()
async def discover_graph(limit: int = 200) -> dict:
    """
    Discover RDF/RDFS/OWL vocabulary and hierarchy information
    without prior knowledge of the business domain.
    """

    query = f"""
    SELECT DISTINCT ?subject ?predicate ?object
    WHERE {{
        ?subject ?predicate ?object .

        FILTER (
             ?predicate = <http://www.w3.org/1999/02/22-rdf-syntax-ns#type>
          || ?predicate = <http://www.w3.org/2000/01/rdf-schema#subClassOf>
          || ?predicate = <http://www.w3.org/2000/01/rdf-schema#subPropertyOf>
        )
    }}
    ORDER BY ?subject ?predicate
    LIMIT {min(max(limit, 1), 1000)}
    """

    return await execute_sparql(query)


@mcp.tool()
async def query_sparql(query: str) -> dict:
    """
    Execute an arbitrary read-only SELECT or ASK SPARQL query.

    Use the discovery tools first when the vocabulary of the graph
    is unknown.
    """

    normalized = query.strip().upper()

    if "SELECT" not in normalized and "ASK" not in normalized:
        raise ValueError("Only SELECT and ASK SPARQL queries are allowed.")

    forbidden = (
        "INSERT",
        "DELETE",
        "LOAD",
        "CLEAR",
        "CREATE",
        "DROP",
        "COPY",
        "MOVE",
        "ADD",
    )

    if any(keyword in normalized for keyword in forbidden):
        raise ValueError("SPARQL Update operations are not allowed.")

    return await execute_sparql(query)

@mcp.tool()
async def find_stereotype_candidates(
    element_type: str = "class",
    rigidity: str | None = None,
    dependency: str | None = None,
    provides_identity: bool | None = None,
    identity_principle: str | None = None,
) -> dict:
    """
    Find OntoUML stereotype candidates compatible with known ontological
    characteristics.

    Unknown characteristics must be passed as null / omitted.

    The tool does NOT guess missing characteristics. It returns the
    remaining candidates and the discriminating characteristics that
    could help distinguish them.

    element_type:
      - "class"
      - "relationship"
    """

    if element_type not in {"class", "relationship"}:
        raise ValueError("element_type must be 'class' or 'relationship'")

    category = (
        "class_stereotype"
        if element_type == "class"
        else "relationship_stereotype"
    )

    query = f"""
PREFIX ok: <https://w3id.org/ontouml/knowledge#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?element ?label ?rigidity ?dependency
       ?providesIdentity ?identityPrinciple
WHERE {{
  GRAPH <urn:ontouml:knowledge> {{
    ?element a ok:LanguageElement ;
             rdfs:label ?label ;
             ok:category "{category}" .

    OPTIONAL {{ ?element ok:rigidity ?rigidity }}
    OPTIONAL {{ ?element ok:dependency ?dependency }}
    OPTIONAL {{ ?element ok:provides-identity ?providesIdentity }}
    OPTIONAL {{ ?element ok:identity-principle ?identityPrinciple }}
  }}
}}
ORDER BY ?label
"""

    result = await execute_sparql(query)

    # Adapt this line only if your existing _sparql_select()
    # already returns the bindings list directly.
    bindings = result.get("results", {}).get("bindings", [])

    requested = {
        "rigidity": rigidity,
        "dependency": dependency,
        "provides_identity": provides_identity,
        "identity_principle": identity_principle,
    }

    sparql_names = {
        "rigidity": "rigidity",
        "dependency": "dependency",
        "provides_identity": "providesIdentity",
        "identity_principle": "identityPrinciple",
    }

    def rdf_value(binding: dict, field: str):
        value = binding.get(sparql_names[field])
        if value is None:
            return None

        raw = value.get("value")

        if field == "provides_identity":
            return str(raw).lower() == "true"

        return raw

    compatible = []
    incompatible = []

    for binding in bindings:
        candidate = {
            "name": binding["label"]["value"],
            "uri": binding["element"]["value"],
        }

        characteristics = {
            field: rdf_value(binding, field)
            for field in requested
        }

        candidate["characteristics"] = characteristics

        conflicts = []

        for field, expected in requested.items():
            if expected is None:
                continue

            actual = characteristics[field]

            # Missing knowledge is NOT treated as a contradiction.
            if actual is not None and actual != expected:
                conflicts.append({
                    "characteristic": field,
                    "expected": expected,
                    "actual": actual,
                })

        if conflicts:
            candidate["conflicts"] = conflicts
            incompatible.append(candidate)
        else:
            compatible.append(candidate)

    # Determine which still-unknown characteristics actually discriminate
    # between the remaining candidates.
    discriminators = []

    for field, supplied_value in requested.items():
        if supplied_value is not None:
            continue

        values = {
            c["characteristics"][field]
            for c in compatible
            if c["characteristics"][field] is not None
        }

        if len(values) > 1:
            discriminators.append({
                "characteristic": field,
                "values": sorted(values, key=str),
            })

    return {
        "element_type": element_type,
        "known_characteristics": {
            k: v for k, v in requested.items()
            if v is not None
        },
        "compatible_candidates": compatible,
        "candidate_count": len(compatible),
        "missing_discriminators": discriminators,
        "incompatible_candidates": incompatible,
    }


def _binding_value(binding: dict, name: str):
    """Return the lexical value of a SPARQL JSON binding, or None."""
    item = binding.get(name)
    return item.get("value") if item else None


def _local_name(value: str | None) -> str | None:
    """Compact an IRI for MCP output while preserving literals."""
    if value is None:
        return None
    if value.startswith(("http://", "https://", "urn:")):
        return value.rsplit("#", 1)[-1].rsplit("/", 1)[-1]
    return value


def _rows(result: dict) -> list[dict]:
    return result.get("results", {}).get("bindings", [])


async def _get_stereotype_knowledge(stereotype: str) -> dict:
    """
    Get structured OntoUML knowledge for a stereotype.

    Returns its ontological characteristics, constraints, related
    patterns/anti-patterns, and linked executable SHACL constraints.

    Use get_modeling_context() instead when making a modeling decision
    that also requires documentary evidence.
    """

    if stereotype.startswith(("http://", "https://")):
        stereotype_iri = stereotype
        validate_iri(stereotype_iri)
    else:
        if not stereotype or any(c in stereotype for c in '<>"{}|\\^` /'):
            raise ValueError("Invalid OntoUML stereotype name.")
        stereotype_iri = f"https://w3id.org/ontouml#{stereotype}"

    # Resolve the LanguageElement that describes the official stereotype IRI.
    semantics_query = f"""
PREFIX ok: <https://w3id.org/ontouml/knowledge#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?element ?label ?category ?rigidity ?dependency
       ?providesIdentity ?identityPrinciple
WHERE {{
  GRAPH <urn:ontouml:knowledge> {{
    ?element a ok:LanguageElement ;
             ok:describes <{stereotype_iri}> .
    OPTIONAL {{ ?element rdfs:label ?label }}
    OPTIONAL {{ ?element ok:category ?category }}
    OPTIONAL {{ ?element ok:rigidity ?rigidity }}
    OPTIONAL {{ ?element ok:dependency ?dependency }}
    OPTIONAL {{ ?element ok:provides-identity ?providesIdentity }}
    OPTIONAL {{ ?element ok:identity-principle ?identityPrinciple }}
  }}
}}
LIMIT 1
"""
    semantics_result = await execute_sparql(semantics_query)
    semantic_rows = _rows(semantics_result)

    semantics = {}
    language_element = None
    if semantic_rows:
        b = semantic_rows[0]
        language_element = _binding_value(b, "element")
        semantics = {
            "label": _binding_value(b, "label"),
            "category": _binding_value(b, "category"),
            "rigidity": _binding_value(b, "rigidity"),
            "dependency": _binding_value(b, "dependency"),
            "provides_identity": (
                _binding_value(b, "providesIdentity").lower() == "true"
                if _binding_value(b, "providesIdentity") is not None
                else None
            ),
            "identity_principle": _binding_value(b, "identityPrinciple"),
        }

    # Retrieve each applicable constraint and its scalar properties.
    constraints_query = f"""
PREFIX ok: <https://w3id.org/ontouml/knowledge#>

SELECT ?constraint ?code ?modality ?constraintType
       ?cardinality ?minCardinality ?maxCardinality
       ?pathScope ?relation ?semanticStatus ?sourceText ?shape
WHERE {{
  GRAPH <urn:ontouml:structured-knowledge> {{
    ?constraint a ok:Constraint ;
                ok:appliesTo <{stereotype_iri}> .
    OPTIONAL {{ ?constraint ok:code ?code }}
    OPTIONAL {{ ?constraint ok:modality ?modality }}
    OPTIONAL {{ ?constraint ok:constraintType ?constraintType }}
    OPTIONAL {{ ?constraint ok:cardinality ?cardinality }}
    OPTIONAL {{ ?constraint ok:minCardinality ?minCardinality }}
    OPTIONAL {{ ?constraint ok:maxCardinality ?maxCardinality }}
    OPTIONAL {{ ?constraint ok:pathScope ?pathScope }}
    OPTIONAL {{ ?constraint ok:relation ?relation }}
    OPTIONAL {{ ?constraint ok:semanticStatus ?semanticStatus }}
    OPTIONAL {{ ?constraint ok:sourceText ?sourceText }}
  }}
  OPTIONAL {{
    GRAPH <urn:ontouml:shapes> {{
      ?constraint ok:implementedBy ?shape .
    }}
  }}
}}
ORDER BY ?code ?constraint
"""
    constraints_result = await execute_sparql(constraints_query)

    constraints_by_iri = {}
    for b in _rows(constraints_result):
        iri = _binding_value(b, "constraint")
        if iri not in constraints_by_iri:
            constraints_by_iri[iri] = {
                "id": _local_name(iri),
                "iri": iri,
                "code": _binding_value(b, "code"),
                "modality": _local_name(_binding_value(b, "modality")),
                "constraint_type": _local_name(_binding_value(b, "constraintType")),
                "cardinality": _binding_value(b, "cardinality"),
                "min_cardinality": _binding_value(b, "minCardinality"),
                "max_cardinality": _binding_value(b, "maxCardinality"),
                "path_scope": _local_name(_binding_value(b, "pathScope")),
                "relation": _local_name(_binding_value(b, "relation")),
                "semantic_status": _local_name(_binding_value(b, "semanticStatus")),
                "source_text": _binding_value(b, "sourceText"),
                "implemented_by": [],
                "lists": {},
            }
        shape = _binding_value(b, "shape")
        if shape and shape not in constraints_by_iri[iri]["implemented_by"]:
            constraints_by_iri[iri]["implemented_by"].append(shape)

    # Generic RDF Collection expansion: no Role/Phase/Kind-specific logic.
    lists_query = f"""
PREFIX ok: <https://w3id.org/ontouml/knowledge#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT ?constraint ?property ?member
WHERE {{
  GRAPH <urn:ontouml:structured-knowledge> {{
    ?constraint a ok:Constraint ;
                ok:appliesTo <{stereotype_iri}> ;
                ?property ?head .
    ?head rdf:rest*/rdf:first ?member .
  }}
}}
ORDER BY ?constraint ?property ?member
"""
    lists_result = await execute_sparql(lists_query)

    for b in _rows(lists_result):
        iri = _binding_value(b, "constraint")
        if iri not in constraints_by_iri:
            continue
        prop = _local_name(_binding_value(b, "property"))
        member = _binding_value(b, "member")
        values = constraints_by_iri[iri]["lists"].setdefault(prop, [])
        compact = _local_name(member)
        if compact not in values:
            values.append(compact)

    # Patterns/anti-patterns are deliberately retrieved generically through
    # references to the stereotype, instead of hard-coding their schemas.
    related_query = f"""
PREFIX ok: <https://w3id.org/ontouml/knowledge#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT DISTINCT ?resource ?type ?label
WHERE {{
  GRAPH <urn:ontouml:structured-knowledge> {{
    ?resource a ?type ;
              ok:references <{stereotype_iri}> .
    OPTIONAL {{ ?resource rdfs:label ?label }}
    VALUES ?type {{ ok:Pattern ok:AntiPattern }}
  }}
}}
ORDER BY ?type ?label ?resource
"""
    related_result = await execute_sparql(related_query)
    patterns, antipatterns = [], []

    for b in _rows(related_result):
        item = {
            "id": _local_name(_binding_value(b, "resource")),
            "iri": _binding_value(b, "resource"),
            "label": _binding_value(b, "label"),
        }
        type_name = _local_name(_binding_value(b, "type"))
        if type_name == "Pattern":
            patterns.append(item)
        elif type_name == "AntiPattern":
            antipatterns.append(item)

    return {
        "stereotype": _local_name(stereotype_iri),
        "stereotype_iri": stereotype_iri,
        "language_element": language_element,
        "semantics": semantics,
        "constraints": list(constraints_by_iri.values()),
        "patterns": patterns,
        "antipatterns": antipatterns,
    }

@mcp.tool()
async def get_stereotype_knowledge(stereotype: str) -> dict:
    """
    Get structured OntoUML knowledge for a stereotype.

    Returns its ontological characteristics, constraints, related
    patterns/anti-patterns, and linked executable SHACL constraints.

    Use get_modeling_context() when making a modeling decision that
    also requires documentary evidence.
    """
    return await _get_stereotype_knowledge(stereotype)

@mcp.tool()
async def get_repair_knowledge(violation: str) -> dict:
    """
    Return repair/refactoring knowledge related to a validation violation.

    `violation` may be:
      - a full constraint or anti-pattern IRI;
      - a short identifier such as "role-c1";
      - a code such as "C1";
      - an anti-pattern label/name.

    The tool does not invent a repair. It returns only repair/refactoring
    knowledge present in urn:ontouml:structured-knowledge, together with
    related patterns/anti-patterns and source text when available.
    """

    if not violation or len(violation) > 500:
        raise ValueError("A non-empty violation identifier is required.")

    # Full IRI: exact matching. Otherwise use a safely escaped literal search.
    if violation.startswith(("http://", "https://", "urn:")):
        validate_iri(violation)
        match_filter = f"?resource = <{violation}>"
    else:
        # SPARQL string literal escaping.
        needle = (
            violation.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
            .replace("\r", "\\r")
        )
        match_filter = f"""
(
    LCASE(STR(?code)) = LCASE("{needle}")
 || LCASE(STR(?label)) = LCASE("{needle}")
 || LCASE(REPLACE(STR(?resource), "^.*[#/]", "")) = LCASE("{needle}")
)
"""

    resolve_query = f"""
PREFIX ok: <https://w3id.org/ontouml/knowledge#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT DISTINCT ?resource ?type ?code ?label ?sourceText
WHERE {{
  GRAPH <urn:ontouml:structured-knowledge> {{
    ?resource a ?type .
    VALUES ?type {{ ok:Constraint ok:AntiPattern ok:DetectionCondition }}
    OPTIONAL {{ ?resource ok:code ?code }}
    OPTIONAL {{ ?resource rdfs:label ?label }}
    OPTIONAL {{ ?resource ok:sourceText ?sourceText }}
    FILTER ({match_filter})
  }}
}}
LIMIT 20
"""
    resolved = await execute_sparql(resolve_query)
    matches = _rows(resolved)

    if not matches:
        return {
            "violation": violation,
            "matched": False,
            "message": "No matching structured OntoUML constraint or anti-pattern was found.",
            "repairs": [],
            "related_patterns": [],
            "related_antipatterns": [],
        }

    resources = []
    for b in matches:
        iri = _binding_value(b, "resource")
        if iri and iri not in resources:
            resources.append(iri)

    values_clause = " ".join(f"<{iri}>" for iri in resources)

    # Retrieve explicit refactoring-plan links in either direction, because
    # the V3 graph may model ownership from the anti-pattern or from the plan.
    repair_query = f"""
PREFIX ok: <https://w3id.org/ontouml/knowledge#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT DISTINCT ?owner ?plan ?label ?sourceText ?action ?creates ?removes ?changes
WHERE {{
  GRAPH <urn:ontouml:structured-knowledge> {{
    VALUES ?matched {{ {values_clause} }}

    {{
      BIND(?matched AS ?owner)
      ?owner ?link ?plan .
      ?plan a ok:RefactoringPlan .
    }}
    UNION
    {{
      ?plan a ok:RefactoringPlan ;
            ?link ?matched .
      BIND(?matched AS ?owner)
    }}
    UNION
    {{
      ?condition ?conditionLink ?matched .
      ?antiPattern ?antiPatternLink ?condition .
      ?antiPattern ?planLink ?plan .
      ?plan a ok:RefactoringPlan .
      BIND(?antiPattern AS ?owner)
    }}

    OPTIONAL {{ ?plan rdfs:label ?label }}
    OPTIONAL {{ ?plan ok:sourceText ?sourceText }}
    OPTIONAL {{ ?plan ok:action ?action }}
    OPTIONAL {{ ?plan ok:creates ?creates }}
    OPTIONAL {{ ?plan ok:removes ?removes }}
    OPTIONAL {{ ?plan ok:changes ?changes }}
  }}
}}
ORDER BY ?owner ?plan
"""
    repairs_result = await execute_sparql(repair_query)

    repairs_by_iri = {}
    for b in _rows(repairs_result):
        iri = _binding_value(b, "plan")
        if iri not in repairs_by_iri:
            repairs_by_iri[iri] = {
                "id": _local_name(iri),
                "iri": iri,
                "owner": _binding_value(b, "owner"),
                "label": _binding_value(b, "label"),
                "source_text": _binding_value(b, "sourceText"),
                "actions": [],
                "creates": [],
                "removes": [],
                "changes": [],
            }
        item = repairs_by_iri[iri]
        for source_name, target_name in (
            ("action", "actions"),
            ("creates", "creates"),
            ("removes", "removes"),
            ("changes", "changes"),
        ):
            value = _binding_value(b, source_name)
            if value:
                compact = _local_name(value)
                if compact not in item[target_name]:
                    item[target_name].append(compact)

    # Find patterns/anti-patterns connected to the matched violation through
    # any shared referenced OntoUML concept. This is intentionally generic.
    related_query = f"""
PREFIX ok: <https://w3id.org/ontouml/knowledge#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT DISTINCT ?related ?type ?label ?reference
WHERE {{
  GRAPH <urn:ontouml:structured-knowledge> {{
    VALUES ?matched {{ {values_clause} }}
    ?matched ok:references ?reference .
    ?related ok:references ?reference ;
             a ?type .
    VALUES ?type {{ ok:Pattern ok:AntiPattern }}
    OPTIONAL {{ ?related rdfs:label ?label }}
    FILTER (?related != ?matched)
  }}
}}
ORDER BY ?type ?label ?related
"""
    related_result = await execute_sparql(related_query)

    patterns, antipatterns = [], []
    seen = set()
    for b in _rows(related_result):
        iri = _binding_value(b, "related")
        type_name = _local_name(_binding_value(b, "type"))
        key = (type_name, iri)
        if key in seen:
            continue
        seen.add(key)
        item = {
            "id": _local_name(iri),
            "iri": iri,
            "label": _binding_value(b, "label"),
        }
        if type_name == "Pattern":
            patterns.append(item)
        elif type_name == "AntiPattern":
            antipatterns.append(item)

    matched_resources = [
        {
            "id": _local_name(_binding_value(b, "resource")),
            "iri": _binding_value(b, "resource"),
            "type": _local_name(_binding_value(b, "type")),
            "code": _binding_value(b, "code"),
            "label": _binding_value(b, "label"),
            "source_text": _binding_value(b, "sourceText"),
        }
        for b in matches
    ]

    return {
        "violation": violation,
        "matched": True,
        "matched_resources": matched_resources,
        "repairs": list(repairs_by_iri.values()),
        "related_patterns": patterns,
        "related_antipatterns": antipatterns,
        "note": (
            "Repairs are returned only when explicitly represented in the "
            "structured knowledge graph; an empty list means no explicit "
            "refactoring plan was found, not that no repair is possible."
        ),
    }


@mcp.tool()
async def get_theory_concept(concept: str) -> dict:
    """
    Retrieve a structured OntoUML theory concept from urn:ontouml:theory.

    Examples:
      get_theory_concept("anti-rigid")
      get_theory_concept("rigidity")
      get_theory_concept("identity principle")
      get_theory_concept("instantiation")

    The tool resolves the concept generically by exact IRI/local-name/label
    matching and returns its definition plus incoming/outgoing semantic
    relationships. It does not hard-code individual theory concepts.
    """

    if not concept or len(concept) > 500:
        raise ValueError("A non-empty theory concept is required.")

    # Resolve a full IRI exactly; otherwise resolve against local name or label.
    if concept.startswith(("http://", "https://", "urn:")):
        validate_iri(concept)
        match_filter = f"?concept = <{concept}>"
    else:
        needle = (
            concept.strip()
            .replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
            .replace("\r", "\\r")
        )
        # Treat spaces, underscores and hyphens as equivalent for lookup.
        match_filter = f"""
(
    LCASE(REPLACE(REPLACE(REPLACE(STR(?label), "[-_ ]", ""), "\\\\s+", "")) =
    LCASE(REPLACE(REPLACE(REPLACE("{needle}", "[-_ ]", ""), "\\\\s+", ""))
 ||
    LCASE(REPLACE(REPLACE(REPLACE(REPLACE(STR(?concept),
        "^.*[#/]", ""), "[-_ ]", ""), "\\\\s+", "")) =
    LCASE(REPLACE(REPLACE(REPLACE("{needle}", "[-_ ]", ""), "\\\\s+", ""))
)
"""

    resolve_query = f"""
PREFIX ok: <https://w3id.org/ontouml/knowledge#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX dcterms: <http://purl.org/dc/terms/>

SELECT DISTINCT ?concept ?label ?definition ?source
WHERE {{
  GRAPH <urn:ontouml:theory> {{
    ?concept a ok:TheoryConcept .
    OPTIONAL {{ ?concept rdfs:label ?label }}
    OPTIONAL {{ ?concept skos:definition ?definition }}
    OPTIONAL {{ ?concept dcterms:source ?source }}
    FILTER ({match_filter})
  }}
}}
ORDER BY ?concept
LIMIT 20
"""
    resolved = await execute_sparql(resolve_query)
    matches = _rows(resolved)

    if not matches:
        return {
            "query": concept,
            "matched": False,
            "message": "No matching OntoUML theory concept was found in urn:ontouml:theory.",
        }

    concept_iris = []
    concepts = {}

    for b in matches:
        iri = _binding_value(b, "concept")
        if not iri:
            continue
        if iri not in concept_iris:
            concept_iris.append(iri)
        if iri not in concepts:
            concepts[iri] = {
                "id": _local_name(iri),
                "iri": iri,
                "label": _binding_value(b, "label"),
                "definition": _binding_value(b, "definition"),
                "source": _binding_value(b, "source"),
                "outgoing_relations": [],
                "incoming_relations": [],
                "characterized_stereotypes": [],
            }

    values_clause = " ".join(f"<{iri}>" for iri in concept_iris)

    # Return the graph neighborhood so GPT receives the meaning of the concept,
    # not merely its textual definition.
    relations_query = f"""
PREFIX ok: <https://w3id.org/ontouml/knowledge#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX dcterms: <http://purl.org/dc/terms/>

SELECT DISTINCT ?concept ?direction ?predicate ?value
WHERE {{
  VALUES ?concept {{ {values_clause} }}

  {{
    GRAPH <urn:ontouml:theory> {{
      ?concept ?predicate ?value .
      FILTER (
        ?predicate NOT IN (
          rdf:type,
          rdfs:label,
          skos:definition,
          dcterms:source
        )
      )
    }}
    BIND("outgoing" AS ?direction)
  }}
  UNION
  {{
    GRAPH <urn:ontouml:theory> {{
      ?value ?predicate ?concept .
    }}
    BIND("incoming" AS ?direction)
  }}
}}
ORDER BY ?concept ?direction ?predicate ?value
"""
    relations_result = await execute_sparql(relations_query)

    for b in _rows(relations_result):
        iri = _binding_value(b, "concept")
        if iri not in concepts:
            continue

        direction = _binding_value(b, "direction")
        predicate_iri = _binding_value(b, "predicate")
        value = _binding_value(b, "value")

        relation = {
            "predicate": _local_name(predicate_iri),
            "predicate_iri": predicate_iri,
            "value": _local_name(value),
            "value_iri": value if value and value.startswith(
                ("http://", "https://", "urn:")
            ) else None,
        }

        target = (
            concepts[iri]["outgoing_relations"]
            if direction == "outgoing"
            else concepts[iri]["incoming_relations"]
        )

        if relation not in target:
            target.append(relation)

        if (
            direction == "outgoing"
            and _local_name(predicate_iri) == "characterizesStereotype"
            and value
        ):
            compact = _local_name(value)
            if compact not in concepts[iri]["characterized_stereotypes"]:
                concepts[iri]["characterized_stereotypes"].append(compact)

    # Also expose stereotypes that point to this theory concept, e.g.
    # ontouml:role ok:hasRigidity theory:anti-rigid.
    stereotype_query = f"""
PREFIX ok: <https://w3id.org/ontouml/knowledge#>

SELECT DISTINCT ?concept ?stereotype ?relation
WHERE {{
  VALUES ?concept {{ {values_clause} }}
  GRAPH <urn:ontouml:theory> {{
    ?stereotype ?relation ?concept .
    FILTER(STRSTARTS(STR(?stereotype), "https://w3id.org/ontouml#"))
  }}
}}
ORDER BY ?concept ?stereotype
"""
    stereotype_result = await execute_sparql(stereotype_query)

    for b in _rows(stereotype_result):
        iri = _binding_value(b, "concept")
        if iri not in concepts:
            continue
        st = _local_name(_binding_value(b, "stereotype"))
        if st and st not in concepts[iri]["characterized_stereotypes"]:
            concepts[iri]["characterized_stereotypes"].append(st)

    return {
        "query": concept,
        "matched": True,
        "concepts": list(concepts.values()),
    }


async def _search_ontouml_documentation(
    query: str,
    top_k: int = 5,
) -> dict:
    """
    Search official OntoUML documentation with BM25.

    Use for definitions, explanations, examples and documentary evidence.
    Prefer structured graph knowledge for formal constraints.
    """

    if not query or not query.strip():
        raise ValueError("A non-empty documentation search query is required.")

    if len(query) > 1000:
        raise ValueError("Documentation search query is too long.")

    result = await execute_elasticsearch_search(
        query=query.strip(),
        top_k=top_k,
    )

    hits = result.get("hits", {}).get("hits", [])

    return {
        "query": query,
        "retrieval": {
            "engine": "elasticsearch",
            "method": "BM25",
            "index": ELASTICSEARCH_INDEX,
        },
        "result_count": len(hits),
        "results": [
            {
                "rank": rank,
                "score": hit.get("_score"),
                **hit.get("_source", {}),
            }
            for rank, hit in enumerate(hits, start=1)
        ],
    }

@mcp.tool()
async def search_ontouml_documentation(
    query: str,
    top_k: int = 5,
) -> dict:
    """
    Search official OntoUML documentation with Elasticsearch BM25.

    Use for definitions, explanations, examples and documentary evidence.
    Prefer structured graph knowledge for formal constraints.
    """
    return await _search_ontouml_documentation(
        query=query,
        top_k=top_k,
    )

@mcp.tool()
async def get_modeling_context(
    stereotype: str,
    question: str,
    top_k: int = 5,
) -> dict:
    """
    Get evidence for an OntoUML modeling decision.

    Combines:
    - structured semantic knowledge from the knowledge graph;
    - executable constraints linked to that knowledge;
    - relevant official documentation retrieved with BM25.

    This tool retrieves evidence; it does not choose the stereotype.
    """

    structured = await _get_stereotype_knowledge(stereotype)

    documentation = await _search_ontouml_documentation(
        query=f"{stereotype} {question}",
        top_k=top_k,
    )

    return {
        "candidate": stereotype,
        "question": question,
        "retrieval_strategy": "graph-first-hybrid",
        
        "structured_knowledge": structured["semantics"],
        "constraints": structured["constraints"],
        "patterns": structured.get("patterns", []),
        "anti_patterns": structured.get("antipatterns", []),

        "documentation": documentation["results"],
    }

@mcp.tool()
async def validate_model(model_turtle: str) -> dict:
    """
    Validate an OntoUML model against the executable SHACL constraints
    stored in the MCP knowledge base.

    Use after creating or modifying a candidate model.
    Returns formal violations without repairing the model.
    """

    if not model_turtle or not model_turtle.strip():
        raise ValueError("model_turtle must not be empty.")

    result = await _validate_shacl(model_turtle)

    return {
        "validator": "SHACL",
        "shapes_graph": "urn:ontouml:shapes",
        **result,
    }

@mcp.tool()
async def find_catalog_models(
    metadata_terms: list[str],
    concept_terms: list[str] | None = None,
    limit: int = 10,
) -> dict:
    """
    Find relevant modeling precedents in the OntoUML model catalog.

    Search catalog metadata first and optionally named model elements.
    Provide several short terms, preferably including English synonyms
    for multilingual discovery. Returned models are examples, not rules.

    After selecting promising results, use inspect_catalog_model() to
    analyze their OntoUML structure before reusing any modeling pattern.
    """
    metadata_terms = [
        t.strip()
        for t in (metadata_terms or [])
        if t and t.strip()
    ]

    concept_terms = [
        t.strip()
        for t in (concept_terms or [])
        if t and t.strip()
    ]

    if not metadata_terms and not concept_terms:
        raise ValueError(
            "Provide at least one metadata term or concept term."
        )

    limit = max(1, min(limit, 20))

    # --------------------------------------------------------------
    # Build lexical conditions
    # --------------------------------------------------------------

    metadata_filter = "false"

    if metadata_terms:
        metadata_filter = " || ".join(
            f'CONTAINS(LCASE(STR(?metadataValue)), '
            f'LCASE("{_sparql_escape(term)}"))'
            for term in metadata_terms
        )

    concept_filter = "false"

    if concept_terms:
        concept_filter = " || ".join(
            f'CONTAINS(LCASE(STR(?elementName)), '
            f'LCASE("{_sparql_escape(term)}"))'
            for term in concept_terms
        )

    # --------------------------------------------------------------
    # One result row per catalog model.
    #
    # Metadata and structural evidence are collected independently.
    # The localGraph link connects the two knowledge layers.
    # --------------------------------------------------------------

    query = f"""
    PREFIX dct:     <http://purl.org/dc/terms/>
    PREFIX dcat:    <http://www.w3.org/ns/dcat#>
    PREFIX ontouml: <{ONTOUML_NS}>
    PREFIX ok:      <{OK_NS}>

    SELECT
        ?model
        ?title
        ?graph
        ?language
        (COUNT(DISTINCT ?metadataValue) AS ?metadataMatches)
        (COUNT(DISTINCT ?element) AS ?conceptMatches)
        (GROUP_CONCAT(
            DISTINCT STR(?metadataValue);
            separator=" | "
        ) AS ?metadataEvidence)
        (GROUP_CONCAT(
            DISTINCT STR(?elementName);
            separator=" | "
        ) AS ?conceptEvidence)

    WHERE {{

        GRAPH <{CATALOG_GRAPH}> {{
            ?model ok:localGraph ?graph .

            OPTIONAL {{
                ?model dct:title ?title .
            }}

            OPTIONAL {{
                ?model dct:language ?language .
            }}
        }}

        # Only consider graphs that actually exist.
        FILTER EXISTS {{
            GRAPH ?graph {{
                ?existingSubject ?existingPredicate ?existingObject .
            }}
        }}

        OPTIONAL {{
            GRAPH <{CATALOG_GRAPH}> {{
                ?model ?metadataProperty ?metadataValue .

                FILTER(isLiteral(?metadataValue))
                FILTER({metadata_filter})
            }}
        }}

        OPTIONAL {{
            GRAPH ?graph {{
                ?element ontouml:name ?elementName .

                FILTER({concept_filter})
            }}
        }}

        FILTER(
            BOUND(?metadataValue)
            ||
            BOUND(?element)
        )
    }}

    GROUP BY ?model ?title ?graph ?language

    ORDER BY
        DESC(?metadataMatches)
        DESC(?conceptMatches)
        LCASE(STR(?title))

    LIMIT {limit}
    """

    result = await _query_fuseki(query)

    models = []

    for b in result.get("results", {}).get("bindings", []):
        graph = _binding_value(b, "graph")

        models.append({
            "model_uri": _binding_value(b, "model"),
            "title": _binding_value(b, "title"),
            "graph": graph,
            "model_id": (
                graph.removeprefix(MODEL_GRAPH_PREFIX)
                if graph
                else None
            ),
            "language": _binding_value(b, "language"),
            "metadata_matches": int(
                _binding_value(b, "metadataMatches", "0")
            ),
            "concept_matches": int(
                _binding_value(b, "conceptMatches", "0")
            ),
            "metadata_evidence": _binding_value(
                b,
                "metadataEvidence",
                "",
            ),
            "concept_evidence": _binding_value(
                b,
                "conceptEvidence",
                "",
            ),
        })

    return {
        "metadata_terms": metadata_terms,
        "concept_terms": concept_terms,
        "models_found": len(models),
        "models": models,
        "usage": (
            "Select the most promising candidates from the evidence, "
            "then call inspect_catalog_model() on their graph IRIs. "
            "Catalog models are precedents, not normative OntoUML rules."
        ),
    }

@mcp.tool()
async def inspect_catalog_model(
    graph: str,
    element_limit: int = 150,
) -> dict:
    """
    Inspect one OntoUML catalog model as a modeling precedent.

    Returns metadata plus its main OntoUML classes, stereotypes,
    relations and generalizations. Use after find_catalog_models().
    Treat the model as an example: normative decisions must still use
    structured OntoUML knowledge and executable validation.
    """
    graph = _validate_model_graph(graph)
    element_limit = max(20, min(element_limit, 300))

    # --------------------------------------------------------------
    # 1. Metadata
    # --------------------------------------------------------------

    metadata_query = f"""
    PREFIX dct:  <http://purl.org/dc/terms/>
    PREFIX dcat: <http://www.w3.org/ns/dcat#>
    PREFIX ok:   <{OK_NS}>

    SELECT
        ?model
        ?title
        ?language
        ?keyword
        ?theme
    WHERE {{
        GRAPH <{CATALOG_GRAPH}> {{
            ?model ok:localGraph <{graph}> .

            OPTIONAL {{ ?model dct:title ?title }}
            OPTIONAL {{ ?model dct:language ?language }}
            OPTIONAL {{ ?model dcat:keyword ?keyword }}
            OPTIONAL {{ ?model dcat:theme ?theme }}
        }}
    }}
    """

    metadata_result = await _query_fuseki(metadata_query)
    metadata_bindings = (
        metadata_result
        .get("results", {})
        .get("bindings", [])
    )

    metadata = {
        "model_uri": None,
        "title": None,
        "languages": set(),
        "keywords": set(),
        "themes": set(),
    }

    for b in metadata_bindings:
        metadata["model_uri"] = (
            metadata["model_uri"]
            or _binding_value(b, "model")
        )

        metadata["title"] = (
            metadata["title"]
            or _binding_value(b, "title")
        )

        if value := _binding_value(b, "language"):
            metadata["languages"].add(value)

        if value := _binding_value(b, "keyword"):
            metadata["keywords"].add(value)

        if value := _binding_value(b, "theme"):
            metadata["themes"].add(value)

    # --------------------------------------------------------------
    # 2. Classes
    # --------------------------------------------------------------

    classes_query = f"""
    PREFIX ontouml: <{ONTOUML_NS}>

    SELECT DISTINCT
        ?class
        ?name
        ?stereotype
    WHERE {{
        GRAPH <{graph}> {{
            ?class a ontouml:Class ;
                   ontouml:name ?name .

            OPTIONAL {{
                ?class ontouml:stereotype ?stereotype .
            }}
        }}
    }}
    ORDER BY LCASE(STR(?name))
    LIMIT {element_limit}
    """

    classes_result = await _query_fuseki(classes_query)

    classes = []

    for b in classes_result.get("results", {}).get("bindings", []):
        stereotype = _binding_value(b, "stereotype")

        classes.append({
            "uri": _binding_value(b, "class"),
            "name": _binding_value(b, "name"),
            "stereotype": _local_name(stereotype),
            "stereotype_iri": stereotype,
        })

    # --------------------------------------------------------------
    # 3. Relations
    # --------------------------------------------------------------

    relations_query = f"""
    PREFIX ontouml: <{ONTOUML_NS}>

    SELECT DISTINCT
        ?relation
        ?name
        ?stereotype
        ?source
        ?sourceName
        ?target
        ?targetName
    WHERE {{
        GRAPH <{graph}> {{
            ?relation a ontouml:Relation .

            OPTIONAL {{
                ?relation ontouml:name ?name .
            }}

            OPTIONAL {{
                ?relation ontouml:stereotype ?stereotype .
            }}

            OPTIONAL {{
                ?relation ontouml:sourceEnd ?sourceEnd .
                ?sourceEnd ontouml:propertyType ?source .

                OPTIONAL {{
                    ?source ontouml:name ?sourceName .
                }}
            }}

            OPTIONAL {{
                ?relation ontouml:targetEnd ?targetEnd .
                ?targetEnd ontouml:propertyType ?target .

                OPTIONAL {{
                    ?target ontouml:name ?targetName .
                }}
            }}
        }}
    }}
    LIMIT {element_limit}
    """

    relations_result = await _query_fuseki(relations_query)

    relations = []

    for b in relations_result.get("results", {}).get("bindings", []):
        stereotype = _binding_value(b, "stereotype")

        relations.append({
            "uri": _binding_value(b, "relation"),
            "name": _binding_value(b, "name"),
            "stereotype": _local_name(stereotype),
            "stereotype_iri": stereotype,
            "source": {
                "uri": _binding_value(b, "source"),
                "name": _binding_value(b, "sourceName"),
            },
            "target": {
                "uri": _binding_value(b, "target"),
                "name": _binding_value(b, "targetName"),
            },
        })

    # --------------------------------------------------------------
    # 4. Generalizations
    # --------------------------------------------------------------

    generalizations_query = f"""
    PREFIX ontouml: <{ONTOUML_NS}>

    SELECT DISTINCT
        ?generalization
        ?specific
        ?specificName
        ?general
        ?generalName
    WHERE {{
        GRAPH <{graph}> {{
            ?generalization a ontouml:Generalization ;
                            ontouml:specific ?specific ;
                            ontouml:general ?general .

            OPTIONAL {{
                ?specific ontouml:name ?specificName .
            }}

            OPTIONAL {{
                ?general ontouml:name ?generalName .
            }}
        }}
    }}
    LIMIT {element_limit}
    """

    generalizations_result = await _query_fuseki(
        generalizations_query
    )

    generalizations = []

    for b in (
        generalizations_result
        .get("results", {})
        .get("bindings", [])
    ):
        generalizations.append({
            "uri": _binding_value(b, "generalization"),
            "specific": {
                "uri": _binding_value(b, "specific"),
                "name": _binding_value(b, "specificName"),
            },
            "general": {
                "uri": _binding_value(b, "general"),
                "name": _binding_value(b, "generalName"),
            },
        })

    # --------------------------------------------------------------
    # 5. Statistics
    # --------------------------------------------------------------

    stats_query = f"""
    PREFIX ontouml: <{ONTOUML_NS}>

    SELECT
        (COUNT(DISTINCT ?class) AS ?classes)
        (COUNT(DISTINCT ?relation) AS ?relations)
        (COUNT(DISTINCT ?generalization) AS ?generalizations)
    WHERE {{
        GRAPH <{graph}> {{
            OPTIONAL {{
                ?class a ontouml:Class .
            }}

            OPTIONAL {{
                ?relation a ontouml:Relation .
            }}

            OPTIONAL {{
                ?generalization a ontouml:Generalization .
            }}
        }}
    }}
    """

    stats_result = await _query_fuseki(stats_query)

    stats_bindings = (
        stats_result
        .get("results", {})
        .get("bindings", [])
    )

    stats = {}

    if stats_bindings:
        b = stats_bindings[0]

        stats = {
            "classes": int(
                _binding_value(b, "classes", "0")
            ),
            "relations": int(
                _binding_value(b, "relations", "0")
            ),
            "generalizations": int(
                _binding_value(b, "generalizations", "0")
            ),
        }

    # Convert sets for JSON serialization.
    metadata["languages"] = sorted(metadata["languages"])
    metadata["keywords"] = sorted(metadata["keywords"])
    metadata["themes"] = sorted(metadata["themes"])

    return {
        "graph": graph,
        "model_id": graph.removeprefix(MODEL_GRAPH_PREFIX),
        "metadata": metadata,
        "statistics": stats,
        "classes": classes,
        "relations": relations,
        "generalizations": generalizations,
        "interpretation": (
            "This is an existing catalog model and may provide modeling "
            "precedents. Its structures are examples, not normative "
            "OntoUML constraints."
        ),
    }

@mcp.tool()
async def find_modeling_pattern(
    focal_stereotype: str,
    concept_terms: list[str] | None = None,
    related_stereotypes: list[str] | None = None,
    limit: int = 30,
) -> dict:
    """
    Find structural OntoUML modeling precedents across the model catalog.

    Use when you want to know how concepts with a given OntoUML
    stereotype have actually been modeled in existing models.

    concept_terms optionally narrows results by element names.
    related_stereotypes optionally narrows results to occurrences whose
    generalizations or relations involve those stereotypes.

    Results are empirical catalog evidence, not normative OntoUML rules.
    """

    focal_iri = _stereotype_iri(focal_stereotype)
    limit = max(1, min(limit, 100))

    terms = [
        t.strip()
        for t in (concept_terms or [])
        if t and t.strip()
    ]

    related = {
        s.strip().lower()
        for s in (related_stereotypes or [])
        if s and s.strip()
    }

    name_filter = ""

    if terms:
        conditions = " || ".join(
            f'CONTAINS(LCASE(STR(?name)), '
            f'LCASE("{_sparql_escape(t)}"))'
            for t in terms
        )
        name_filter = f"FILTER({conditions})"

    query = f"""
    PREFIX ontouml: <{ONTOUML_NS}>

    SELECT DISTINCT ?g ?element ?name
    WHERE {{
      GRAPH ?g {{
        ?element a ontouml:Class ;
                 ontouml:stereotype <{focal_iri}> ;
                 ontouml:name ?name .
      }}

      FILTER(
        STRSTARTS(
          STR(?g),
          "{MODEL_GRAPH_PREFIX}"
        )
      )

      {name_filter}
    }}
    ORDER BY LCASE(STR(?name))
    LIMIT {limit}
    """

    result = await _query_fuseki(query)

    occurrences = []

    for b in result.get("results", {}).get("bindings", []):

        graph = _binding_value(b, "g")
        element = _binding_value(b, "element")
        name = _binding_value(b, "name")

        # ----------------------------------------------------------
        # Generalizations involving the focal element
        # ----------------------------------------------------------

        gen_query = f"""
        PREFIX ontouml: <{ONTOUML_NS}>

        SELECT DISTINCT
          ?direction
          ?other
          ?otherName
          ?otherStereotype
        WHERE {{
          {{
            GRAPH <{graph}> {{
              ?gen a ontouml:Generalization ;
                   ontouml:specific <{element}> ;
                   ontouml:general ?other .

              OPTIONAL {{ ?other ontouml:name ?otherName }}
              OPTIONAL {{
                ?other ontouml:stereotype ?otherStereotype
              }}

              BIND("generalizes_to" AS ?direction)
            }}
          }}
          UNION
          {{
            GRAPH <{graph}> {{
              ?gen a ontouml:Generalization ;
                   ontouml:general <{element}> ;
                   ontouml:specific ?other .

              OPTIONAL {{ ?other ontouml:name ?otherName }}
              OPTIONAL {{
                ?other ontouml:stereotype ?otherStereotype
              }}

              BIND("specialized_by" AS ?direction)
            }}
          }}
        }}
        """

        gen_result = await _query_fuseki(gen_query)

        generalizations = []

        for gb in gen_result.get("results", {}).get("bindings", []):
            generalizations.append({
                "direction": _binding_value(gb, "direction"),
                "element": _binding_value(gb, "other"),
                "name": _binding_value(gb, "otherName"),
                "stereotype": _local_name(
                    _binding_value(gb, "otherStereotype")
                ),
            })

        neighborhood = await _get_structural_neighborhood(
            element,
            graph,
        )

        occurrence = {
            "graph": graph,
            "model_id": graph.removeprefix(MODEL_GRAPH_PREFIX),
            "element": element,
            "name": name,
            "stereotype": _local_name(focal_iri),
            "generalizations": generalizations,
            "relations": neighborhood["relations"],
        }

        if related:
            observed = {
                x["stereotype"].lower()
                for x in generalizations
                if x.get("stereotype")
            }

            observed |= {
                x["other_stereotype"].lower()
                for x in neighborhood["relations"]
                if x.get("other_stereotype")
            }

            observed |= {
                x["relation_stereotype"].lower()
                for x in neighborhood["relations"]
                if x.get("relation_stereotype")
            }

            if not observed.intersection(related):
                continue

        occurrences.append(occurrence)

    graphs_examined = await _catalog_graph_count()

    return {
        "focal_stereotype": _local_name(focal_iri),
        "concept_terms": terms,
        "related_stereotypes": sorted(related),
        "catalog_graphs_examined": graphs_examined,
        "occurrences_returned": len(occurrences),
        "occurrences": occurrences,
        "evidence_type": "empirical_catalog_precedent",
        "warning": (
            "Catalog frequency and precedent do not establish "
            "normative OntoUML correctness."
        ),
    }

@mcp.tool()
async def explain_modeling_decision(
    concept: str,
    candidate_stereotypes: list[str],
    context: str | None = None,
    catalog_terms: list[str] | None = None,
) -> dict:
    """
    Gather evidence for an OntoUML modeling decision.

    Combines formal structured knowledge and catalog precedents for
    candidate stereotypes. It does not decide when business semantics
    are insufficient.

    Use the returned evidence to explain consequences, identify missing
    facts, and formulate questions for the domain expert.
    """

    candidates = [
        s.strip()
        for s in candidate_stereotypes
        if s and s.strip()
    ]

    if not candidates:
        raise ValueError(
            "At least one candidate stereotype is required."
        )

    decision_evidence = []

    for candidate in candidates:

        stereotype_iri = _stereotype_iri(candidate)

        knowledge_query = f"""
        PREFIX ontouml: <{ONTOUML_NS}>
        PREFIX ok: <https://w3id.org/ontouml/knowledge#>

        SELECT DISTINCT
          ?p
          ?o
        WHERE {{
          GRAPH <urn:ontouml:structured-knowledge> {{
            <{stereotype_iri}> ?p ?o .
          }}
        }}
        """

        knowledge_result = await _query_fuseki(
            knowledge_query
        )

        formal_properties = []

        for b in (
            knowledge_result
            .get("results", {})
            .get("bindings", [])
        ):
            formal_properties.append({
                "property": _local_name(
                    _binding_value(b, "p")
                ),
                "value": _binding_value(b, "o"),
            })

        constraints_query = f"""
        PREFIX ok: <https://w3id.org/ontouml/knowledge#>

        SELECT DISTINCT
          ?constraint
          ?code
          ?type
          ?modality
          ?sourceText
        WHERE {{
          GRAPH <urn:ontouml:structured-knowledge> {{
            ?constraint ok:appliesTo <{stereotype_iri}> .

            OPTIONAL {{ ?constraint ok:code ?code }}
            OPTIONAL {{
              ?constraint ok:constraintType ?type
            }}
            OPTIONAL {{
              ?constraint ok:modality ?modality
            }}
            OPTIONAL {{
              ?constraint ok:sourceText ?sourceText
            }}
          }}
        }}
        """

        constraints_result = await _query_fuseki(
            constraints_query
        )

        constraints = []

        for b in (
            constraints_result
            .get("results", {})
            .get("bindings", [])
        ):
            constraints.append({
                "constraint": _binding_value(
                    b, "constraint"
                ),
                "code": _binding_value(b, "code"),
                "type": _local_name(
                    _binding_value(b, "type")
                ),
                "modality": _local_name(
                    _binding_value(b, "modality")
                ),
                "source_text": _binding_value(
                    b, "sourceText"
                ),
            })

        # Small sample of empirical precedents.
        pattern_query = f"""
        PREFIX ontouml: <{ONTOUML_NS}>

        SELECT DISTINCT
          ?g
          ?element
          ?name
        WHERE {{
          GRAPH ?g {{
            ?element a ontouml:Class ;
                     ontouml:stereotype <{stereotype_iri}> ;
                     ontouml:name ?name .
          }}

          FILTER(
            STRSTARTS(
              STR(?g),
              "{MODEL_GRAPH_PREFIX}"
            )
          )

          FILTER(
            CONTAINS(
              LCASE(STR(?name)),
              LCASE("{_sparql_escape(concept)}")
            )
          )
        }}
        LIMIT 10
        """

        pattern_result = await _query_fuseki(
            pattern_query
        )

        precedents = []

        for b in (
            pattern_result
            .get("results", {})
            .get("bindings", [])
        ):
            precedents.append({
                "graph": _binding_value(b, "g"),
                "element": _binding_value(b, "element"),
                "name": _binding_value(b, "name"),
            })

        decision_evidence.append({
            "candidate": candidate,
            "stereotype_iri": stereotype_iri,
            "formal_properties": formal_properties,
            "constraints": constraints,
            "catalog_precedents": precedents,
        })

    return {
        "concept": concept,
        "context": context,
        "candidates": decision_evidence,
        "instruction": (
            "Compare the ontological commitments of the candidates. "
            "Do not infer missing business semantics from catalog "
            "frequency. Identify unresolved facts and ask the domain "
            "expert when those facts determine the stereotype."
        ),
    }

@mcp.tool()
async def create_working_model(
    name: str,
    description: str | None = None,
) -> dict:
    """
    Create a persistent OntoUML working model.

    Use when beginning a new modeling activity.
    The returned model_id identifies the model in subsequent calls.
    """

    model = create_model(
        name=name,
        description=description,
    )

    return {
        "model": model,
        "instruction": (
            "Use apply_model_changes() to modify "
            "this model. Do not maintain a separate "
            "authoritative copy in conversation."
        ),
    }

@mcp.tool()
async def get_working_model(
    model_id: str,
) -> dict:
    """
    Retrieve the authoritative current state and version
    of an OntoUML working model.
    """

    return {
        "model": get_model(model_id)
    }

@mcp.tool()
async def apply_model_changes(
    model_id: str,
    expected_version: int,
    changes: list[dict],
    reason: str | None = None,
) -> dict:
    """
    Apply controlled changes to an OntoUML working model.

    Changes are atomic: either all requested operations succeed
    or none are persisted.

    Supported operations:
    add_class, update_class, remove_class,
    add_generalization, remove_generalization,
    add_relation, update_relation, remove_relation,
    record_decision, resolve_decision.

    Always use the current model version as expected_version.
    Record important ontological decisions and their evidence.
    """

    try:
        model = apply_changes(
            model_id=model_id,
            expected_version=expected_version,
            changes=changes,
            reason=reason,
        )

    except WorkingModelError as exc:
        return {
            "success": False,
            "error": type(exc).__name__,
            "message": str(exc),
        }

    return {
        "success": True,
        "model_id": model_id,
        "version": model["version"],
        "model": model,
        "next_action":
            "Assess the model after meaningful structural changes.",
    }

@mcp.tool()
async def assess_model(
    model_id: str,
) -> dict:
    """
    Assess the authoritative current OntoUML working model.

    Identifies incomplete modeling decisions and retrieves formal
    structured constraints relevant to the stereotypes in use.

    Catalog precedents are empirical evidence only. Formal validation
    remains the responsibility of validate_model when an executable
    RDF representation is available.
    """

    model = get_model(model_id)

    classes = model.get("classes", [])
    relations = model.get("relations", [])
    generalizations = model.get(
        "generalizations",
        [],
    )
    decisions = model.get(
        "decisions",
        [],
    )

    by_id = {
        cls["id"]: cls
        for cls in classes
        if cls.get("id")
    }

    issues = []
    elements = []

    for cls in classes:

        cls_id = cls.get("id")
        name = cls.get("name")
        stereotype = cls.get("stereotype")

        if not stereotype:

            issues.append({
                "element_id": cls_id,
                "element": name,
                "type": "missing_stereotype",
                "severity": "unresolved",
                "recommended_action":
                    "Use explain_modeling_decision.",
            })

            continue

        stereotype_iri = _stereotype_iri(
            stereotype
        )

        query = f"""
        PREFIX ok:
          <https://w3id.org/ontouml/knowledge#>

        SELECT DISTINCT
          ?constraint
          ?code
          ?type
          ?modality
          ?cardinality
          ?relation
          ?sourceText
        WHERE {{
          GRAPH
            <urn:ontouml:structured-knowledge>
          {{
            ?constraint
              ok:appliesTo
              <{stereotype_iri}> .

            OPTIONAL {{
              ?constraint ok:code ?code
            }}

            OPTIONAL {{
              ?constraint
                ok:constraintType ?type
            }}

            OPTIONAL {{
              ?constraint
                ok:modality ?modality
            }}

            OPTIONAL {{
              ?constraint
                ok:cardinality ?cardinality
            }}

            OPTIONAL {{
              ?constraint
                ok:relation ?relation
            }}

            OPTIONAL {{
              ?constraint
                ok:sourceText ?sourceText
            }}
          }}
        }}
        """

        result = await _query_fuseki(query)

        constraints = []

        for b in (
            result
            .get("results", {})
            .get("bindings", [])
        ):

            constraints.append({
                "constraint":
                    _binding_value(
                        b,
                        "constraint",
                    ),
                "code":
                    _binding_value(
                        b,
                        "code",
                    ),
                "type":
                    _local_name(
                        _binding_value(
                            b,
                            "type",
                        )
                    ),
                "modality":
                    _local_name(
                        _binding_value(
                            b,
                            "modality",
                        )
                    ),
                "cardinality":
                    _binding_value(
                        b,
                        "cardinality",
                    ),
                "relation":
                    _local_name(
                        _binding_value(
                            b,
                            "relation",
                        )
                    ),
                "source_text":
                    _binding_value(
                        b,
                        "sourceText",
                    ),
            })

        parents = []

        for gen in generalizations:

            if gen.get("specific") != cls_id:
                continue

            parent = by_id.get(
                gen.get("general")
            )

            if parent:
                parents.append({
                    "id": parent.get("id"),
                    "name": parent.get("name"),
                    "stereotype":
                        parent.get("stereotype"),
                })

        connected_relations = [
            rel
            for rel in relations
            if rel.get("source") == cls_id
            or rel.get("target") == cls_id
        ]

        elements.append({
            "id": cls_id,
            "name": name,
            "stereotype": stereotype,
            "status": cls.get("status"),
            "parents": parents,
            "connected_relations":
                connected_relations,
            "applicable_constraints":
                constraints,
        })

    unresolved_decisions = [
        d
        for d in decisions
        if d.get("status")
        in {"proposed", "unresolved"}
    ]

    if unresolved_decisions:
        for decision in unresolved_decisions:
            issues.append({
                "decision_id":
                    decision.get("decision_id"),
                "element_id":
                    decision.get("subject"),
                "type":
                    "unresolved_modeling_decision",
                "severity": "unresolved",
                "property":
                    decision.get("property"),
                "proposed_value":
                    decision.get("value"),
            })

    status = (
        "needs_decisions"
        if issues
        else "ready_for_validation"
    )

    return {
        "model_id": model_id,
        "version": model["version"],
        "status": status,

        "summary": {
            "classes": len(classes),
            "relations": len(relations),
            "generalizations":
                len(generalizations),
            "decisions": len(decisions),
            "issues": len(issues),
        },

        "issues": issues,
        "elements": elements,

        "instruction": (
            "Resolve semantic uncertainty using "
            "explain_modeling_decision and "
            "find_modeling_pattern. Catalog evidence "
            "must not replace domain evidence or "
            "formal OntoUML constraints."
        ),
    }

if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=8001,
        streamable_http_path="/ontouml-mcp",
        stateless_http=True,
        json_response=True,
    )