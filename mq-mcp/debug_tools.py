import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    server_params = StdioServerParameters(
        command="uv",
        args=["run", "mcp", "run", "server.py"],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()

            print("Available MCP tools:")
            for tool in result.tools:
                print(f"- {tool.name}")
                if tool.description:
                    print(f"  {tool.description}")

if __name__ == "__main__":
    asyncio.run(main())
