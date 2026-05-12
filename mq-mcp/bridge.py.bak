import asyncio
import os
import json
import sys
from openai import OpenAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# 1. Konfigurera OpenAI
client = OpenAI()

async def run_bridge():
    # 1. Kontrollera om en prompt skickades med som argument från terminalen
    if len(sys.argv) > 1:
        prompt = sys.argv[1]
    else:
        prompt = "Vad blir 18 + 2? Berätta sen ett kort skämt om programmering."

    # 2. Parametrar för att starta din lokala MCP-server
    server_params = StdioServerParameters(
        command="uv",
        args=["run", "mcp", "run", "server.py"],
        env=os.environ.copy()
    )

    print(f"--- Startar bridget (MCP <-> OpenAI) ---")
    print(f"Fråga: {prompt}\n")

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initiera sessionen
            await session.initialize()

            # 3. Hämta lokala verktyg från MCP-servern
            mcp_tools = await session.list_tools()
            
            # 4. Översätt MCP-schema till OpenAI Tool format
            openai_tools = []
            for tool in mcp_tools.tools:
                openai_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.inputSchema
                    }
                })

            # 5. Skicka fråga till OpenAI
            messages = [{"role": "user", "content": prompt}]
            
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                tools=openai_tools
            )

            # 6. Hantera Tool Calls (om modellen vill använda dina lokala verktyg)
            response_message = response.choices[0].message
            if response_message.tool_calls:
                messages.append(response_message)
                
                for tool_call in response_message.tool_calls:
                    name = tool_call.function.name
                    args = json.loads(tool_call.function.arguments)
                    
                    print(f"-> ChatGPT anropar lokalt verktyg: {name}({args})")
                    
                    # Kör verktyget på den lokala MCP-servern
                    result = await session.call_tool(name, args)
                    
                    # Extrahera textresultatet
                    tool_result_text = ""
                    if result.content:
                        for item in result.content:
                            if hasattr(item, 'text'):
                                tool_result_text += item.text
                    
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": tool_result_text
                    })

                # Slutför konversationen med resultaten från verktygen
                final_response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=messages
                )
                print(f"\nChatGPT: {final_response.choices[0].message.content}")
            else:
                print(f"\nChatGPT: {response_message.content}")

if __name__ == "__main__":
    try:
        asyncio.run(run_bridge())
    except Exception as e:
        print(f"\nEtt fel uppstod: {e}")
