import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from server.mail_security_updates import update_health
from tools.messaging.mail_room_attachment_scan import scanner_ready


class UpdateHealthTests(unittest.TestCase):
    def test_stale_and_failed_checks_preserve_last_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            self.assertEqual(len(update_health(root,1000000)['warnings']),2)
            (root/'definitions.json').write_text(json.dumps({'last_success':999000,'last_attempt':999500,'last_result':'failed'}))
            health=update_health(root,1000000)
            self.assertFalse(health['jobs']['definitions']['stale'])
            self.assertIn('definitions_update_attention',health['warnings'])
            self.assertEqual(health['jobs']['definitions']['last_success'],999000)
            self.assertTrue(update_health(root,1010000)['jobs']['definitions']['stale'])
            (root/'packages.json').write_text('{malformed')
            self.assertEqual(update_health(root)['jobs']['packages']['last_result'],'unavailable')
    def test_fresh_verification_allows_unchanged_old_definitions(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);daily=root/'daily.cvd';daily.write_text('unchanged')
            import os
            os.utime(daily,(1,1))
            marker=root/'definitions.json';marker.write_text(json.dumps({'last_success':999999}));marker.chmod(0o640)
            original=Path.exists
            def exists(path):
                return True if str(path)=='/etc/clamav/wwcx-mail-clamd.conf' else original(path)
            original_stat=Path.stat
            def stats(path,*args,**kwargs):
                result=original_stat(path,*args,**kwargs)
                if path==marker:
                    from types import SimpleNamespace
                    return SimpleNamespace(st_uid=0,st_mode=result.st_mode)
                return result
            original_path=Path
            def paths(value):return marker if str(value)=='/var/lib/wwcx-mail-updates/definitions.json' else original_path(value)
            with patch('tools.messaging.mail_room_attachment_scan.shutil.which',return_value='/bin/clamscan'),patch('tools.messaging.mail_room_attachment_scan.time.time',return_value=1000000),patch.object(Path,'exists',exists),patch('tools.messaging.mail_room_attachment_scan.Path',side_effect=paths),patch.object(Path,'stat',stats):
                self.assertTrue(scanner_ready(root))
                marker.write_text(json.dumps({'last_success':900000}))
                self.assertFalse(scanner_ready(root))
                marker.write_text('{bad')
                self.assertFalse(scanner_ready(root))
                marker.write_text(json.dumps({'last_success':999999}));marker.chmod(0o666)
                self.assertFalse(scanner_ready(root))

if __name__=='__main__':unittest.main()
