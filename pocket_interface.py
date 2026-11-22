"""JSON CLI for every cataloged REST operation and official MCP tool."""
import argparse
import asyncio
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys

from pocket_api import PocketAI, PocketError, ConfigurationError
from pocket_catalog import OPERATIONS
from pocket_mcp import connect


def load(value):
    if value is None:
        return None
    text = Path(value[1:]).read_text() if value.startswith('@') else value
    result = json.loads(text)
    if not isinstance(result,dict):
        raise ConfigurationError('JSON arguments must be objects')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description='Pocket REST and official MCP JSON interface')
    sub = parser.add_subparsers(dest='command',required=True)
    sub.add_parser('catalog')
    rest = sub.add_parser('rest')
    rest.add_argument('operation',choices=sorted(OPERATIONS))
    rest.add_argument('--path',help='JSON object or @file of resource IDs')
    rest.add_argument('--query',help='JSON object or @file of query parameters')
    rest.add_argument('--body',help='JSON object or @file; use files for private/secret values')
    mcp = sub.add_parser('mcp')
    mcp.add_argument('tool',help='Official tool name, or capabilities')
    mcp.add_argument('--arguments',help='JSON object or @file')
    for command in (rest,mcp):
        command.add_argument('--allow-writes',action='store_true')
        command.add_argument('--confirm',action='store_true',help='Confirm this specific authorized mutation')
        command.add_argument('--output',help='Create a new private result file (mode 0600) instead of stdout')
    args = parser.parse_args(argv)
    output = None
    try:
        # Reserve the private output before a mutation so an existing/unwritable path
        # cannot discard a one-time credential after the service has created it.
        if getattr(args,'output',None):
            fd = os.open(args.output,os.O_WRONLY | os.O_CREAT | os.O_EXCL,0o600)
            output = os.fdopen(fd,'w')
        if args.command == 'catalog':
            result = {name:asdict(spec) for name,spec in OPERATIONS.items()}
        elif args.command == 'rest':
            if args.operation == 'create_org_api_key' and not args.output:
                raise ConfigurationError('API key creation requires --output to a new private file')
            with PocketAI(allow_writes=args.allow_writes) as client:
                result = client.operation(args.operation,path=load(args.path),query=load(args.query),
                    body=load(args.body),confirm=args.confirm)
        else:
            async def request():
                async with connect(allow_writes=args.allow_writes) as client:
                    if args.tool == 'capabilities':
                        await client.capabilities()
                        return {'tools':client.tool_schemas}
                    return await client.call(args.tool,confirm=args.confirm,**(load(args.arguments) or {}))
            result = asyncio.run(request())
        text = json.dumps(result,ensure_ascii=False,indent=2)+'\n'
        if output is not None:
            output.write(text)
            output.flush()
        else:
            print(text,end='')
        return 0
    except PocketError as exc:
        print(str(exc),file=sys.stderr)
    except (ValueError,OSError,TypeError):
        print('Pocket input/output failed; do not repeat a write without reconciliation',file=sys.stderr)
    finally:
        if output is not None:
            output.close()
    return 1

if __name__ == '__main__':
    raise SystemExit(main())
