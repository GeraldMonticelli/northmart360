from mcp.server import MCPServer
import httpx
import os


FUSEKI_QUERY_URL = os.getenv(
    "FUSEKI_QUERY_URL",
    "http://localhost:3030/cyfun",
)

ELASTICSEARCH_URL = os.getenv(
    "ELASTICSEARCH_URL",
    "http://localhost:9200",
)

ELASTICSEARCH_INDEX = os.getenv(
    "ELASTICSEARCH_INDEX",
    "cyfun",
)


mcp = MCPServer("cyfun-knowledge")


@mcp.tool()
async def query_sparql(query: str) -> dict:
    """
    Execute a read-only SPARQL query against the CyFun knowledge graph.
    """

    normalized = query.strip().upper()

    if not (
        normalized.startswith("SELECT")
        or normalized.startswith("ASK")
        or normalized.startswith("CONSTRUCT")
        or normalized.startswith("DESCRIBE")
        or normalized.startswith("PREFIX")
    ):
        return {
            "success": False,
            "error": "Only read-only SPARQL queries are allowed.",
        }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            FUSEKI_QUERY_URL,
            params={"query": query},
            headers={
                "Accept": "application/sparql-results+json"
            },
        )

        response.raise_for_status()

        return {
            "success": True,
            "source": "cyfun-knowledge-graph",
            "result": response.json(),
        }


@mcp.tool()
async def search_cyfun_documentation(
    query: str,
    limit: int = 10,
) -> dict:
    """
    Search the indexed CyFun/NIS2 cybersecurity documentation.
    """

    payload = {
        "size": limit,
        "query": {
            "multi_match": {
                "query": query,
                "fields": [
                    "title^3",
                    "heading^2",
                    "text",
                ],
            }
        },
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{ELASTICSEARCH_URL}/{ELASTICSEARCH_INDEX}/_search",
            json=payload,
        )

        response.raise_for_status()

        data = response.json()

    results = []

    for hit in data.get("hits", {}).get("hits", []):
        results.append(
            {
                "score": hit.get("_score"),
                **hit.get("_source", {}),
            }
        )

    return {
        "success": True,
        "source": "cyfun-documentation",
        "query": query,
        "results": results,
    }


if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=8002,
        streamable_http_path="/cyfun-mcp",
        stateless_http=True,
        json_response=True,
    )