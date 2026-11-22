import contextlib
import importlib.util
import re
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, AsyncMock, patch
import requests

from pocket_api import PocketAI, ConfigurationError, PocketError, APIError, ResponseError
from pocket_catalog import OPERATIONS, READ_TOOLS, WRITE_TOOLS
from pocket_mcp import PocketMCP
from pocket_interface import main


def response(payload, status=200):
    return NS(status_code=status, headers={}, json=lambda:payload, close=lambda:None)

class RESTCoverageTests(unittest.TestCase):
    def setUp(self):
        self.session = Mock(headers={})
        self.session.request.return_value = response({'data':[], 'success':True})
        self.client = PocketAI('synthetic',session=self.session,allow_writes=True)

    def test_all_published_routes_and_methods(self):
        # Independent expectations transcribed from official endpoint documentation.
        expected = {
            'search':('POST','/public/search'), 'list_recordings':('GET','/public/recordings'),
            'get_recording':('GET','/public/recordings/r'), 'get_audio_url':('GET','/public/recordings/r/audio-url'),
            'create_upload_url':('POST','/public/recordings/upload-url'),
            'list_folders':('GET','/public/folders'), 'list_tags':('GET','/public/tags'),
            'list_users':('GET','/public/users'), 'get_user_settings':('GET','/public/users/u/settings'),
            'update_user_settings':('PATCH','/public/users/u/settings'),
            'list_org_api_keys':('GET','/organization/o/api-keys'),
            'get_org_api_key':('GET','/organization/o/api-keys/k'),
            'create_org_api_key':('POST','/organization/o/api-keys'),
            'delete_org_api_key':('DELETE','/organization/o/api-keys/k'),
            'list_org_templates':('GET','/organization/o/templates'),
            'get_org_template':('GET','/organization/o/templates/t'),
            'create_org_template':('POST','/organization/o/templates'),
            'update_org_template':('PATCH','/organization/o/templates/t'),
            'delete_org_template':('DELETE','/organization/o/templates/t'),
            'get_org_analytics':('GET','/organization/o/analytics'),
            'list_org_recordings':('GET','/organization/o/recordings'),
            'get_org_recording':('GET','/organization/o/recordings/r'),
            'update_org_recording':('PUT','/organization/o/recordings/r'),
            'delete_org_recording':('DELETE','/organization/o/recordings/r'),
            'update_org_member':('PATCH','/organization/o/members/u'),
            'list_org_users':('GET','/organization/o/users'),
            'get_org_user_settings':('GET','/organization/o/users/u/settings'),
            'update_org_user_settings':('PATCH','/organization/o/users/u/settings'),
            'send_org_invite':('POST','/organization/o/invites'),
            'accept_org_invite':('POST','/organization/invites/accept'),
            'revoke_org_invite':('DELETE','/organization/o/invites/i'),
            'resend_org_invite':('POST','/organization/o/invites/i/resend'),
            'list_org_webhooks':('GET','/organization/o/webhooks'),
            'get_org_webhook':('GET','/organization/o/webhooks/w'),
            'create_org_webhook':('POST','/organization/o/webhooks'),
            'update_org_webhook':('PUT','/organization/o/webhooks/w'),
            'delete_org_webhook':('DELETE','/organization/o/webhooks/w'),
            'test_org_webhook':('POST','/organization/o/webhooks/w/test'),
        }
        self.assertEqual(set(OPERATIONS),set(expected))
        ids = dict(org_id='o',recording_id='r',user_id='u',key_id='k',template_id='t',invite_id='i',webhook_id='w')
        bodies = {
            'search':{'query':'q'}, 'create_org_api_key':{'name':'label','scopes':['recordings:read']},
            'create_org_template':{'name':'template','sections':[]},
            'update_org_template':{'name':'new'}, 'update_org_recording':{'title':'new'},
            'update_org_member':{'role':'viewer'}, 'send_org_invite':{'email':'synthetic@example.invalid'},
            'accept_org_invite':{'token':'synthetic'},
            'create_org_webhook':{'explicit_service_payload':True},
            'update_org_webhook':{'explicit_service_payload':True}}
        for name,(method,route) in expected.items():
            with self.subTest(name=name):
                spec = OPERATIONS[name]
                path = {k:v for k,v in ids.items() if '{'+k+'}' in spec.path}
                body = bodies.get(name)
                if name in ('update_user_settings','update_org_user_settings'):body={'settings':{'auto_transcription':False}}
                self.client.operation(name,path=path,body=body,confirm=True)
                self.assertEqual(self.session.request.call_args.args,(method,self.client.BASE_URL+route))
                self.assertFalse(self.session.request.call_args.kwargs['allow_redirects'])

    def test_every_write_requires_both_controls(self):
        for name,spec in OPERATIONS.items():
            if spec.read_only:continue
            # Gate cannot be bypassed through transport flags in the payload.
            for allowed,confirm in [(False,True),(True,False),(False,False),(True,1)]:
                with self.subTest(name=name,allowed=allowed,confirm=confirm):
                    client=PocketAI('synthetic',session=self.session,allow_writes=allowed)
                    self.session.request.reset_mock()
                    path={key:'synthetic-id' for key in re.findall(r'{(\w+)}',spec.path)}
                    body=None
                    if spec.body or not spec.body_documented:
                        body={'settings':{}} if 'settings' in spec.body else {spec.body[0]:'synthetic'} if spec.body else {'explicit_payload':True}
                    if name=='create_org_api_key':body={'name':'x','scopes':['recordings:read']}
                    if name=='create_org_template':body={'name':'x','sections':[]}
                    if name=='update_org_member':body={'role':'viewer'}
                    with self.assertRaisesRegex(ConfigurationError,'Write requires'):
                        client.operation(name,path=path,body=body,confirm=confirm)
                    self.session.request.assert_not_called()
        c=PocketAI('synthetic',session=self.session)
        with self.assertRaises(ConfigurationError):c.operation('delete_org_recording',path={'org_id':'o','recording_id':'r'},confirm=True)

    def test_writes_are_not_retried_and_unknown_outcome_is_explicit(self):
        for error in (requests.Timeout('secret'),requests.ConnectionError('secret')):
            self.session.request.reset_mock();self.session.request.side_effect=error
            with self.assertRaisesRegex(PocketError,'outcome unknown'):
                self.client.operation('create_upload_url',confirm=True)
            self.assertEqual(self.session.request.call_count,1)
        self.session.request.side_effect=None
        for code in (401,403,429,500,503):
            self.session.request.reset_mock();self.session.request.return_value=response({'error':'secret'},code)
            with self.assertRaises(APIError):self.client.operation('create_upload_url',confirm=True)
            self.assertEqual(self.session.request.call_count,1)

    def test_org_response_shapes_and_empty_mutation(self):
        for payload in ({'keys':[]},{'recordings':[],'pagination':{'total':0}},{'success':True},{'applied':{'settings':True}}):
            self.session.request.return_value=response(payload)
            self.assertEqual(self.client.operation('list_org_api_keys',path={'org_id':'o'}),payload)
        self.session.request.return_value=response(None,204)
        self.assertEqual(self.client.operation('delete_org_api_key',path={'org_id':'o','key_id':'k'},confirm=True),{'success':True})
        self.session.request.return_value=response({'error':'sensitive'})
        with self.assertRaises(ResponseError):self.client.operation('list_org_api_keys',path={'org_id':'o'})

    def test_route_escape_and_unrecognized_fields_rejected(self):
        for value in ('../x','%2e%2e','a/b','a?x=1','a#b','a\\b','a\n','..'):
            with self.assertRaises(ConfigurationError):self.client.operation('get_recording',path={'recording_id':value})
        with self.assertRaises(ConfigurationError):self.client.operation('list_folders',query={'url':'https://evil.invalid'})
        with self.assertRaises(ConfigurationError):self.client.operation('list_folders',body={'token':'x'})
        with self.assertRaises(ConfigurationError):self.client.operation('create_org_api_key',path={'org_id':'o'},body={'name':'x'},confirm=True)
        self.session.request.assert_not_called()

    def test_filters_and_boolean_encoding(self):
        self.client.operation('get_user_settings',path={'user_id':'u'},query={'include_notifications':False,'preferences_limit':200})
        self.assertEqual(self.session.request.call_args.kwargs['params']['include_notifications'],'false')
        self.client.operation('delete_org_recording',path={'org_id':'o','recording_id':'r'},query={'permanent':True},confirm=True)
        self.assertEqual(self.session.request.call_args.kwargs['params'],{'permanent':'true'})
        for q in ({'permanent':'true'},{'permanent':1}):
            with self.assertRaises(ConfigurationError):self.client.operation('delete_org_recording',path={'org_id':'o','recording_id':'r'},query=q,confirm=True)

class MCPExpansionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.session=NS(list_tools=AsyncMock(return_value=NS(tools=[NS(name=n,inputSchema={'type':'object'}) for n in READ_TOOLS|WRITE_TOOLS],nextCursor=None)),call_tool=AsyncMock(return_value=NS(isError=False,structuredContent={'success':True})))

    async def test_org_and_personal_coverage(self):
        c=PocketMCP(self.session)
        self.assertEqual(set(await c.capabilities()),READ_TOOLS)
        w=PocketMCP(self.session,allow_writes=True)
        self.assertEqual(set(await w.capabilities()),READ_TOOLS|WRITE_TOOLS)
        for n in READ_TOOLS:await c.call(n)

    async def test_write_confirmation_not_forwarded_no_retry(self):
        c=PocketMCP(self.session,allow_writes=True)
        with self.assertRaises(ConfigurationError):await c.update_action_item('a',status='COMPLETED')
        await c.update_action_item('a',status='COMPLETED',dueDate='',confirm=True)
        self.session.call_tool.assert_awaited_once_with('update_pocket_actionitem',arguments={'actionItemId':'a','status':'COMPLETED','dueDate':''})
        self.session.call_tool.reset_mock();self.session.call_tool.side_effect=RuntimeError('secret')
        with self.assertRaisesRegex(PocketError,'outcome unknown'):await c.update_action_item('a',status='TODO',confirm=True)
        self.session.call_tool.assert_awaited_once()

    async def test_live_schema_and_structured_filter_validation(self):
        c=PocketMCP(self.session)
        self.session.list_tools.return_value.tools=[NS(name='search_pocket_actionitems',inputSchema={'type':'object','required':['query'],'properties':{'query':{'type':'string'}}})]
        with self.assertRaises(ConfigurationError):await c.search_action_items(status='TODO')
        with self.assertRaises(ConfigurationError):await c.search_action_items(query='q',status='wrong')
        with self.assertRaises(ConfigurationError):await c.search_action_items(query='q',dueBefore='tomorrow')
        self.session.call_tool.assert_not_called()

    async def test_external_schema_reference_is_not_resolved(self):
        self.session.list_tools.return_value.tools=[NS(name='list_org_tags',inputSchema={'$ref':'https://example.invalid/private'})]
        c=PocketMCP(self.session)
        with self.assertRaisesRegex(ResponseError,'externally referenced'):
            await c.call('list_org_tags')
        self.session.call_tool.assert_not_called()

class InterfaceCLITests(unittest.TestCase):
    def test_catalog_needs_no_key(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:self.assertEqual(main(['catalog']),0)
        self.assertEqual(len(json.loads(out.getvalue())),38)

    def test_private_output_reserved_before_mutation(self):
        with tempfile.TemporaryDirectory() as d,patch('pocket_interface.PocketAI') as client:
            p=Path(d)/'result';p.write_text('existing')
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(['rest','create_org_api_key','--output',str(p)]),1)
            client.assert_not_called()
            self.assertEqual(p.read_text(),'existing')

    def test_private_output_and_exact_arguments(self):
        with tempfile.TemporaryDirectory() as d,patch('pocket_interface.PocketAI') as client:
            client.return_value.__enter__.return_value.operation.return_value={'key':'synthetic'}
            p=Path(d)/'result'
            args=['rest','create_org_api_key','--path','{"org_id":"o"}','--body','{"name":"x","scopes":["recordings:read"]}', '--allow-writes','--confirm','--output',str(p)]
            with contextlib.redirect_stdout(io.StringIO()) as out:self.assertEqual(main(args),0)
            self.assertEqual(out.getvalue(),'');self.assertEqual(p.stat().st_mode & 0o777,0o600)
            call=client.return_value.__enter__.return_value.operation.call_args
            self.assertTrue(call.kwargs['confirm']);self.assertEqual(call.kwargs['path'],{'org_id':'o'})

@unittest.skipUnless(importlib.util.find_spec('mcp'),'optional MCP SDK not installed')
class LocalServerTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_sdk_server_discovery_and_structured_search(self):
        from contextlib import asynccontextmanager
        from mcp.shared.memory import create_connected_server_and_client_session
        from pocket_server import create_server
        remote=NS(search_action_items=AsyncMock(return_value={'success':True,'data':[{'actionItemId':'a','status':'TODO','label':'same'},{'actionItemId':'b','status':'TODO','label':'same'}]}))
        @asynccontextmanager
        async def factory():yield remote
        server=create_server(remote_factory=factory)
        async with create_connected_server_and_client_session(server) as session:
            tools=(await session.list_tools()).tools
            names={t.name for t in tools}
            self.assertNotIn('update_pocket_actionitem',names)
            self.assertNotIn('rest_delete_org_recording',names)
            self.assertIn('rest_get_org_user_settings',names)
            schema=next(t.inputSchema for t in tools if t.name=='search_pocket_actionitems')
            self.assertIn('dueBefore',schema['properties'])
            r=await session.call_tool('search_pocket_actionitems',{'status':'TODO','priority':'HIGH'})
            self.assertFalse(r.isError)
            remote.search_action_items.assert_awaited_once_with(status='TODO',priority='HIGH')
            self.assertEqual([x['actionItemId'] for x in r.structuredContent['data']],['a','b'])

    async def test_real_sdk_rest_and_write_gate(self):
        from mcp.shared.memory import create_connected_server_and_client_session
        from pocket_server import create_server
        transport=Mock(headers={});transport.request.return_value=response({'success':True})
        factory=lambda:PocketAI('synthetic',allow_writes=True,session=transport)
        async with create_connected_server_and_client_session(create_server(allow_writes=True,client_factory=factory)) as session:
            names={t.name for t in (await session.list_tools()).tools}
            self.assertEqual(len([n for n in names if n.startswith('rest_')]),38)
            args={'path':{'org_id':'o','recording_id':'r'}}
            r=await session.call_tool('rest_delete_org_recording',args)
            self.assertTrue(r.isError);transport.request.assert_not_called()
            r=await session.call_tool('rest_delete_org_recording',{**args,'confirm':True})
            self.assertFalse(r.isError);transport.request.assert_called_once()

@unittest.skipUnless(importlib.util.find_spec('mcp'),'optional MCP SDK not installed')
class StdioServerTests(unittest.IsolatedAsyncioTestCase):
    async def test_actual_subprocess_handshake_without_account(self):
        import sys
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        from datetime import timedelta
        # Discovery must not need credentials or contact Pocket.
        params=StdioServerParameters(command=sys.executable,args=['-m','pocket_server'],env={'POCKET_API_KEY':''})
        async with stdio_client(params) as (read,write):
            async with ClientSession(read,write,read_timeout_seconds=timedelta(seconds=10)) as session:
                await session.initialize()
                tools=(await session.list_tools()).tools
                names={t.name for t in tools}
                self.assertIn('search_pocket_actionitems',names)
                self.assertIn('rest_get_org_analytics',names)
                self.assertNotIn('update_pocket_actionitem',names)
                self.assertTrue(next(t for t in tools if t.name=='search_pocket_actionitems').outputSchema)


class MutationHTTPTests(unittest.TestCase):
    def test_actual_write_is_single_request_and_preserves_json(self):
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        captured=[]
        class Handler(BaseHTTPRequestHandler):
            def do_PUT(self):
                captured.append((self.path,json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
                self.send_response(503);self.end_headers()
            def log_message(self,*_):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        body={'title':'Quoted " title 雪', 'tags':['t1','t2']}
        try:
            with PocketAI('synthetic',allow_writes=True) as client:
                client.BASE_URL=f'http://127.0.0.1:{server.server_port}/api/v1'
                client.session.trust_env=False
                with self.assertRaises(APIError):
                    client.operation('update_org_recording',path={'org_id':'o','recording_id':'r'},body=body,confirm=True)
            self.assertEqual(captured,[('/api/v1/organization/o/recordings/r',body)])
        finally:
            server.shutdown();thread.join();server.server_close()
