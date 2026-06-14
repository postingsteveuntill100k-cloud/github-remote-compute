# AutoYT Hybrid Local AI Core

This project orchestrates a hybrid AI deployment on a local/remote environment specifically tuned for video automation workflows.

## Architecture
- **Cloud Heavy Reasoner**: Routes complex tasks to the Gemini API (`gemini_orchestrator.py`).
- **Local Vision/Multimodal**: Uses `qwen2.5-8k` locally for image and media understanding.
- **Local Agentic Coder**: Uses `qwen-coder-agent` (4-bit quantized) to write format-specific code.

## System Restrictions
Ollama is hard-capped via Systemd (`~/.config/systemd/user/ollama.service`) to strictly prevent lag or CPU starvation on the host machine:
- `MemoryMax=4G`
- `CPUQuota=50%`
- `OLLAMA_NUM_PARALLEL=1`

## MCP (Model Context Protocol) Integration
Both local and cloud instances wrap around the host's MCP server endpoint (`http://127.0.0.1:8000/sse`) via the standard `mcp` Python SDK, bridging LLM tool calls (e.g. bash scripting, web searching) directly to the environment.

## Secrets
Keys are natively stored outside the repo tree under `.secerts/keys.txt`.
