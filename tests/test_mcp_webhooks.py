import asyncio
import hashlib
import hmac
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

from pocket_api import ConfigurationError, PocketError, ResponseError
from pocket_mcp import PocketMCP
from pocket_webhooks import verify_event, ReconciliationInbox


class MCPTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.session=NS(list_tools=AsyncMock(return_value=NS(tools=[NS(name=n) for n in ['search_pocket_actionitems','search_pocket_conversations','update_pocket_actionitem']],nextCursor=None)),call_tool=AsyncMock())
        self.client=PocketMCP(self.session)

    async def test_write_tool_is_rejected(self):
        self.assertNotIn('update_pocket_actionitem',await self.client.capabilities())
        with self.assertRaises(ConfigurationError):await self.client.call('update_pocket_actionitem',actionItemId='x')
        self.session.call_tool.assert_not_called()

    async def test_structured_actions_preserved(self):
        payload={'success':True,'data':[{'actionItemId':'a','label':'same','status':'TODO'},{'actionItemId':'b','label':'same','status':'COMPLETED'}]}
        self.session.call_tool.return_value=NS(isError=False,structuredContent=payload)
        self.assertEqual(await self.client.search_action_items(status='TODO'),payload)
        self.session.call_tool.assert_awaited_once_with('search_pocket_actionitems',arguments={'status':'TODO'})

    async def test_text_fallback(self):
        self.session.call_tool.return_value=NS(isError=False,structuredContent=None,content=[NS(type='text',text='{"data": []}')])
        self.assertEqual(await self.client.search_action_items(),{'data':[]})

    async def test_remote_errors_are_redacted(self):
        self.session.call_tool.return_value=NS(isError=True,content=[NS(type='text',text='private data')])
        with self.assertRaises(PocketError) as c:await self.client.search_action_items()
        self.assertNotIn('private',str(c.exception))
        with self.assertRaises(PocketError):await self.client.call('get_pocket_conversation')

    async def test_recency_pagination(self):
        self.session.call_tool.side_effect=[NS(isError=False,structuredContent={'data':{'meta':{'hasMore':True,'nextCursor':'c1'},'records':[{'id':'r1'}]}}),NS(isError=False,structuredContent={'data':{'meta':{'hasMore':False},'records':[{'id':'r2'}]}})]
        pages=await self.client.recent_recordings(recordingDateAfter='2026-11-01T00:00:00Z')
        self.assertEqual(len(pages),2)
        self.assertEqual(self.session.call_tool.call_args.kwargs['arguments']['cursor'],'c1')

    async def test_recency_loop_rejected(self):
        self.session.call_tool.return_value=NS(isError=False,structuredContent={'data':{'meta':{'hasMore':True,'nextCursor':'c1'}}})
        with self.assertRaises(ResponseError):await self.client.recent_recordings()

    async def test_malformed_result(self):
        self.session.call_tool.return_value=NS(isError=False,structuredContent=None,content=[NS(type='text',text='not json')])
        with self.assertRaises(ResponseError):await self.client.search_action_items()


NOW=1800000000.0
STAMP=str(int(NOW*1000))
SECRET='synthetic-webhook-secret'
def body(version=1,event='summary.completed',user='u1'):
    return json.dumps({'event':event,'timestamp':version,'user':{'id':user},'recording':{'id':'r1'},'synthetic_private_content':f'version {version}'}).encode()
def sign(raw, stamp=STAMP):
    return hmac.new(SECRET.encode(),stamp.encode()+b'.'+raw,hashlib.sha256).hexdigest()


class WebhookTests(unittest.TestCase):
    def test_exact_bytes_and_valid_signature(self):
        raw=body()
        self.assertEqual(verify_event(raw,sign(raw),STAMP,SECRET,now=NOW)['event'],'summary.completed')
        with self.assertRaises(ResponseError):verify_event(raw+b' ',sign(raw),STAMP,SECRET,now=NOW)

    def test_invalid_signatures_timestamps_and_replay(self):
        raw=body()
        for signature in ('','a','g'*64):
            with self.assertRaises(ResponseError):verify_event(raw,signature,STAMP,SECRET,now=NOW)
        for now in (NOW+301,NOW-301):
            with self.assertRaises(ResponseError):verify_event(raw,sign(raw),STAMP,SECRET,now=now)
        with self.assertRaises(ResponseError):verify_event(raw,sign(raw),'nan',SECRET,now=NOW)

    def test_duplicate_and_out_of_order_events(self):
        inbox=ReconciliationInbox(':memory:',user_id='u1')
        try:
            raw=body(2)
            self.assertTrue(inbox.receive(raw,sign(raw),STAMP,SECRET,now=NOW))
            self.assertFalse(inbox.receive(raw,sign(raw),STAMP,SECRET,now=NOW))
            old=inbox.pending()[0]
            raw=body(1)
            self.assertTrue(inbox.receive(raw,sign(raw),STAMP,SECRET,now=NOW))
            self.assertFalse(inbox.acknowledge(*old))
            self.assertTrue(inbox.acknowledge(*inbox.pending()[0]))
            self.assertEqual(inbox.pending(),[])
        finally:inbox.close()

    def test_no_aba_generation_reuse(self):
        inbox=ReconciliationInbox(':memory:',user_id='u1')
        try:
            raw=body(1);inbox.receive(raw,sign(raw),STAMP,SECRET,now=NOW)
            old=inbox.pending()[0];inbox.acknowledge(*old)
            raw=body(2);inbox.receive(raw,sign(raw),STAMP,SECRET,now=NOW)
            self.assertFalse(inbox.acknowledge(*old))
            self.assertTrue(inbox.pending())
        finally:inbox.close()

    def test_account_boundary(self):
        inbox=ReconciliationInbox(':memory:',user_id='u1')
        try:
            raw=body(user='other')
            with self.assertRaises(ResponseError):inbox.receive(raw,sign(raw),STAMP,SECRET,now=NOW)
            self.assertEqual(inbox.pending(),[])
        finally:inbox.close()

    def test_reopen_and_real_database_concurrent_generation(self):
        with tempfile.TemporaryDirectory() as td:
            path=str(Path(td)/'inbox.sqlite')
            a=ReconciliationInbox(path,user_id='u1');b=ReconciliationInbox(path,user_id='u1')
            try:
                raw=body(1);a.receive(raw,sign(raw),STAMP,SECRET,now=NOW)
                old=a.pending()[0]
                raw=body(2,'recording.deleted');b.receive(raw,sign(raw),STAMP,SECRET,now=NOW)
                self.assertFalse(a.acknowledge(*old))
                rows=b.db.execute('SELECT name FROM sqlite_master WHERE type="table"').fetchall()
                dump='\n'.join(b.db.iterdump())
                self.assertNotIn('synthetic_private_content',dump)
                self.assertNotIn(SECRET,dump)
            finally:a.close();b.close()
            reopened=ReconciliationInbox(path,user_id='u1')
            self.assertTrue(reopened.pending());reopened.close()
            with self.assertRaises(ConfigurationError):ReconciliationInbox(path,user_id='other')

    def test_simultaneous_duplicate_delivery_on_two_connections(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        with tempfile.TemporaryDirectory() as td:
            path=str(Path(td)/'inbox.sqlite')
            seed=ReconciliationInbox(path,user_id='u1');seed.close()
            barrier=Barrier(2)
            raw=body(5)
            def deliver():
                inbox=ReconciliationInbox(path,user_id='u1')
                try:
                    barrier.wait(timeout=3)
                    return inbox.receive(raw,sign(raw),STAMP,SECRET,now=NOW)
                finally:inbox.close()
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures=[executor.submit(deliver) for _ in range(2)]
                self.assertEqual(sorted(f.result(timeout=5) for f in futures),[False,True])
            check=ReconciliationInbox(path,user_id='u1')
            self.assertEqual(check.pending(),[('r1',1)])
            check.close()
