#!/usr/bin/env python3
"""Pocket REST client, read-only by default. Network results are untrusted data."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import date, datetime, time as daytime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

import requests


class PocketError(Exception):
    """Safe-to-display integration error; excludes remote bodies and credentials."""


class ConfigurationError(PocketError):
    pass


class ResponseError(PocketError):
    pass


class APIError(PocketError):
    def __init__(self, status):
        self.status = status
        super().__init__(f"Pocket HTTP error {status}")


def integer(value, name, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ConfigurationError(f"{name} must be an integer from {minimum} to {maximum}")
    return value


def timestamp(value):
    if not isinstance(value, str):
        raise ResponseError("Missing or invalid timestamp")
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        raise ResponseError("Invalid timestamp") from None
    if result.tzinfo is None:
        raise ResponseError("Timestamp must include a timezone")
    return result.astimezone(timezone.utc)


def day_interval(day=None, timezone_name='UTC'):
    try:
        zone = ZoneInfo(timezone_name)
        if day is not None and (not isinstance(day, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', day)):
            raise ValueError('invalid date')
        selected = date.fromisoformat(day) if day else datetime.now(zone).date()
    except (ValueError, KeyError, TypeError):
        raise ConfigurationError("Use a YYYY-MM-DD date and an IANA timezone") from None
    start = datetime.combine(selected, daytime.min, zone).astimezone(timezone.utc)
    end = datetime.combine(selected + timedelta(days=1), daytime.min, zone).astimezone(timezone.utc)
    return start, end


def key_value(explicit=None):
    if explicit is not None:
        value = explicit
    elif 'POCKET_API_KEY' in os.environ:
        value = os.environ['POCKET_API_KEY']
    else:
        try:
            value = (Path.home() / '.config/pocket-ai/api_key').read_text()
        except OSError:
            raise ConfigurationError("Set POCKET_API_KEY or provide the legacy key file") from None
    if not isinstance(value, str) or not value.strip() or any(c in value.strip() for c in '\r\n'):
        raise ConfigurationError("Pocket API key is empty or invalid")
    return value.strip()


def objects(value, label):
    if not isinstance(value, list) or any(not isinstance(v, dict) for v in value):
        raise ResponseError(f"Invalid {label} list")
    return value


def identifier(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 256 or value in ('.', '..'):
        raise ConfigurationError("Invalid recording identifier")
    return quote(value, safe='')


class PocketAI:
    BASE_URL = 'https://public.heypocketai.com/api/v1'

    def __init__(self, api_key=None, *, timeout=(5, 30), max_retries=2,
                 session=None, sleep=time.sleep, allow_writes=False):
        if (not isinstance(timeout, (tuple, list)) or len(timeout) != 2 or
                any(type(v) not in (int, float) or not 0 < v <= 120 for v in timeout)):
            raise ConfigurationError("Timeout requires two positive values at most 120 seconds")
        if type(allow_writes) is not bool:
            raise ConfigurationError("allow_writes must be boolean")
        self.allow_writes = allow_writes
        self.max_retries = integer(max_retries, 'max_retries', 0, 3)
        self.timeout = tuple(timeout)
        self._sleep = sleep
        token = key_value(api_key)
        self.session = session or requests.Session()
        self.session.headers.update({'Authorization': f'Bearer {token}',
                                     'Accept': 'application/json'})

    def close(self):
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def _request(self, method, path, *, _read_only=True, _envelope=True, **kwargs):
        # Non-idempotent/unknown-effect mutations are never replayed automatically.
        retries = self.max_retries if _read_only else 0
        for attempt in range(retries + 1):
            response = None
            try:
                response = self.session.request(method, self.BASE_URL + path,
                                                timeout=self.timeout, allow_redirects=False, **kwargs)
            except (requests.Timeout, requests.ConnectionError):
                if attempt == retries:
                    raise PocketError("Pocket connection failed or timed out" if _read_only else
                                      "Pocket write outcome unknown; reconcile before retrying") from None
            except requests.RequestException:
                raise PocketError("Pocket request failed") from None
            else:
                status = response.status_code
                if status not in (429, 500, 502, 503, 504) or attempt == retries:
                    try:
                        if not 200 <= status < 300:
                            raise APIError(status)
                        if status == 204 and not _read_only:
                            return {"success": True}
                        try:
                            result = response.json()
                        except (ValueError, requests.RequestException):
                            raise ResponseError("Pocket returned invalid JSON") from None
                        if not isinstance(result, dict):
                            raise ResponseError("Pocket response must be an object")
                        if result.get('success') is False or result.get('error'):
                            raise ResponseError("Pocket reported an application error")
                        if _envelope and ('data' not in result or result['data'] is None):
                            raise ResponseError("Pocket response is missing data")
                        if not result:
                            raise ResponseError("Pocket returned an empty response object")
                        return result
                    finally:
                        response.close()
            delay = min(2 ** attempt, 8)
            if response is not None:
                # Do not retry earlier than an advertised numeric Retry-After.
                retry_after = response.headers.get('Retry-After')
                response.close()
                if retry_after:
                    try:
                        wait = float(retry_after)
                    except ValueError:
                        raise APIError(status) from None
                    if not 0 <= wait <= 8:
                        raise APIError(status)
                    delay = max(delay, wait)
            self._sleep(delay)
        raise PocketError("Pocket retry budget exhausted")

    def operation(self, name, *, path=None, query=None, body=None, confirm=False):
        """Call a documented REST operation. See pocket_catalog and docs/API-COVERAGE.md.

        Writes require both allow_writes=True and confirm=True for this call.
        Returns the service envelope unchanged (organization schemas vary).
        """
        from pocket_operations import prepare_operation
        spec, route, params, payload = prepare_operation(name, path, query, body)
        if not spec.read_only and not (self.allow_writes and confirm is True):
            raise ConfigurationError("Write requires allow_writes=True and confirm=True")
        kwargs = {"params": params}
        if payload is not None:
            kwargs["json"] = payload
        return self._request(spec.method, route, _read_only=spec.read_only,
                             _envelope=spec.envelope, **kwargs)

    def list_folders(self):
        return self.operation('list_folders')['data']

    def create_upload_url(self, *, confirm=False, **metadata):
        return self.operation('create_upload_url', body=metadata, confirm=confirm)

    def search(self, query, *, limit=8, filters=None):
        if not isinstance(query, str) or not query.strip():
            raise ConfigurationError("Search query must not be blank")
        body = {'query': query, 'limit': integer(limit, 'limit', 1, 20)}
        if filters is not None:
            if not isinstance(filters, dict) or set(filters) - {'dateFrom','dateTo','folderIds','recordingIds'}:
                raise ConfigurationError("Unsupported search filters")
            for k, v in filters.items():
                if k in ('dateFrom', 'dateTo'):
                    timestamp(v)
                elif not isinstance(v, list) or any(not isinstance(x, str) or not x for x in v):
                    raise ConfigurationError("ID filters require lists of nonempty strings")
            if 'dateFrom' in filters and 'dateTo' in filters and timestamp(filters['dateFrom']) >= timestamp(filters['dateTo']):
                raise ConfigurationError("Search date range is reversed or empty")
            body['filters'] = filters.copy()
        return self._request('POST', '/public/search', json=body)

    def get_memories(self, query, limit=10, *, filters=None):
        data = self.search(query, limit=limit, filters=filters)['data']
        if not isinstance(data, dict) or 'relevantMemories' not in data:
            raise ResponseError("Unsupported search shape; legacy relevantMemories unavailable")
        memories = objects(data['relevantMemories'], 'memory')
        result = []
        for m in memories[:limit]:
            if not isinstance(m.get('content'), str):
                raise ResponseError("Invalid memory content")
            result.append({'content':m['content'], 'date':m.get('recordingDate'),
                           'title':m.get('recordingTitle'), 'speakers':m.get('speakers'),
                           'score':m.get('relevanceScore'), 'recording_id':m.get('recordingId'),
                           'transcription_id':m.get('transcriptionId'), 'metadata':m.get('metadata', {})})
        return result

    def get_action_items(self, query='action items tasks todo follow up', *, limit=20, filters=None):
        """Legacy snippet fallback only, not a complete/open task inventory.

        Returns structured provenance records rather than the old list of strings.
        Use PocketMCP.search_action_items for authoritative task status and IDs.
        """
        result = []
        for memory in self.get_memories(query, limit, filters=filters):
            for line in memory['content'].splitlines():
                match = re.search(r'action item:\s*(.+)', line, re.IGNORECASE)
                if match:
                    result.append({'title':match.group(1).strip(), 'status':None,
                                   'recording_id':memory['recording_id'], 'recording_at':memory['date'],
                                   'source':'search_snippet', 'complete':False})
        return result

    def get_user_profile(self, query='business'):
        """Explicit opt-in legacy profile access; never used by default briefings."""
        data = self.search(query)['data']
        if not isinstance(data, dict) or not isinstance(data.get('userProfile'), dict):
            raise ResponseError("Legacy profile data unavailable")
        values = data['userProfile'].get('dynamicContext')
        if not isinstance(values, list) or any(not isinstance(v, str) for v in values):
            raise ResponseError("Invalid profile response")
        return values

    def list_tags(self):
        return objects(self._request('GET', '/public/tags')['data'], 'tag')

    def list_recordings(self, page=1, limit=20, *, start_date=None, end_date=None, tag_ids=None):
        params = {'page':integer(page,'page',1,1000000), 'limit':integer(limit,'limit',1,100)}
        for name, value in [('start_date',start_date),('end_date',end_date)]:
            if value is not None:
                try:
                    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
                        raise ValueError('invalid date')
                    date.fromisoformat(value)
                except (TypeError, ValueError):
                    raise ConfigurationError("Recording dates must be YYYY-MM-DD") from None
                params[name] = value
        if start_date and end_date and start_date > end_date:
            raise ConfigurationError("Recording dates are reversed")
        if tag_ids is not None:
            if not isinstance(tag_ids, list) or any(not isinstance(v,str) or not v or ',' in v for v in tag_ids):
                raise ConfigurationError("tag_ids must be a list of IDs")
            params['tag_ids'] = ','.join(tag_ids)
        result = self._request('GET', '/public/recordings', params=params)
        objects(result['data'], 'recording')
        return result

    def iter_recordings(self, *, max_pages=100, **filters):
        integer(max_pages, 'max_pages', 1, 10000)
        seen = set()
        for page in range(1, max_pages + 1):
            response = self.list_recordings(page=page, limit=100, **filters)
            pagination = response.get('pagination')
            if not isinstance(pagination, dict) or type(pagination.get('has_more')) is not bool:
                raise ResponseError("Recording pagination is missing or invalid")
            if pagination.get('page', page) != page:
                raise ResponseError("Unexpected recording page")
            new = 0
            for recording in response['data']:
                rid = recording.get('id')
                if not isinstance(rid,str) or not rid:
                    raise ResponseError("Recording ID missing")
                if rid not in seen:
                    seen.add(rid)
                    new += 1
                    yield recording
            if not pagination['has_more']:
                return
            if not new:
                raise ResponseError("Recording pagination made no progress")
        raise ResponseError("Recording page budget exhausted; retrieval incomplete")

    def get_recording(self, recording_id):
        result = self._request('GET', '/public/recordings/' + identifier(recording_id))
        if not isinstance(result['data'], dict):
            raise ResponseError("Invalid recording details")
        return result

    def get_audio_url(self, recording_id, *, expires_in=None):
        """Return service data containing a signed URL; no audio fetch or URL logging."""
        params = {} if expires_in is None else {'expires_in':integer(expires_in,'expires_in',60,86400)}
        return self._request('GET', '/public/recordings/' + identifier(recording_id) + '/audio-url', params=params)['data']

    def search_contact(self, name, **kwargs):
        """Bounded relevant mentions, never an exhaustive contact history."""
        return self.get_memories(f'conversations with {name} discussions', **kwargs)

    def search_topic(self, topic, **kwargs):
        return self.search(f'{topic} discussion decisions strategy', **kwargs)

    def recordings_for_day(self, day=None, *, timezone_name='UTC', max_pages=100):
        start, end = day_interval(day, timezone_name)
        selected, issues = [], []
        for r in self.iter_recordings(start_date=start.date().isoformat(),
                                     end_date=end.date().isoformat(), max_pages=max_pages):
            try:
                at = timestamp(r.get('recording_at'))
            except ResponseError:
                issues.append({'recording_id':r['id'], 'reason':'missing_or_invalid_recording_at'})
                continue
            if start <= at < end:
                selected.append(r)
        return selected, issues, start, end

    def daily_briefing_data(self, day=None, *, timezone_name='UTC', max_pages=100):
        """Read every selected recording; return actual summaries and structured tasks.

        Unknown schemas/processing states are explicit incomplete results, never empty success.
        """
        from pocket_models import normalize_recording
        records, issues, start, end = self.recordings_for_day(day, timezone_name=timezone_name, max_pages=max_pages)
        normalized = []
        for r in records:
            details = self.get_recording(r['id'])['data']
            if details.get('id') != r['id']:
                raise ResponseError("Recording detail ID does not match inventory")
            item = normalize_recording(details)
            try:
                if not start <= timestamp(details.get('recording_at')) < end:
                    item['issues'].append('recording_date_changed_since_inventory')
                    issues.extend({'recording_id':r['id'], 'reason':reason} for reason in item['issues'])
                    continue
            except ResponseError:
                item['issues'].append('recording_detail_date_unavailable')
            normalized.append(item)
            issues.extend({'recording_id':r['id'], 'reason':reason} for reason in item['issues'])
        return {'interval':{'start':start.isoformat(), 'end_exclusive':end.isoformat(), 'timezone':timezone_name},
                'recordings':normalized,
                'action_items':[a for r in normalized for a in r['action_items'] if a['status'] in ('TODO','IN_PROGRESS')],
                'unknown_status_action_items':[a for r in normalized for a in r['action_items'] if a['status'] is None],
                'complete':not issues, 'issues':issues,
                'coverage':'recording summaries, not an exhaustive global Pocket task inventory'}

    def get_meeting_summary(self, date=None, *, timezone_name='UTC'):
        return self.daily_briefing_data(date, timezone_name=timezone_name)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Read-only Pocket integration (JSON output)')
    sub = parser.add_subparsers(dest='command', required=True)
    search = sub.add_parser('search')
    search.add_argument('query')
    search.add_argument('--limit', type=int, default=8)
    search.add_argument('--date-from')
    search.add_argument('--date-to')
    search.add_argument('--folder-id', action='append')
    search.add_argument('--recording-id', action='append')
    search.add_argument('--include-profile', action='store_true', help='Include legacy profile data explicitly')
    sub.add_parser('tags')
    rec = sub.add_parser('recordings')
    rec.add_argument('--start-date')
    rec.add_argument('--end-date')
    rec.add_argument('--tag-id', action='append')
    rec.add_argument('--max-pages', type=int, default=100)
    one = sub.add_parser('recording')
    one.add_argument('id')
    brief = sub.add_parser('briefing')
    brief.add_argument('--date')
    brief.add_argument('--timezone', default='UTC')
    brief.add_argument('--max-pages', type=int, default=100)
    args = parser.parse_args(argv)
    try:
        with PocketAI() as pocket:
            if args.command == 'search':
                filters = {k:v for k,v in {'dateFrom':args.date_from,'dateTo':args.date_to,
                           'folderIds':args.folder_id,'recordingIds':args.recording_id}.items() if v is not None}
                result = pocket.search(args.query, limit=args.limit, filters=filters)
                if not args.include_profile and isinstance(result['data'], dict):
                    result['data'] = {k:v for k,v in result['data'].items() if k != 'userProfile'}
            elif args.command == 'tags':
                result = pocket.list_tags()
            elif args.command == 'recordings':
                result = list(pocket.iter_recordings(start_date=args.start_date,end_date=args.end_date,
                                                    tag_ids=args.tag_id,max_pages=args.max_pages))
            elif args.command == 'recording':
                result = pocket.get_recording(args.id)
            else:
                result = pocket.daily_briefing_data(args.date,timezone_name=args.timezone,max_pages=args.max_pages)
        print(json.dumps(result, ensure_ascii=False))
        return 3 if isinstance(result, dict) and result.get('complete') is False else 0
    except PocketError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except (OSError, ValueError):
        print('Pocket configuration or output error', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
