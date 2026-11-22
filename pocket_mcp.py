"""Official Pocket MCP adapter, read-only by default.

Writes require explicit opt-in and per-call confirmation. No automatic scope fallback.
The default session uses a supplied API key; OAuth may be handled by a host MCP client.
"""
import json
from contextlib import asynccontextmanager

from pocket_api import PocketError, ConfigurationError, ResponseError, key_value

URL = 'https://public.heypocketai.com/mcp'
from pocket_catalog import READ_TOOLS, WRITE_TOOLS



class PocketMCP:
    def __init__(self, session, *, allow_writes=False):
        if type(allow_writes) is not bool:
            raise ConfigurationError("allow_writes must be boolean")
        self.allow_writes = allow_writes
        self.session = session
        self.tools = None
        self.tool_schemas = {}

    async def capabilities(self):
        names, cursor, seen, schemas = set(), None, set(), {}
        for _ in range(20):
            try:
                page = await self.session.list_tools(cursor=cursor)
            except Exception:
                raise PocketError('Pocket MCP capability discovery failed') from None
            names.update(t.name for t in page.tools)
            for tool in page.tools:
                if tool.name in (READ_TOOLS | WRITE_TOOLS if self.allow_writes else READ_TOOLS):
                    schemas[tool.name] = getattr(tool,'inputSchema',{'type':'object'})
            cursor = page.nextCursor
            if not cursor:
                self.tools = names & (READ_TOOLS | WRITE_TOOLS if self.allow_writes else READ_TOOLS)
                self.tool_schemas = schemas
                return sorted(self.tools)
            if cursor in seen:
                raise ResponseError('MCP tool pagination made no progress')
            seen.add(cursor)
        raise ResponseError('MCP tool listing budget exhausted')

    async def call(self, name, *, confirm=False, **arguments):
        if name not in READ_TOOLS | WRITE_TOOLS:
            raise ConfigurationError('Unsupported Pocket MCP tool')
        if name in WRITE_TOOLS and not (self.allow_writes and confirm is True):
            raise ConfigurationError('Write requires allow_writes=True and confirm=True')
        if name in ('search_pocket_actionitems','update_pocket_actionitem'):
            validate_action_arguments(name, arguments)
        if self.tools is None:
            await self.capabilities()
        if name not in self.tools:
            raise PocketError('Pocket MCP tool unavailable; check account capabilities and plan')
        schema = self.tool_schemas.get(name)
        if schema:
            try:
                from jsonschema import Draft202012Validator
                from referencing import Registry
                # No external schema resolution/network requests from remote tool metadata.
                Draft202012Validator.check_schema(schema)
                if not Draft202012Validator(schema,registry=Registry()).is_valid(arguments):
                    raise ConfigurationError('Arguments do not match the discovered MCP tool schema')
            except ImportError:
                pass  # Official SDK installs jsonschema; tool-less mocks need not.
            except ConfigurationError:
                raise
            except Exception:
                raise ResponseError('Invalid or externally referenced MCP input schema') from None
        try:
            response = await self.session.call_tool(name, arguments=arguments)
        except Exception:
            raise PocketError('Pocket MCP write outcome unknown; reconcile before retrying' if name in WRITE_TOOLS else
                              'Pocket MCP call failed; check connectivity, scopes and plan') from None
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

    async def update_action_item(self, action_item_id, *, confirm=False, **changes):
        """Update only supplied fields of a task previously retrieved by ID."""
        return await self.call('update_pocket_actionitem', actionItemId=action_item_id,
                               confirm=confirm, **changes)

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
async def connect(api_key=None, *, allow_writes=False):
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
                yield PocketMCP(session, allow_writes=allow_writes)
    except PocketError:
        raise
    except Exception:
        raise PocketError('Pocket MCP session failed') from None


def validate_action_arguments(name, arguments):
    from datetime import date
    from pocket_api import timestamp
    search = name == 'search_pocket_actionitems'
    allowed = ({'query','status','priority','category','dueBefore','dueAfter','recordingDateFrom','recordingDateTo'}
               if search else {'actionItemId','status','priority','dueDate','label','context','assignee'})
    if set(arguments) - allowed or any(not isinstance(v,str) for v in arguments.values()):
        raise ConfigurationError('Unsupported action-item fields or types')
    for field, values in [('status',('TODO','IN_PROGRESS','COMPLETED','CANCELLED')),
                          ('priority',('CRITICAL','HIGH','MEDIUM','LOW')),
                          ('category',('TASK','MEETING','REMINDER'))]:
        if field in arguments and arguments[field] not in values:
            raise ConfigurationError('Invalid action-item ' + field)
    if not search and (not arguments.get('actionItemId') or len(arguments) < 2):
        raise ConfigurationError('Task ID and at least one change required')
    for field in ('dueBefore','dueAfter','recordingDateFrom','recordingDateTo','dueDate'):
        if field not in arguments or (field == 'dueDate' and arguments[field] == ''):
            continue
        value = arguments[field]
        try:
            if len(value) == 10: date.fromisoformat(value)
            else: timestamp(value)
        except (ValueError, ResponseError):
            raise ConfigurationError('Invalid action-item date') from None
