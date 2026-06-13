import asyncio
import os
import sys
from mcp import ClientSession
from mcp.client.sse import sse_client

async def run_remote_bash(session, command):
    print(f"Executing: {command}")
    result = await session.call_tool("execute_bash", {"command": command})
    for content in result.content:
        if content.type == "text":
            print(content.text)

async def main():
    api_key = os.environ.get("MCP_API_KEY")
    if not api_key:
        print("Error: MCP_API_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    url = f"https://hackme.tail160e56.ts.net/sse?api_key={api_key}"

    try:
        async with sse_client(url) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                print("✅ Connection established and authenticated!\n")

                # 1. Create project directory
                await run_remote_bash(session, "mkdir -p auto-yt/ollama/bin && ls -la auto-yt")

                # 2. Install Ollama natively
                await run_remote_bash(session, "curl -L https://github.com/ollama/ollama/releases/download/v0.1.30/ollama-linux-amd64 -o auto-yt/ollama/bin/ollama && chmod +x auto-yt/ollama/bin/ollama")

                # 3. Configure the Linux service daemon
                service_content = """[Unit]
Description=Ollama Service
After=network-online.target

[Service]
ExecStart=/home/hecker/mcp_server0local/-mcp_server0local/auto-yt/ollama/bin/ollama serve
User=hecker
Group=hecker
Restart=always
RestartSec=3
Environment="OLLAMA_NUM_PARALLEL=1"
CPUQuota=50%

[Install]
WantedBy=default.target"""

                await run_remote_bash(session, f"cat << 'INNEREOF' > auto-yt/ollama/ollama.service\n{service_content}\nINNEREOF")
                await run_remote_bash(session, "mkdir -p ~/.config/systemd/user && mv auto-yt/ollama/ollama.service ~/.config/systemd/user/")

                # 4. Reload daemon and restart service
                await run_remote_bash(session, "systemctl --user daemon-reload && systemctl --user enable --now ollama && systemctl --user restart ollama")

                # 5. Pull model
                # Sleep a bit to make sure service is up
                await run_remote_bash(session, "sleep 5 && auto-yt/ollama/bin/ollama pull qwen2.5:1.5b")

                # 6. Create modular README.md
                readme_content = """# Local AI Workspace

This workspace is set up to run local LLMs efficiently without bogging down the main desktop environment.

## Directory Structure
- `auto-yt/ollama/bin/ollama`: The natively downloaded Ollama executable (Linux amd64).
- `auto-yt/ollama/`: The main project folder containing logs and binaries.

## System Configuration
The Ollama service is configured via a user-level Systemd unit (`~/.config/systemd/user/ollama.service`) to strictly bound its resource usage:
- **CPU Quota**: Limited to `50%` using the `CPUQuota=50%` directive.
- **Concurrency**: Forced to single-stream execution via `Environment="OLLAMA_NUM_PARALLEL=1"`.

## Models
Currently pulled models for this workspace:
- **qwen2.5:1.5b**: A specialized automation model.
"""
                await run_remote_bash(session, f"cat << 'INNEREOF' > auto-yt/README.md\n{readme_content}\nINNEREOF")

                print("\n✅ Setup complete!")

    except Exception as e:
        print(f"\n❌ Setup failed: {e}")
        if hasattr(e, 'exceptions'):
            for sub_e in e.exceptions:
                print(repr(sub_e))

if __name__ == "__main__":
    asyncio.run(main())
