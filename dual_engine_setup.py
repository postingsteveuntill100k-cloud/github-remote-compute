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

                # 1. Update Systemd Constraints
                print("--- 1. Updating Systemd Constraints ---")
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
MemoryMax=4G

[Install]
WantedBy=default.target"""

                await run_remote_bash(session, f"cat << 'INNEREOF' > ~/.config/systemd/user/ollama.service\n{service_content}\nINNEREOF")
                await run_remote_bash(session, "systemctl --user daemon-reload && systemctl --user restart ollama")

                # 2. Setup Engine 1 (Qwen)
                print("\n--- 2. Setting up Engine 1 (Qwen) ---")
                qwen_modelfile = """FROM qwen2.5:0.5b
PARAMETER num_ctx 8192"""
                await run_remote_bash(session, f"cat << 'INNEREOF' > auto-yt/ollama/Modelfile.qwen\n{qwen_modelfile}\nINNEREOF")
                await run_remote_bash(session, "auto-yt/ollama/bin/ollama pull qwen2.5:0.5b")
                await run_remote_bash(session, "auto-yt/ollama/bin/ollama create qwen2.5-8k -f auto-yt/ollama/Modelfile.qwen")

                # 3 & 4. Setup Engine 2 (Gemma GGUF)
                print("\n--- 3 & 4. Setting up Engine 2 (Gemma GGUF) ---")
                download_cmd = """cat << 'PYEOF' > /tmp/dl_gemma.py
import os
os.system("pip install -q huggingface_hub")
from huggingface_hub import hf_hub_download
import shutil

try:
    path = hf_hub_download(repo_id="bartowski/gemma-2-2b-it-GGUF", filename="gemma-2-2b-it-Q4_K_M.gguf")
    os.system("mkdir -p /tmp/gemma")
    shutil.copy(path, "/tmp/gemma/gemma.gguf")
    print("Downloaded successfully")
except Exception as e:
    print(f"Error: {e}")
PYEOF
python3 /tmp/dl_gemma.py"""
                await run_remote_bash(session, download_cmd)

                gemma_modelfile = """FROM /tmp/gemma/gemma.gguf
PARAMETER num_ctx 8192"""
                await run_remote_bash(session, f"cat << 'INNEREOF' > auto-yt/ollama/Modelfile.gemma\n{gemma_modelfile}\nINNEREOF")
                await run_remote_bash(session, "auto-yt/ollama/bin/ollama create gemma4-mobile -f auto-yt/ollama/Modelfile.gemma")

                # 5. Clean up and Generate Code
                print("\n--- 5. Cleaning up and Generating Code ---")
                await run_remote_bash(session, "rm -rf /tmp/gemma")
                prompt = "Write a small python program for a phone book. Output ONLY the raw python code without any markdown formatting or explanation."
                await run_remote_bash(session, f"auto-yt/ollama/bin/ollama run gemma4-mobile '{prompt}' > auto-yt/phone_book.py")
                await run_remote_bash(session, "cat auto-yt/phone_book.py | grep -v '```' > auto-yt/phone_book_clean.py && mv auto-yt/phone_book_clean.py auto-yt/phone_book.py")
                await run_remote_bash(session, "cat auto-yt/phone_book.py")

                print("\n✅ Dual-Engine Setup complete!")

    except Exception as e:
        print(f"\n❌ Setup failed: {e}")
        if hasattr(e, 'exceptions'):
            for sub_e in e.exceptions:
                print(repr(sub_e))

if __name__ == "__main__":
    asyncio.run(main())
