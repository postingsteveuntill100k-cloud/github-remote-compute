import asyncio
import os
import sys
from mcp import ClientSession
from mcp.client.sse import sse_client

async def main():
    api_key = os.environ.get("MCP_API_KEY")
    if not api_key:
        print("Error: MCP_API_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    url = f"https://hackme.tail160e56.ts.net/sse?api_key={api_key}"

    try:
        # Connect using the official SDK
        async with sse_client(url) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                print("✅ Connection established and authenticated!\n")

                print("Sending execute_bash command...")
                bash_payload = {
                    "command": "curl -O https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-cli-linux-x86_64.tar.gz && ls -la google-cloud-cli-linux-x86_64.tar.gz"
                }

                result = await session.call_tool("execute_bash", bash_payload)
                print("\nServer Output:")
                for content in result.content:
                    if content.type == "text":
                        print(content.text)

    except Exception as e:
        print(f"\n❌ Connection failed: {e}")
        if hasattr(e, 'exceptions'):
            for sub_e in e.exceptions:
                print(repr(sub_e))

if __name__ == "__main__":
    asyncio.run(main())
