import contextlib
import copy
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from datetime import timedelta
from unittest.mock import Mock, patch

import requests
from pocket_api import (PocketAI, PocketError, ConfigurationError, ResponseError, APIError,
                        day_interval, key_value, main)
from pocket_models import normalize_recording


def response(data=None, status=200, headers=None):
    r = Mock(status_code=status, headers=headers or {})
    r.json.return_value = data if data is not None else {'success':True,'data':{}}
    return r


def record(rid='r1', at='2026-11-22T15:00:00Z', tasks=None):
    return {'id':rid,'title':'Synthetic meeting','recording_at':at,'state':'completed',
            'transcript':{'segments':[{'text':'Synthetic words','start':0,'end':3,'speaker':'S1'}]},
            'summarizations':{'s1':{'summarizationId':'s1','processingStatus':'completed',
                'updatedAt':'2026-11-22T16:00:00Z','v2':{'summary':{'markdown':'A decision'},
                  'actionItems':{'actionItems':tasks or []}}}}}


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.s = Mock(headers={})
        self.sleep = Mock()
        self.c = PocketAI('synthetic-secret', session=self.s, sleep=self.sleep)
        self.s.request.return_value = response()

    def test_serialization_preserves_special_characters(self):
        q = 'quote " newline\n backslash\\ 雪 $(not-a-command)'
        self.c.search(q)
        call = self.s.request.call_args
        self.assertEqual(json.loads(json.dumps(call.kwargs['json']))['query'],q)
        self.assertEqual(call.kwargs['timeout'],(5,30))
        self.assertFalse(call.kwargs['allow_redirects'])

    def test_server_limit_and_filters(self):
        filters = {'dateFrom':'2026-11-22T00:00:00Z','dateTo':'2026-11-23T00:00:00Z','folderIds':['f1']}
        self.c.search('q',limit=20,filters=filters)
        self.assertEqual(self.s.request.call_args.kwargs['json'],{'query':'q','limit':20,'filters':filters})

    def test_bad_limits_and_filters(self):
        for limit in (-1,0,21,True,'2'):
            with self.subTest(limit=limit), self.assertRaises(ConfigurationError): self.c.search('q',limit=limit)
        with self.assertRaises(ConfigurationError):self.c.search('q',filters={'untrusted':True})
        with self.assertRaises(ConfigurationError):self.c.search('q',filters={'folderIds':'not-list'})
        with self.assertRaises(ConfigurationError):self.c.search('q',filters={'dateFrom':'2026-12-01T00:00:00Z','dateTo':'2026-11-01T00:00:00Z'})

    def test_auth_not_retried_and_body_not_exposed(self):
        for status in (401,403,404,400,302):
            with self.subTest(status=status):
                self.s.request.reset_mock()
                self.s.request.return_value = response({'error':'PRIVATE TRANSCRIPT synthetic-secret'},status)
                with self.assertRaises(APIError) as ctx:self.c.search('q')
                self.assertNotIn('PRIVATE',str(ctx.exception))
                self.assertEqual(self.s.request.call_count,1)

    def test_transient_retry(self):
        for status in (429,500,502,503,504):
            with self.subTest(status=status):
                self.s.request.side_effect = [response(status=status),response({'data':{'ok':True}})]
                self.assertTrue(self.c.search('q')['data']['ok'])
        self.assertEqual(self.sleep.call_count,5)

    def test_retry_after_budget(self):
        self.s.request.return_value = response(status=429,headers={'Retry-After':'4'})
        with self.assertRaises(APIError):self.c.search('q')
        self.assertEqual(self.sleep.call_args_list[0].args,(4,))
        self.assertEqual(self.s.request.call_count,3)
        self.s.request.reset_mock()
        self.s.request.return_value = response(status=429,headers={'Retry-After':'999'})
        with self.assertRaises(APIError):self.c.search('q')
        self.assertEqual(self.s.request.call_count,1)

    def test_transport_budget_and_safe_error(self):
        for err in (requests.Timeout('synthetic-secret'), requests.ConnectionError('private')):
            self.s.request.reset_mock()
            self.s.request.side_effect = err
            with self.assertRaises(PocketError) as ctx:self.c.search('q')
            self.assertEqual(self.s.request.call_count,3)
            self.assertNotIn('synthetic-secret',str(ctx.exception))

    def test_invalid_response_shapes(self):
        for data in ([], {'data':None}, {}, {'success':False,'data':{}}, {'error':'private','data':{}}):
            with self.subTest(data=data):
                self.s.request.return_value = response(data)
                with self.assertRaises(ResponseError):self.c.search('q')
        r=response();r.json.side_effect=ValueError('private')
        self.s.request.return_value=r
        with self.assertRaises(ResponseError):self.c.search('q')
        r.close.assert_called_once()

    def test_legacy_snippet_is_labeled_and_not_truncated(self):
        self.s.request.return_value=response({'data':{'relevantMemories':[
            {'content':'action item: Discuss literal Action item: marker','recordingId':'r1'},
            {'content':'Action item: Same title','recordingId':'r2'},
            {'content':'Action item: Same title','recordingId':'r3'}]}})
        items=self.c.get_action_items()
        self.assertEqual(items[0]['title'],'Discuss literal Action item: marker')
        self.assertIsNone(items[0]['status'])
        self.assertEqual(len(items),3)
        self.assertFalse(items[0]['complete'])

    def test_unsupported_search_schema_is_error(self):
        self.s.request.return_value=response({'data':{'different':[]}})
        with self.assertRaises(ResponseError):self.c.get_memories('q')

    def test_memory_provenance(self):
        self.s.request.return_value=response({'data':{'relevantMemories':[{'content':'text','recordingId':'r1','transcriptionId':'t1','metadata':{'start':1}}]}})
        self.assertEqual(self.c.get_memories('q')[0]['transcription_id'],'t1')

    def test_recording_filters(self):
        self.s.request.return_value=response({'data':[]})
        self.c.list_recordings(start_date='2026-11-01',end_date='2026-11-22',tag_ids=['t1','t2'],limit=100)
        self.assertEqual(self.s.request.call_args.kwargs['params']['tag_ids'],'t1,t2')
        with self.assertRaises(ConfigurationError):self.c.list_recordings(limit=101)
        with self.assertRaises(ConfigurationError):self.c.list_recordings(start_date='yesterday')

    def test_pages_deduplicate_by_id(self):
        self.c.list_recordings=Mock(side_effect=[{'data':[{'id':'a'}],'pagination':{'has_more':True,'page':1}},
            {'data':[{'id':'a'},{'id':'b'}],'pagination':{'has_more':False,'page':2}}])
        self.assertEqual([r['id'] for r in self.c.iter_recordings()],['a','b'])

    def test_pagination_missing_stuck_budget(self):
        for pages in ([{'data':[]}],
                      [{'data':[{'id':'a'}],'pagination':{'has_more':True}}]*2):
            self.c.list_recordings=Mock(side_effect=pages)
            with self.assertRaises(ResponseError):list(self.c.iter_recordings(max_pages=len(pages)))
        self.c.list_recordings=Mock(return_value={'data':[{'id':'a'}],'pagination':{'has_more':True}})
        with self.assertRaisesRegex(ResponseError,'budget'):list(self.c.iter_recordings(max_pages=1))

    def test_audio_correct_path_no_second_request(self):
        self.c.get_audio_url('r1')
        self.assertTrue(self.s.request.call_args.args[1].endswith('/r1/audio-url'))
        self.assertEqual(self.s.request.call_count,1)
        with self.assertRaises(ConfigurationError):self.c.get_recording('..')

    def test_context_manager(self):
        with self.c:pass
        self.s.close.assert_called_once()

    def test_keys_and_blank_rejection(self):
        with patch.dict(os.environ,{'POCKET_API_KEY':' env-key '}):
            self.assertEqual(key_value(),'env-key')
            self.assertEqual(key_value('explicit'),'explicit')
            with self.assertRaises(ConfigurationError):key_value(' ')
        with patch.dict(os.environ,{'POCKET_API_KEY':''}):
            with self.assertRaises(ConfigurationError):key_value()
        with self.assertRaises(ConfigurationError):key_value('first\nsecond')


class BriefingTests(unittest.TestCase):
    def test_dst_boundaries(self):
        for day,hours in [('2026-03-08',23),('2026-11-01',25),('2026-11-22',24)]:
            start,end=day_interval(day,'America/New_York')
            self.assertEqual((end-start).total_seconds()/3600,hours)
        with self.assertRaises(ConfigurationError):day_interval('bad','UTC')
        with self.assertRaises(ConfigurationError):day_interval('2026-11-22','Not/AZone')

    def test_daily_inventory_and_source_linked_tasks(self):
        c=PocketAI('synthetic')
        tasks=[{'id':'a','title':'same','status':'TODO'}, {'id':'b','title':'same','status':'IN_PROGRESS'},
               {'id':'c','title':'finished','status':'COMPLETED'}]
        included=record(tasks=tasks)
        # Upload date is intentionally wrong: selection uses conversation time.
        included['created_at']='2026-11-25T00:00:00Z'
        start,end=day_interval('2026-11-22','America/Edmonton')
        c.iter_recordings=Mock(return_value=iter([included,record('before',(start-timedelta(seconds=1)).isoformat()),record('end',end.isoformat())]))
        c.get_recording=Mock(return_value={'data':included})
        result=c.daily_briefing_data('2026-11-22',timezone_name='America/Edmonton')
        self.assertTrue(result['complete'])
        self.assertEqual([a['id'] for a in result['action_items']],['a','b'])
        self.assertEqual(result['action_items'][0]['recording_id'],'r1')
        self.assertEqual(len(result['recordings']),1)
        self.assertEqual(result['recordings'][0]['summary']['content']['markdown'],'A decision')
        c.close()

    def test_unknown_date_not_silent(self):
        c=PocketAI('synthetic');c.iter_recordings=Mock(return_value=iter([{'id':'bad'}]))
        result=c.daily_briefing_data('2026-11-22')
        self.assertFalse(result['complete'])
        self.assertEqual(result['issues'][0]['recording_id'],'bad')
        c.close()

    def test_processing_incomplete_and_unsupported_schema(self):
        r=record();r['summarizations']['s1']['processingStatus']='processing'
        self.assertIn('summary_processing_incomplete',normalize_recording(r)['issues'])
        r=record();r['summarizations']=None
        self.assertIn('summary_unavailable_or_unsupported',normalize_recording(r)['issues'])

    def test_unknown_and_conflicting_task_status(self):
        r=record(tasks=[{'id':'a','title':'x'}, {'id':'b','title':'y','status':'TODO','isCompleted':True}])
        result=normalize_recording(r)
        self.assertEqual([t['status'] for t in result['action_items']],[None,None])
        self.assertTrue(result['issues'])

    def test_latest_summary_and_ambiguity(self):
        r=record();old=copy.deepcopy(r['summarizations']['s1']);old['updatedAt']='2026-11-21T00:00:00Z'
        old['v2']['summary']['markdown']='old'
        r['summarizations']['old']=old
        self.assertEqual(normalize_recording(r)['summary']['content']['markdown'],'A decision')
        old['updatedAt']=r['summarizations']['s1']['updatedAt']
        self.assertIn('ambiguous_latest_summary',normalize_recording(r)['issues'])


class CLITests(unittest.TestCase):
    def test_no_profile_default_and_explicit_opt_in(self):
        for extra, present in [([],False),(['--include-profile'],True)]:
            c=Mock();c.search.return_value={'data':{'userProfile':{'private':'x'},'relevantMemories':[]}}
            c.__enter__=Mock(return_value=c);c.__exit__=Mock(return_value=False)
            out=io.StringIO()
            with patch('pocket_api.PocketAI',return_value=c),contextlib.redirect_stdout(out):
                self.assertEqual(main(['search','q']+extra),0)
            self.assertEqual('userProfile' in json.loads(out.getvalue())['data'],present)

    def test_error_is_nonzero_and_redacted(self):
        with patch('pocket_api.PocketAI',side_effect=ConfigurationError('Set key')),contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(['tags']),1)

    def test_incomplete_briefing_exit_code(self):
        c=Mock();c.daily_briefing_data.return_value={'complete':False,'issues':['missing']}
        c.__enter__=Mock(return_value=c);c.__exit__=Mock(return_value=False)
        with patch('pocket_api.PocketAI',return_value=c),contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(['briefing']),3)

    def test_shell_preserves_query_and_exit_status(self):
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as td:
            fake=Path(td)/'python3'
            fake.write_text('#!/bin/sh\nprintf "%s" "$3"\nexit 7\n');fake.chmod(0o700)
            query='quote " newline\n backslash\\ 雪 $(not-run)'
            env={**os.environ,'PATH':td+':'+os.environ['PATH']}
            p=subprocess.run([str(root/'search.sh'),query],env=env,text=True,capture_output=True)
            self.assertEqual(p.returncode,7)
            self.assertEqual(p.stdout,query)
