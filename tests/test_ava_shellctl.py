from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tools import ava_shellctl as ctl

class Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name)
        p1=patch.object(ctl,'GATE_DIR',root/'gates'); p1.start(); self.addCleanup(p1.stop)
        p2=patch.object(ctl,'AUDIT',root/'audit.jsonl'); p2.start(); self.addCleanup(p2.stop)
    def test_enable_status_disable(self):
        value=ctl.enable('edge1',15,'tester','diagnosis','T1')
        self.assertTrue(value['enabled'])
        self.assertEqual((ctl.GATE_DIR/'edge1.json').stat().st_mode & 0o777,0o600)
        value=ctl.disable('edge1','tester'); self.assertFalse(value['enabled'])
    def test_hosts_are_independent(self):
        ctl.enable('edge1',15,'tester','diagnosis','')
        self.assertTrue(ctl.status('edge1')['enabled']); self.assertFalse(ctl.status('business159')['enabled'])
    def test_maximum_window_is_bounded(self):
        with self.assertRaises(SystemExit): ctl.enable('edge1',241,'tester','x','')

if __name__=='__main__': unittest.main()
