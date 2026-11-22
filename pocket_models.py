"""Conservative adapters for documented Pocket recording summary structures."""
from pocket_api import timestamp, ResponseError


def normalize_recording(record):
    rid = record.get('id')
    issues = []
    result = {'recording_id':rid, 'title':record.get('title'),
              'recording_at':record.get('recording_at'), 'state':record.get('state'),
              'summary':None, 'action_items':[], 'transcript_segments':[], 'issues':issues}
    if record.get('transcript_error') or record.get('summarizations_errors'):
        issues.append('processing_error')
    transcript = record.get('transcript')
    if isinstance(transcript, dict) and isinstance(transcript.get('segments'), list):
        for s in transcript['segments']:
            if (not isinstance(s, dict) or not isinstance(s.get('text'), str) or
                type(s.get('start')) not in (int, float) or type(s.get('end')) not in (int, float) or
                not 0 <= s['start'] <= s['end']):
                issues.append('invalid_transcript_segment')
                continue
            result['transcript_segments'].append({k:s.get(k) for k in ('text','start','end','speaker','speakerName')})
    else:
        issues.append('transcript_unavailable')
    summaries = record.get('summarizations')
    if not isinstance(summaries, dict) or not summaries or any(not isinstance(v,dict) for v in summaries.values()):
        issues.append('summary_unavailable_or_unsupported')
        return result
    candidates = list(summaries.values())
    if len(candidates) > 1:
        try:
            candidates.sort(key=lambda s: timestamp(s.get('updatedAt') or s.get('createdAt')))
            if timestamp(candidates[-1].get('updatedAt') or candidates[-1].get('createdAt')) == timestamp(candidates[-2].get('updatedAt') or candidates[-2].get('createdAt')):
                raise ResponseError('ambiguous')
        except ResponseError:
            issues.append('ambiguous_latest_summary')
            return result
    latest = candidates[-1]
    if latest.get('processingStatus') != 'completed':
        issues.append('summary_processing_incomplete')
        return result
    v2 = latest.get('v2')
    if not isinstance(v2,dict):
        issues.append('unsupported_summary_schema')
        return result
    summary = v2.get('summary')
    if not isinstance(summary, dict):
        issues.append('summary_unavailable')
    else:
        result['summary'] = {'recording_id':rid, 'summarization_id':latest.get('summarizationId'),
                             'recording_at':record.get('recording_at'), 'content':summary}
    block = v2.get('actionItems')
    if not isinstance(block,dict) or not isinstance(block.get('actionItems'),list):
        issues.append('structured_action_items_unavailable')
        return result
    seen = set()
    for task in block['actionItems']:
        if not isinstance(task,dict):
            issues.append('invalid_action_item')
            continue
        tid = task.get('id')
        if not isinstance(tid,str) or not tid or not isinstance(task.get('title'),str):
            issues.append('action_item_identity_or_title_missing')
            continue
        if tid in seen:
            issues.append('duplicate_action_item_id')
            continue
        seen.add(tid)
        status = task.get('status')
        if status not in ('TODO','IN_PROGRESS','COMPLETED','CANCELLED'):
            status = None
            issues.append('action_item_status_unknown')
        flags = [task[k] for k in ('isCompleted','is_completed') if k in task]
        if any(type(f) is not bool for f in flags) or (flags and (len(set(flags)) > 1 or (status is not None and flags[0] != (status == 'COMPLETED')))):
            status = None
            issues.append('action_item_status_conflict')
        result['action_items'].append({'id':tid, 'global_action_item_id':task.get('globalActionItemId'),
                                      'parent_task_id':task.get('parentTaskId'), 'title':task['title'],
                                      'status':status, 'due_date':task.get('dueDate'),
                                      'assignee':task.get('assignee'), 'priority':task.get('priority'),
                                      'recording_id':rid, 'recording_at':record.get('recording_at'),
                                      'source':'recording_summary'})
    return result
