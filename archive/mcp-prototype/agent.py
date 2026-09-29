import asyncio
import sys

from agents import Agent, Runner
from agents.mcp import MCPServerStdio


async def main():

    async with MCPServerStdio(
        name="Northmart Knowledge Graph",
        params={
            "command": sys.executable,
            "args": ["server.py"],
        },
        cache_tools_list=True,
    ) as server:

        agent = Agent(
            name="Northmart Knowledge Graph Agent",

            instructions="""
You are connected to an RDF Knowledge Graph.

You do NOT know its business model in advance.

Rules:

1. Do not assume the existence of business classes or properties.
2. Use discover_graph when you need to understand the graph vocabulary.
3. Use query_sparql to retrieve actual business information.
4. Build SPARQL queries only from vocabulary you have discovered.
5. Distinguish RDF/RDFS/OWL schema knowledge from instance data.
6. Never invent facts that are not returned by the Knowledge Graph.
7. Explain briefly which semantic relationships you used to answer.
""",

            mcp_servers=[server],
        )

        question = """
What parties exist in the knowledge graph,
and what information do we know about them?
"""

        print("\nQUESTION")
        print(question)

        result = await Runner.run(agent, question)

        print("\nANSWER")
        print(result.final_output)


if __name__ == "__main__":
    asyncio.run(main())