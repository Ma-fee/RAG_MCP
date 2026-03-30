import os
import sys
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# 获取当前虚拟环境的 Python 路径
python_path = os.path.join(os.path.dirname(__file__), ".venv", "bin", "python")
workspace_dir = os.path.dirname(os.path.abspath(__file__))

server_params = StdioServerParameters(
    command=python_path,
    args=["-m", "main"],
    env={**os.environ, "PYTHONPATH": workspace_dir + "/src", "MCP_TRANSPORT": "stdio"},
)

async def main():
    # 默认目录
    directory_path = sys.argv[1] if len(sys.argv) > 1 else "/Users/admin/Downloads/rag_mcp/dataset"
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print(f"正在为目录：{directory_path} 构建索引...")
            
            result = await session.call_tool("rag_rebuild_index", {"directory_path": directory_path})
            print(result.content[0].text)

if __name__ == "__main__":
    asyncio.run(main())
