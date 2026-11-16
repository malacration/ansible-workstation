"""Smoke test the installed MCP and Chrome in an isolated, headless profile."""

import argparse
import asyncio
import os
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def check(command):
    parameters = StdioServerParameters(
        command=str(command),
        args=['--headless', '--isolated', '--no-usage-statistics'],
        env=dict(
            os.environ,
            PATH=str(Path.home() / '.local/bin') + ':/usr/local/bin:/usr/bin:/bin',
            CHROME_DEVTOOLS_MCP_NO_USAGE_STATISTICS='1',
            CHROME_DEVTOOLS_MCP_NO_UPDATE_CHECKS='1',
        ),
    )
    async with asyncio.timeout(60):
        async with stdio_client(parameters) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                available = await session.list_tools()
                assert 'new_page' in {tool.name for tool in available.tools}
                result = await session.call_tool('new_page', {'url': 'about:blank'})
                error = getattr(result, 'is_error', getattr(result, 'isError', False))
                assert not error, result
                print(f'MCP validado: {len(available.tools)} ferramentas e Chrome headless abrindo about:blank.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--command', type=Path, default=Path.home() / '.local/bin/chrome-devtools-mcp')
    options = parser.parse_args()
    asyncio.run(check(options.command))
