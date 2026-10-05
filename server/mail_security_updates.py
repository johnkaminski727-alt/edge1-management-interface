"""Read-only, aggregate update health; state is written only by root jobs."""
import json
from pathlib import Path
import time

STATE = Path('/var/lib/wwcx-mail-updates')
SCHEDULES = {'definitions': 'Hourly at :10 (UTC)', 'packages': 'Daily at 03:15 America/Regina (09:15 UTC)'}


def update_health(directory=STATE, now=None):
    now = time.time() if now is None else now
    result = {'schedule_timezone': 'America/Regina', 'jobs': {}, 'warnings': []}
    for name, schedule in SCHEDULES.items():
        try:
            record = json.loads((directory / (name + '.json')).read_text())
            success = float(record.get('last_success') or 0)
            attempt = float(record.get('last_attempt') or 0)
            if success > now + 300 or attempt > now + 300: raise ValueError('Future timestamp')
            age = now - success if success else None
            stale = age is None or age > (3*3600 if name == 'definitions' else 36*3600)
            job = {'schedule': schedule, 'last_success': success or None, 'last_attempt': attempt or None,
                   'last_result': record.get('last_result'), 'versions': record.get('versions', {}), 'stale': stale}
            if stale or job['last_result'] != 'success': result['warnings'].append(name + '_update_attention')
        except (OSError, ValueError, TypeError):
            job = {'schedule': schedule, 'last_success': None, 'last_attempt': None, 'stale': True, 'last_result': 'unavailable'}
            result['warnings'].append(name + '_update_unavailable')
        result['jobs'][name] = job
    return result
