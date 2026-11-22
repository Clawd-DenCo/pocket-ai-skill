"""Optional read-only adapter using the official MCP Python SDK.

No writes, OAuth token persistence, or automatic fallback to unscoped tools.
The default session uses a supplied API key; OAuth may be handled by a host MCP client.
"""
import json
from contextlib import asynccontextmanager

from pocket_api import PocketError, ConfigurationError, ResponseError, key_value

URL = 'https://public.heypocketai.com/mcp'
READ_TOOLS = frozenset({'get_account_info','list_pocket_folders','search_pocket_conversations',
                        'search_pocket_actionitems','get_pocket_conversation','query_pocket_meetings'})


class PocketMCP:
    def __init__(self, session):
        self.session = session
        self.tools = None

    async def capabilities(self):
        names, cursor, seen = set(), None, set()
        for _ in range(20):
            try:
                page = await self.session.list_tools(cursor=cursor)
            except Exception:
                raise PocketError('Pocket MCP capability discovery failed') from None
            names.update(t.name for t in page.tools)
            cursor = page.nextCursor
            if not cursor:
                self.tools = names & READ_TOOLS
                return sorted(self.tools)
            if cursor in seen:
                raise ResponseError('MCP tool pagination made no progress')
            seen.add(cursor)
        raise ResponseError('MCP tool listing budget exhausted')

    async def call(self, name, **arguments):
        if name not in READ_TOOLS:
            raise ConfigurationError('Only approved read-only Pocket MCP tools are supported')
        if self.tools is None:
            await self.capabilities()
        if name not in self.tools:
            raise PocketError('Pocket MCP tool unavailable; check account capabilities and plan')
        try:
            response = await self.session.call_tool(name, arguments=arguments)
        except Exception:
            raise PocketError('Pocket MCP call failed; check connectivity, scopes and plan') from None
        if response.isError:
            raise PocketError('Pocket MCP returned a tool error; check scopes and plan')
        value = getattr(response,'structuredContent',None)
        if value is None:
            text = [c.text for c in response.content if getattr(c,'type',None) == 'text']
            if len(text) != 1:
                raise ResponseError('Unsupported MCP content shape')
            try:
                value = json.loads(text[0])
            except (ValueError,TypeError):
                raise ResponseError('MCP returned non-JSON data') from None
        if (not isinstance(value,dict) or value.get('success') is False or value.get('error')
                or ('data' in value and value['data'] is None)):
            raise ResponseError('MCP returned an invalid or failed result')
        return value

    async def search_action_items(self, **filters):
        allowed = {'query','status','priority','category','dueBefore','dueAfter','recordingDateFrom','recordingDateTo'}
        if set(filters) - allowed:
            raise ConfigurationError('Unsupported action-item filter')
        # Return authoritative structured payload intact: no guessing its envelope or losing IDs.
        return await self.call('search_pocket_actionitems', **filters)

    async def recent_recordings(self, *, max_pages=100, **filters):
        from pocket_api import integer
        integer(max_pages,'max_pages',1,10000)
        if set(filters) - {'recordingDateAfter','recordingDateBefore','tags','folderIds'}:
            raise ConfigurationError('Unsupported recency filter')
        pages, cursor, seen = [], None, set()
        for _ in range(max_pages):
            args = dict(filters)
            if cursor:
                args['cursor'] = cursor
            page = await self.call('search_pocket_conversations', **args)
            data = page.get('data')
            meta = data.get('meta') if isinstance(data,dict) else None
            if not isinstance(meta,dict) or type(meta.get('hasMore')) is not bool:
                raise ResponseError('MCP recency pagination is missing or invalid')
            pages.append(page)
            if not meta['hasMore']:
                return pages
            cursor = meta.get('nextCursor')
            if not isinstance(cursor,str) or not cursor or cursor in seen:
                raise ResponseError('MCP recency pagination made no progress')
            seen.add(cursor)
        raise ResponseError('MCP recency page budget exhausted; retrieval incomplete')


@asynccontextmanager
async def connect(api_key=None):
    """Connect to the fixed official endpoint with a bounded SDK transport."""
    try:
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client
    except ImportError:
        raise ConfigurationError('Install the mcp optional dependency: pip install .[mcp]') from None
    from datetime import timedelta
    token = key_value(api_key)
    try:
        async with streamablehttp_client(URL, headers={'Authorization':f'Bearer {token}'},
                                        timeout=timedelta(seconds=30),
                                        sse_read_timeout=timedelta(seconds=60)) as (read,write,_):
            async with ClientSession(read,write,read_timeout_seconds=timedelta(seconds=60)) as session:
                await session.initialize()
                yield PocketMCP(session)
    except PocketError:
        raise
    except Exception:
        raise PocketError('Pocket MCP session failed') from None
