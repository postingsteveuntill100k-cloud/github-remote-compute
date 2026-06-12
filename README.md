# MCP Client for Google Cloud SDK Download

This script demonstrates how to connect to an MCP (Model Context Protocol) server via SSE using the official `mcp` Python SDK and remotely execute a bash command to download the Google Cloud CLI SDK archive.

## Usage

Set the `MCP_API_KEY` environment variable with your secret agent key:

```bash
export MCP_API_KEY="your_secret_agent_key_here"
python3 mcp_client.py
```
