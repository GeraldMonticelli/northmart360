from mcp.server import MCPServer
import httpx
import os


FUSEKI_QUERY_URL = os.getenv(
    "FUSEKI_QUERY_URL",
    "http://localhost:3030/northmart",
)

mcp = MCPServer("generic-knowledge-graph")


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

if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=8000,
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
    )