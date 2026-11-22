"""Offline baseline defect probes; success means the documented defect reproduced.
No real credentials, HTTP requests, or private recordings are used.
Historical only: check out review commit 21dbe1c in a separate worktree to run
this harness against its unchanged baseline. Do not run against corrected code.
Current acceptance suite: python3 -m unittest discover -s tests -v
"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('pocket_api', ROOT / 'pocket_api.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
client = module.PocketAI(api_key='synthetic-review-only')
client.session.close()
client.session = Mock()
observations = []
def check(name, condition):
    assert condition, name
    observations.append(name)

response = Mock()
response.json.return_value = {'data': {'relevantMemories': []}}
client.session.post.return_value = response
client.search('test')
check('Python search omits timeout', 'timeout' not in client.session.post.call_args.kwargs)
client.get_memories('test', limit=20)
check('Memory limit is not sent to server', client.session.post.call_args.kwargs['json'] == {'query':'test'})
client.get_meeting_summary('2026-11-21')
check('Meeting date only appears in prose query', client.session.post.call_args.kwargs['json'] == {'query':'meeting summary 2026-11-21'})
client.search = Mock(return_value={'data': {'relevantMemories': [
    {'content':'Action item: Discuss literal Action item: marker'},
    {'content':'action item: lowercase task'},
]}})
check('Action parser truncates repeated marker and misses lowercase', client.get_action_items() == ['Discuss literal'])
client.search.return_value = {'data': {'relevantMemories': [{'content':'a'}, {'content':'b'}, {'content':'c'}]}}
check('Negative memory limit returns items instead of rejecting', len(client.get_memories('test', -1)) == 2)
client.search.return_value = {'success': False, 'error':'synthetic error'}
check('Application error becomes empty action list', client.get_action_items() == [])
client.search.return_value = {'data': None}
try:
    client.get_action_items()
except TypeError:
    check('Null data raises TypeError', True)
else:
    raise AssertionError('Null data did not reproduce')
check('ASAP urgency example misses uppercase keyword', not any(k in 'ASAP please'.lower() for k in ['urgent','ASAP','today','immediately','deadline']))

with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    key = root / '.config/pocket-ai/api_key'
    key.parent.mkdir(parents=True)
    key.write_text('synthetic-review-only')
    # Shell functions replace every external process in search.sh. No network.
    wrapper = '''curl() {
  while [ "$#" -gt 0 ]; do
    if [ "$1" = '-d' ]; then shift; printf '%s' "$1"; return 0; fi
    shift
  done
}
jq() { /bin/cat; }
source "$1" "$2"
'''
    env = {**os.environ, 'HOME': td}
    def payload(query):
        return subprocess.run(['bash','-c',wrapper,'review',str(ROOT/'search.sh'),query],env=env,text=True,capture_output=True,check=True).stdout
    try: json.loads(payload('say "hello"'))
    except json.JSONDecodeError: check('Quoted shell query makes invalid JSON', True)
    else: raise AssertionError('JSON quoting defect did not reproduce')
    check('Shell query can inject JSON fields', json.loads(payload('x", "limit": 20, "extra": "y'))['limit'] == 20)
    failure = "curl() { return 7; }; jq() { /bin/cat; }; source \"$1\" test"
    r = subprocess.run(['bash','-c',failure,'review',str(ROOT/'search.sh')],env=env,capture_output=True)
    check('Shell pipeline masks curl failure', r.returncode == 0)
check('Documented direct shell execution lacks executable bit', not os.access(ROOT/'search.sh', os.X_OK))
print(json.dumps({'reproduced':len(observations),'observations':observations},indent=2))
