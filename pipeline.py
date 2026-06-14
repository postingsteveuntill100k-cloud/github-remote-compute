import asyncio
import os
import aiohttp
import ollama
from mcp import ClientSession
from mcp.client.sse import sse_client

class GeminiOrchestrator:
    def __init__(self, secrets_path="/home/hecker/mcp_server0local/-mcp_server0local/.secerts/keys.txt"):
        self.keys = self._load_keys(secrets_path)
        self.current_index = 0
        if not self.keys:
            raise ValueError("No Gemini API keys found. Please check secrets_path.")

    def _load_keys(self, path):
        try:
            with open(path, 'r') as f:
                return [line.strip() for line in f if line.strip()]
        except Exception as e:
            print(f"Error loading keys: {e}")
            return []

    def _get_next_key(self):
        self.current_index = (self.current_index + 1) % len(self.keys)
        return self.keys[self.current_index]

    async def generate_content(self, prompt, model="gemini-1.5-flash"):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

        for _ in range(len(self.keys)):
            current_key = self.keys[self.current_index]
            headers = {"Content-Type": "application/json"}
            payload = {
                "contents": [{"parts": [{"text": prompt}]}]
            }

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(f"{url}?key={current_key}", headers=headers, json=payload) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if 'candidates' in data and len(data['candidates']) > 0:
                                return data['candidates'][0]['content']['parts'][0]['text']
                            return "No output generated."
                        elif resp.status == 429: # Rate limit
                            print(f"[GeminiOrchestrator] Key rate limited. Rotating key...")
                            self._get_next_key()
                        else:
                            error_text = await resp.text()
                            print(f"[GeminiOrchestrator] API Error {resp.status}: {error_text}")
                            self._get_next_key()
            except Exception as e:
                print(f"[GeminiOrchestrator] Request failed: {e}")
                self._get_next_key()

            await asyncio.sleep(1)

        return "[Fallback] Cloud reasoning unavailable due to exhausted keys or API errors."

class AutoYTPipeline:
    def __init__(self):
        self.gemini = GeminiOrchestrator()
        self.ollama_client = ollama.AsyncClient()
        self.mcp_url = "http://127.0.0.1:8000/sse?api_key=your_secret_agent_key_here"
        self.mcp_session = None
        self.mcp_tools = []

    async def init_mcp(self):
        try:
            self.mcp_streams = sse_client(self.mcp_url)
            streams = await self.mcp_streams.__aenter__()
            self.mcp_session = ClientSession(streams[0], streams[1])
            await self.mcp_session.__aenter__()
            await self.mcp_session.initialize()
            print("✅ [MCP] Connected successfully.")

            tools_response = await self.mcp_session.list_tools()
            self.mcp_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.inputSchema
                    }
                } for t in tools_response.tools
            ]
        except Exception as e:
            print(f"❌ [MCP] Connection Failed: {e}")

    async def cleanup_mcp(self):
        if self.mcp_session:
            await self.mcp_session.__aexit__(None, None, None)
        if hasattr(self, 'mcp_streams'):
            await self.mcp_streams.__aexit__(None, None, None)

    async def execute_mcp_tool(self, tool_name, arguments):
        print(f"🔧 [MCP Executing Tool] {tool_name}: {arguments}")
        if self.mcp_session:
            result = await self.mcp_session.call_tool(tool_name, arguments)
            output = [c.text for c in result.content if c.type == 'text']
            return "\n".join(output)
        return "MCP not connected."

    async def run_local_model(self, model_name, prompt):
        print(f"⚙️ [Local Agent: {model_name}] Starting task...")
        messages = [{"role": "user", "content": prompt}]

        response = await self.ollama_client.chat(
            model=model_name,
            messages=messages,
            tools=self.mcp_tools if model_name == "qwen-coder-agent" else None
        )

        if "tool_calls" in response['message'] and response['message']['tool_calls']:
            messages.append(response['message'])
            for tool_call in response['message']['tool_calls']:
                tool_res = await self.execute_mcp_tool(
                    tool_call['function']['name'],
                    tool_call['function']['arguments']
                )
                messages.append({"role": "tool", "name": tool_call['function']['name'], "content": tool_res})

            final_response = await self.ollama_client.chat(model=model_name, messages=messages)
            return final_response['message']['content']

        return response['message']['content']

    async def route_task(self, task_type, payload):
        if task_type == "plan":
            print(f"☁️ [Cloud Core: Gemini] Planning and Reasoning...")
            return await self.gemini.generate_content(payload)

        elif task_type == "code":
            return await self.run_local_model("qwen-coder-agent", payload)

        elif task_type == "vision":
            return await self.run_local_model("qwen2.5-8k", payload)

        else:
            raise ValueError(f"Unknown task type: {task_type}")

async def main():
    pipeline = AutoYTPipeline()
    await pipeline.init_mcp()

    print("\n--- Pipeline Diagnostic Initialization ---")

    plan_out = await pipeline.route_task("plan", "Plan a very short video about Python.")
    print(f"\n[Plan Output]\n{plan_out[:100]}...\n")

    code_out = await pipeline.route_task("code", "Write a python script that prints 'Hello AutoYT'. Output ONLY code.")
    print(f"\n[Code Output]\n{code_out}\n")

    vision_out = await pipeline.route_task("vision", "What are the common formats for thumbnails?")
    print(f"\n[Vision Output]\n{vision_out[:100]}...\n")

    await pipeline.cleanup_mcp()
    print("--- Diagnostic Complete ---")

if __name__ == "__main__":
    asyncio.run(main())
