#!/usr/bin/env python3
from __future__ import annotations
import json,os,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"server"))
from edge1_snmp_platform import CredentialResolver,add_device,allowed_discovery_hosts,canonical_oid,connect_db,counter_rate,evidence_query,normalize_trap,propose_action,rolling_anomaly,validate_config
class SNMPPlatformTests(unittest.TestCase):
 def setUp(self): self.tmp=tempfile.TemporaryDirectory(); self.db=Path(self.tmp.name)/"snmp.sqlite3"; self.conn=connect_db(self.db)
 def tearDown(self): self.conn.close(); self.tmp.cleanup()
 def test_oid_validation(self):
  self.assertEqual(canonical_oid(".1.3.6.1.2.1.1.3.0"),"1.3.6.1.2.1.1.3.0")
  with self.assertRaises(ValueError): canonical_oid("1.3.bad")
 def test_counter_rate_and_reset(self):
  self.assertEqual(counter_rate(100,300,10),20); self.assertIsNone(counter_rate(300,100,10,bits=32)); self.assertIsNone(counter_rate(100,300,10,rebooted=True)); self.assertEqual(counter_rate((1<<32)-10,20,5,bits=32),6)
 def test_anomaly_math(self):
  self.assertTrue(rolling_anomaly([10,10,11,9,10,10,11],100)["anomalous"]); self.assertEqual(rolling_anomaly([1,2],5)["reason"],"insufficient_baseline")
 def test_inventory_defaults_to_v3_and_rejects_unapproved_legacy(self):
  row=add_device(self.conn,{"display_name":"router-01","management_address":"192.0.2.10","credential_reference":"router-01-v3"}); self.assertEqual(row["snmp_version"],"3"); self.assertFalse(bool(row["write_enabled"]))
  with self.assertRaises(ValueError): add_device(self.conn,{"display_name":"legacy","management_address":"192.0.2.11","credential_reference":"legacy-ro","snmp_version":"2c"})
 def test_credentials_require_private_permissions(self):
  d=Path(self.tmp.name)/"profiles"; d.mkdir(); p=d/"x.json"; p.write_text(json.dumps({"version":"3","username":"u","auth_protocol":"SHA","auth_password":"secret-a","priv_protocol":"AES","priv_password":"secret-b"}),encoding="utf-8"); os.chmod(p,0o600); self.assertEqual(CredentialResolver(d).load("x").version,"3"); os.chmod(p,0o644)
  with self.assertRaises(PermissionError): CredentialResolver(d).load("x")
 def test_discovery_is_bounded(self):
  cfg={"polling":{"interval_seconds":300,"concurrency":4},"discovery":{"allowed_cidrs":["10.10.0.0/16"],"max_hosts":32,"allow_public":False}}; self.assertEqual(len(allowed_discovery_hosts("10.10.1.0/29",cfg)),6)
  with self.assertRaises(PermissionError): allowed_discovery_hosts("10.20.1.0/29",cfg)
  with self.assertRaises(ValueError): allowed_discovery_hosts("10.10.0.0/24",cfg)
 def test_trap_deduplication(self):
  payload={"source_address":"192.0.2.4","trap_oid":"1.3.6.1.6.3.1.1.5.3","varbinds":{"x":"y"}}; self.assertFalse(normalize_trap(self.conn,payload)["duplicate"]); self.assertTrue(normalize_trap(self.conn,payload)["duplicate"])
 def test_ai_evidence_is_typed(self):
  add_device(self.conn,{"display_name":"switch-01","management_address":"192.0.2.20","credential_reference":"sw-v3"}); result=evidence_query(self.conn,"summarize network health"); self.assertIn("observed_facts",result); self.assertIn("ai_inferences",result); self.assertIn("evidence",result); self.assertEqual(result["provider"],"deterministic-evidence-layer")
 def test_action_policy_requires_validation_and_rollback(self):
  p=propose_action(self.conn,actor="ai",action="restart_snmp_service",target="edge1-snmp-api.service",reason="health probe failed"); self.assertEqual(p["state"],"pending_review")
  p2=propose_action(self.conn,actor="ai",action="restart_snmp_service",target="edge1-snmp-api.service",reason="health probe failed",validation={"health_check":"/api/snmp/health"},rollback={"action":"restart_previous"}); self.assertEqual(p2["state"],"approved")
 def test_configuration_validation(self):
  validate_config({"polling":{"interval_seconds":60,"concurrency":8},"discovery":{"allowed_cidrs":["192.168.0.0/16"],"max_hosts":128}})
  with self.assertRaises(ValueError): validate_config({"polling":{"interval_seconds":1}})
if __name__=="__main__": unittest.main(verbosity=2)
