import asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client

async def main():
    # Replace this with your actual Tailscale URL and Secret Key
    url = "https://hackme.tail160e56.ts.net/sse?api_key=your_secret_agent_key_here"

    print(f"Attempting connection to: {url.split('?')[0]}...")

    try:
        # Connect using the official SDK
        async with sse_client(url) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                print("✅ Connection established and authenticated!\n")

                # List tools to verify server capabilities
                print("Fetching available tools...")
                tools_response = await session.list_tools()
                for tool in tools_response.tools:
                    print(f" - {tool.name}: {tool.description}")

                # Execute a test web search
                print("\nExecuting test web_search for 'dogs'...")
                result = await session.call_tool("web_search", {"query": "dogs", "max_results": 3})

                print("\n--- Search Results ---")
                print(result.content[0].text)

    except Exception as e:
        print(f"\n❌ Connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
