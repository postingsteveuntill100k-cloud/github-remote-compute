import asyncio
import os
import sys
from mcp import ClientSession
from mcp.client.sse import sse_client

async def main():
    # Loopback connection for local MCP Server
    url = "http://127.0.0.1:8000/sse?api_key=your_secret_agent_key_here"

    try:
        async with sse_client(url) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                print("✅ [Gemma Startup] Connected to local MCP server at 127.0.0.1:8000")

                tools_response = await session.list_tools()
                tools_names = [tool.name for tool in tools_response.tools]
                print(f"Available tools for Gemma: {', '.join(tools_names)}")

                # Further integration with the local Gemma model can happen here
                # enabling it to execute bash commands or search the web via DuckDuckGo.

    except Exception as e:
        print(f"❌ Connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
