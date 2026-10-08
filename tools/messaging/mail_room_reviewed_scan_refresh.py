import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from tools.messaging.mail_room_reviewed_scan import reviewed_scan,REVIEW_FILE
records=json.loads(REVIEW_FILE.read_text());result=[]
for digest,r in records.items():
 raw=Path(r['raw_path']).read_bytes()
 result.append({'sha256':digest,'clean':reviewed_scan(raw)})
print(json.dumps(result))
raise SystemExit(0 if all(x['clean'] for x in result) else 1)
