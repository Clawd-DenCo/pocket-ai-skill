"""Synthetic integration tests: loopback HTTP and in-memory official MCP SDK."""
import importlib.util
import inspect
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from pocket_api import PocketAI, APIError
from pocket_mcp import PocketMCP


class HTTPTests(unittest.TestCase):
    def test_real_serialization_headers_and_redirect_refusal(self):
        captured=[]
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                captured.append((self.path,self.headers.get('Authorization'),json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
                data=json.dumps({'success':True,'data':{'relevantMemories':[]}}).encode()
                self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(data)
            def do_GET(self):
                self.send_response(302);self.send_header('Location','http://127.0.0.1:1/must-not-follow');self.end_headers()
            def log_message(self,*_):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with PocketAI('synthetic-only',max_retries=0) as client:
                client.BASE_URL=f'http://127.0.0.1:{server.server_port}/api/v1'
                client.session.trust_env=False
                query='quote " newline\n backslash\\ 雪'
                client.search(query,limit=20)
                self.assertEqual(captured,[('/api/v1/public/search','Bearer synthetic-only',{'query':query,'limit':20})])
                with self.assertRaises(APIError) as ctx:client.list_tags()
                self.assertEqual(ctx.exception.status,302)
        finally:
            server.shutdown();thread.join();server.server_close()


@unittest.skipUnless(importlib.util.find_spec('mcp'),'optional MCP SDK not installed')
class SDKTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_sdk_initialize_discovery_and_structured_result(self):
        from mcp.server.fastmcp import FastMCP
        from mcp.shared.memory import create_connected_server_and_client_session
        server=FastMCP('synthetic-pocket')
        @server.tool()
        def search_pocket_actionitems(status: str) -> dict:
            return {'success':True,'data':[{'actionItemId':'synthetic-id','status':status}]}
        @server.tool()
        def update_pocket_actionitem(actionItemId: str) -> dict:
            raise AssertionError('Write tool must never be called')
        async with create_connected_server_and_client_session(server) as session:
            client=PocketMCP(session)
            self.assertEqual(await client.capabilities(),['search_pocket_actionitems'])
            result=await client.search_action_items(status='TODO')
            self.assertEqual(result['data'][0]['actionItemId'],'synthetic-id')

    async def test_supported_transport_arguments(self):
        from datetime import timedelta
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client
        inspect.signature(streamablehttp_client).bind('https://public.heypocketai.com/mcp',headers={'Authorization':'Bearer synthetic'},timeout=timedelta(seconds=30),sse_read_timeout=timedelta(seconds=60))
        inspect.signature(ClientSession).bind(None,None,read_timeout_seconds=timedelta(seconds=60))
