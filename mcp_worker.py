import asyncio
import os
import sys
from mcp import ClientSession
from mcp.client.sse import sse_client

async def main():
    # Allow the GCP server IP/URL to be passed in securely via GitHub Secrets/env variables
    gcp_mcp_url = os.environ.get("GCP_MCP_URL")

    if not gcp_mcp_url:
        print("Error: GCP_MCP_URL environment variable is missing.", file=sys.stderr)
        print("Expected format: http://<gcp-ip>:8000/sse", file=sys.stderr)
        sys.exit(1)

    print(f"Attempting to connect to MCP server at {gcp_mcp_url}...")

    # Connect to the GCP MCP server using SSE
    async with sse_client(gcp_mcp_url) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            # Initialize the connection
            await session.initialize()
            print("Successfully connected to the GCP MCP server!")

            # Fetch available tools
            tools_response = await session.list_tools()
            tools = tools_response.tools

            print("\nAvailable tools on GCP MCP:")
            for tool in tools:
                print(f"- {tool.name}: {tool.description}")

            # Example: You can now call the tools provided by the GCP server.
            # Example call for DuckDuckGo (Assuming tool is named 'duckduckgo_search')
            # result = await session.call_tool("duckduckgo_search", {"query": "GitHub Actions MCP"})
            # print(result)

            # Keep the runner alive to do whatever heavy lifting is needed
            print("\nRunner initialized and ready for work.")
            # Add your heavy computation / video rendering logic here!

if __name__ == "__main__":
    asyncio.run(main())
