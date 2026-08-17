#!/usr/bin/env python3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
checks={
 'server/edge1_comms/control.py':['/api/comms/irc/channels/','recent_irc','mode\':\'read_only'],
 'src/web/comms-relay/app.js':['Copy AI briefing','copyChannelPrompt','history?limit=50'],
 'src/web/comms-relay/news.js':['copyArticlePrompt','Private AI prompt copied','slice(0, 12000)'],
 'src/web/comms-relay/news.html':['copy-ai-summary','copy-ai-explain','No data is sent automatically.'],
}
for name,markers in checks.items():
 text=(ROOT/name).read_text()
 for marker in markers:
  if marker not in text: raise SystemExit(f'{name} missing {marker}')
print('communications Private AI prompt controls validation passed')
