#!/usr/bin/env python3
from __future__ import annotations
import importlib.util,json,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"tools/networking/spamhaus_boot_restore.py"
SPEC=importlib.util.spec_from_file_location("restore",SRC)
M=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(M)

class Fake:
    def __init__(self,present=False,check_fail=False,apply_fail=False):
        self.present=present; self.check_fail=check_fail; self.apply_fail=apply_fail; self.commands=[]
    def __call__(self,args):
        self.commands.append(list(args))
        if args[:4]==[M.NFT,"-j","list","tables"]:
            tables=[{"table":{"family":"inet","name":"ufw"}}]
            if self.present: tables.append({"table":{"family":"inet","name":"bigbird_spamhaus"}})
            return subprocess.CompletedProcess(args,0,json.dumps({"nftables":tables}),"")
        if args[:3]==[M.NFT,"--check","--file"]:
            return subprocess.CompletedProcess(args,1 if self.check_fail else 0,"","")
        if args[:2]==[M.NFT,"--file"]:
            if not self.apply_fail: self.present=True
            return subprocess.CompletedProcess(args,1 if self.apply_fail else 0,"","")
        raise AssertionError(args)

class T(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.c=Path(self.tmp.name)/"c.nft"; self.c.write_text("table inet bigbird_spamhaus {}\n")
    def swap(self,f):
        old=M.run; M.run=f; self.addCleanup(lambda:setattr(M,"run",old))
    def test_default_check_only(self):
        f=Fake(); self.swap(f); self.assertEqual(M.restore(self.c),"eligible_check_only"); self.assertFalse(f.present)
    def test_execute_restores_and_verifies(self):
        f=Fake(); self.swap(f); self.assertEqual(M.restore(self.c,execute=True),"restored_verified"); self.assertTrue(f.present)
    def test_existing_table_is_not_replaced(self):
        f=Fake(present=True); self.swap(f); self.assertEqual(M.restore(self.c,execute=True),"already_present"); self.assertEqual(len(f.commands),1)
    def test_check_failure_blocks_apply(self):
        f=Fake(check_fail=True); self.swap(f)
        with self.assertRaises(RuntimeError): M.restore(self.c,execute=True)
        self.assertFalse(any(x[:2]==[M.NFT,"--file"] for x in f.commands))
    def test_apply_failure_reported(self):
        f=Fake(apply_fail=True); self.swap(f)
        with self.assertRaises(RuntimeError): M.restore(self.c,execute=True)
    def test_missing_candidate_rejected(self):
        f=Fake(); self.swap(f)
        with self.assertRaises(RuntimeError): M.restore(Path(self.tmp.name)/"missing",execute=True)

if __name__=="__main__": unittest.main()
