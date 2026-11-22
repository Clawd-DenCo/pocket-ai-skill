"""Documented Pocket operations, inspected 2026-11-22. No arbitrary URL dispatch."""
from dataclasses import dataclass

DOCS = 'https://docs.heypocketai.com/docs/api/'

@dataclass(frozen=True)
class Operation:
    method: str
    path: str
    source: str
    query: tuple = ()
    body: tuple = ()
    required: tuple = ()
    read_only: bool = True
    envelope: bool = True
    body_documented: bool = True

OPERATIONS = {}
def add(name, method, path, source, *, query='', body='', required='', read_only=None,
        envelope=True, body_documented=True):
    OPERATIONS[name] = Operation(method, path, DOCS + source, tuple(query.split()),
        tuple(body.split()), tuple(required.split()), method == 'GET' if read_only is None else read_only,
        envelope, body_documented)

add('search', 'POST', '/public/search', 'search/search-recordings', body='query limit filters', required='query', read_only=True)
add('list_recordings','GET','/public/recordings','recordings/list-recordings',query='start_date end_date tag_ids page limit')
add('get_recording','GET','/public/recordings/{recording_id}','recordings/get-recording-details',query='include_transcript include_summarizations summarization_id')
add('get_audio_url','GET','/public/recordings/{recording_id}/audio-url','recordings/get-audio-download-url',query='expires_in')
add('create_upload_url','POST','/public/recordings/upload-url','recordings/create-upload-url',body='content_type duration file_name recording_at title')
add('list_folders','GET','/public/folders','folders/list-folders-and-spaces')
add('list_tags','GET','/public/tags','tags/list-tags')
settings_query = 'include include_profile include_preferences include_tags include_notifications preferences_page preferences_limit'
settings_body = 'settings notifications profile preferences'
add('list_users','GET','/public/users','users/list-organization-users',query='q page limit')
add('get_user_settings','GET','/public/users/{user_id}/settings','users/get-an-organization-member-s-settings-bundle',query=settings_query)
add('update_user_settings','PATCH','/public/users/{user_id}/settings','organization/users',body=settings_body,envelope=False)
org = '/organization/{org_id}'
for resource, singular, ident, fields, required in [
    ('api-keys','api_key','key_id','name scopes expires_at','name scopes'),
    ('templates','template','template_id','name description sections','name sections')]:
    source = 'organization/' + resource
    add('list_org_' + resource.replace('-','_'),'GET',org+'/'+resource,source,envelope=False)
    add('get_org_'+singular,'GET',org+'/'+resource+'/{'+ident+'}',source,envelope=False)
    add('create_org_'+singular,'POST',org+'/'+resource,source,body=fields,required=required,envelope=False)
    add('delete_org_'+singular,'DELETE',org+'/'+resource+'/{'+ident+'}',source,envelope=False)
    if resource == 'templates':
        add('update_org_template','PATCH',org+'/templates/{template_id}',source,body=fields,envelope=False)
add('get_org_analytics','GET',org+'/analytics','organization/analytics',query='start_date end_date',envelope=False)
add('list_org_recordings','GET',org+'/recordings','organization/recordings',query='date startDate endDate tagIds tagMode recordedBy recordedByEmail page limit cursor',envelope=False)
add('get_org_recording','GET',org+'/recordings/{recording_id}','organization/recordings',query='include',envelope=False)
add('update_org_recording','PUT',org+'/recordings/{recording_id}','organization/recordings',body='title description tags',envelope=False)
add('delete_org_recording','DELETE',org+'/recordings/{recording_id}','organization/recordings',query='permanent',envelope=False)
add('update_org_member','PATCH',org+'/members/{user_id}','organization/members',body='role status',envelope=False)
add('list_org_users','GET',org+'/users','organization/users',query='q page limit')
add('get_org_user_settings','GET',org+'/users/{user_id}/settings','organization/users',query=settings_query)
add('update_org_user_settings','PATCH',org+'/users/{user_id}/settings','organization/users',body=settings_body,envelope=False)
add('send_org_invite','POST',org+'/invites','organization/invites',body='email role',required='email',envelope=False)
add('accept_org_invite','POST','/organization/invites/accept','organization/invites',body='token',required='token',envelope=False)
add('revoke_org_invite','DELETE',org+'/invites/{invite_id}','organization/invites',envelope=False)
add('resend_org_invite','POST',org+'/invites/{invite_id}/resend','organization/invites',envelope=False)
for name,method,suffix in [('list_org_webhooks','GET',''),('get_org_webhook','GET','/{webhook_id}'),
    ('create_org_webhook','POST',''),('update_org_webhook','PUT','/{webhook_id}'),
    ('delete_org_webhook','DELETE','/{webhook_id}'),('test_org_webhook','POST','/{webhook_id}/test')]:
    # Official docs publish routes, not create/update body schemas. Preserve explicit payloads.
    add(name,method,org+'/webhooks'+suffix,'webhooks',envelope=False,
        body_documented=name not in ('create_org_webhook','update_org_webhook'))

PERSONAL_READ_TOOLS = frozenset({'get_account_info','list_pocket_folders','search_pocket_conversations',
    'search_pocket_actionitems','get_pocket_conversation','query_pocket_meetings'})
ORG_READ_TOOLS = frozenset({'list_org_recordings','get_org_recording','get_org_recording_audio_url',
    'search_org_recordings','list_org_tags','list_org_templates','get_org_template','get_org_analytics'})
WRITE_TOOLS = frozenset({'update_pocket_actionitem','create_org_template','update_org_template','delete_org_template'})
READ_TOOLS = PERSONAL_READ_TOOLS | ORG_READ_TOOLS
