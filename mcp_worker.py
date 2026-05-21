import asyncio
import os
import sys
import httpx
from mcp import ClientSession

# A simple custom HTTP client transport since the server only uses POST
class HTTPPostClient:
    def __init__(self, url):
        self.url = url
        self.client = httpx.AsyncClient()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    async def send(self, message):
        response = await self.client.post(self.url, json=message)
        response.raise_for_status()
        return response.json()

async def main():
    gcp_mcp_url = os.environ.get("GCP_MCP_URL")

    if not gcp_mcp_url:
        print("Error: GCP_MCP_URL environment variable is missing.", file=sys.stderr)
        sys.exit(1)

    print(f"Attempting to connect to MCP server via POST at {gcp_mcp_url}...")

    # For servers that only accept POST requests, we send JSON-RPC manually or via a custom transport
    async with httpx.AsyncClient() as client:
        # Construct a standard JSON-RPC 2.0 payload to initialize or list tools
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {}
        }

        try:
            response = await client.post(gcp_mcp_url, json=payload)
            response.raise_for_status()

            data = response.json()
            print("Successfully communicated with the GCP MCP server!")
            print("Response:", data)

        except Exception as e:
            print(f"Failed to communicate with server: {e}", file=sys.stderr)

if __name__ == "__main__":
    asyncio.run(main())
