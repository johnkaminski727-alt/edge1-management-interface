"""Mail Room admin authorization through the existing authenticated session service."""
import json
import urllib.request


def admin_session(headers, fetch=None):
    cookie=headers.get('Cookie','')
    if not cookie or len(cookie)>8192: return False
    request=urllib.request.Request('http://127.0.0.1:8108/edge1-ops/session',headers={
        'Cookie':cookie,'Host':'edge1.ww.cx','X-Forwarded-Proto':'https',
        'X-Edge1-Client-IP':headers.get('X-Edge1-Client-IP',''),
        'X-Edge1-Original-Path':'/edge1-ops/mail-room/','X-Edge1-Request-ID':headers.get('X-Edge1-Request-ID','mail-room')})
    try:
        with (fetch or urllib.request.urlopen)(request,timeout=5) as response:
            context=json.loads(response.read(65536))
        return context.get('authenticated') is True and context.get('source_role')=='admin' and 'edge1.security.read' in context.get('scopes',[])
    except Exception: return False


ACCESS_POLICY={'mode':'admin_only','read_mail':'Authenticated admin only, including private and company addresses',
 'review_quarantine':'Admin; explicit plain-text review required','release_quarantine':'Admin; explicit acknowledgement and completed checks required; hard malware findings cannot be released',
 'change_filters':'Admin','compose_and_prepare':'Admin; drafts only','send':'Disabled for everyone',
 'ava':'Explicit assistance on released mail only; no sending, quarantine release or filtering authority',
 'shared_mailbox_delegation':'Disabled until individual mailbox grants and isolated drafts are commissioned',
 'retention':'No automatic deletion enabled; retention periods require a separate approved policy'}
