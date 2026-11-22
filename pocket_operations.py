"""Validation and routing for the source-backed REST operation catalog."""
import re
from datetime import date

from pocket_api import ConfigurationError, integer, timestamp
from pocket_catalog import OPERATIONS

SCOPES = {'recordings:read','recordings:write','templates:read','templates:write','users:read','users:write'}

def mapping(value, label):
    if value is None:
        return {}
    if not isinstance(value, dict) or any(not isinstance(k, str) for k in value):
        raise ConfigurationError(f'{label} must be a JSON object')
    return value.copy()


def prepare_operation(name, path=None, query=None, body=None):
    if name not in OPERATIONS:
        raise ConfigurationError('Unknown REST operation; use the operation catalog')
    spec = OPERATIONS[name]
    path, query = mapping(path, 'path'), mapping(query, 'query')
    expected = set(re.findall(r'{(\w+)}', spec.path))
    if set(path) != expected:
        raise ConfigurationError('Path parameters must match: ' + ', '.join(sorted(expected)))
    for value in path.values():
        if (not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,256}',value)
                or value in ('.','..')):
            raise ConfigurationError('Invalid resource identifier')
    if set(query) - set(spec.query):
        raise ConfigurationError('Unsupported query parameter')
    for key, value in query.items():
        if key in ('page','preferences_page'):
            integer(value,key,1,1000000)
        elif key in ('limit','preferences_limit'):
            integer(value,key,1,200 if key == 'preferences_limit' else 100)
        elif key == 'expires_in':
            integer(value,key,60,86400)
        elif key == 'permanent' or key.startswith('include_'):
            if type(value) is not bool:
                raise ConfigurationError(f'{key} must be boolean')
        elif not isinstance(value,str):
            raise ConfigurationError(f'{key} must be a string')
        if key in ('date','start_date','end_date','startDate','endDate'):
            try: date.fromisoformat(value)
            except (ValueError, TypeError): raise ConfigurationError('Invalid calendar date') from None
    for a,b in [('start_date','end_date'),('startDate','endDate')]:
        if a in query and b in query and query[a] > query[b]:
            raise ConfigurationError('Reversed date interval')
    if 'tagMode' in query and query['tagMode'] not in ('any','all'):
        raise ConfigurationError('tagMode must be any or all')
    payload = mapping(body,'body') if body is not None else ({} if name == 'create_upload_url' else None)
    if payload is not None and spec.body_documented and set(payload) - set(spec.body):
        raise ConfigurationError('Unsupported body field')
    if spec.required and (payload is None or set(spec.required) - set(payload)):
        raise ConfigurationError('Required body fields: ' + ', '.join(spec.required))
    if not spec.read_only and (spec.body or not spec.body_documented) and not payload and name != 'create_upload_url':
        raise ConfigurationError('Write body must not be empty')
    if payload is not None:
        for key in spec.required:
            if payload[key] is None or payload[key] == '':
                raise ConfigurationError('Required body value missing')
        if name == 'search':
            if not isinstance(payload['query'],str) or not payload['query'].strip():
                raise ConfigurationError('Search query must not be blank')
            integer(payload.get('limit',8),'limit',1,20)
            filters = mapping(payload.get('filters'),'filters')
            if set(filters) - {'dateFrom','dateTo','folderIds','recordingIds'}:
                raise ConfigurationError('Unsupported search filter')
            for key,value in filters.items():
                if key in ('dateFrom','dateTo'):timestamp(value)
                elif not isinstance(value,list) or any(not isinstance(v,str) or not v for v in value):
                    raise ConfigurationError('ID filter must contain strings')
            if 'dateFrom' in filters and 'dateTo' in filters and timestamp(filters['dateFrom']) >= timestamp(filters['dateTo']):
                raise ConfigurationError('Reversed or empty search interval')
        if name == 'create_org_api_key':
            scopes = payload['scopes']
            if not isinstance(scopes,list) or not scopes or any(not isinstance(s,str) or s not in SCOPES for s in scopes):
                raise ConfigurationError('Explicit nonempty documented scopes required')
        if name in ('update_org_member','send_org_invite'):
            if 'role' in payload and payload['role'] not in ('owner','admin','member','viewer'):
                raise ConfigurationError('Invalid member role')
            if 'status' in payload and payload['status'] not in ('active','pending','removed'):
                raise ConfigurationError('Invalid member status')
        if 'sections' in payload:
            sections = payload['sections']
            if not isinstance(sections,list) or any(not isinstance(s,dict) or
                not isinstance(s.get('title'),str) or not isinstance(s.get('prompt'),str) for s in sections):
                raise ConfigurationError('Template sections require title and prompt strings')
    # HTTP query booleans must be lowercase, not Python's True/False strings.
    query = {k:str(v).lower() if type(v) is bool else v for k,v in query.items()}
    return spec, spec.path.format(**path), query, payload
