#!/usr/bin/env python3
"""G3 tests: whitelist, stale-data fail-closed, private authenticated HTTP."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import tempfile
import threading
import urllib.error
import urllib.request
import unittest

TOOL=Path(__file__).resolve().parents[1]/"tools/operations"
sys.path.insert(0,str(TOOL))
from edge1_operations_view import summarize
from edge1_operations_api import G3Server
from edge1_host_metrics import read_metrics
from edge1_candidate_store import CandidateStore

TOKEN="a"*64


class G3Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name)
        self.core=root/"core.json"
        self.security=root/"defense.json"
        self.now=datetime.now(timezone.utc)
        self.core_data={
            "schema_version":"wwcx.core-observation.v1","read_only":True,
            "traffic_controls_changed":False,"generated_at":self.now.isoformat(),
            "services":{"ufw":{"state":"active","credentials":"SECRET"},
                        "unbound":{"state":"failed"},"unknown-hidden-service":{"state":"active"}},
            "interfaces":{"ens3":{"available":True,"up":True,"address":"192.0.2.77"},
                          "wg0":{"available":True,"up":False,"peer":"privatepeer"}},
            "routing":{"ipv4_forwarding":1,"ipv6_forwarding":0}}
        self.security_data={
            "generated_at":self.now.isoformat(),"traffic_controls_changed":False,
            "components":{
                "spamhaus":{"state":"feed_ready","observed":True,"enforcement_verified":False,
                            "metrics":{"combined_ipv4_networks":1500,"raw_ruleset":"NEVER_EXPORT"}},
                "ids":{"state":"observed","observed":True,"metrics":{"recent_alerts":11,"secret":"SECRET"}},
                "foreign_component":{"state":"healthy","observed":True,"metrics":{"password":"SECRET"}}},
            "sources":{"network":{"available":True}}}
        self.dump()

    def dump(self):
        self.core.write_text(json.dumps(self.core_data))
        self.security.write_text(json.dumps(self.security_data))

    def test_curated_services_interfaces_security_and_no_secrets(self):
        view=summarize(self.core,self.security,now=self.now)
        self.assertEqual(view["summary"]["active_services"],1)
        self.assertEqual(view["summary"]["interface_up"],1)
        self.assertEqual(view["summary"]["security_components_observed"],2)
        self.assertEqual(view["routing"]["ipv4_forwarding"],1)
        self.assertFalse(view["execution_allowed"])
        self.assertTrue(view["sources"]["core"]["fresh"])
        self.assertTrue(view["sources"]["network_defense"]["fresh"])
        output=json.dumps(view)
        for secret in ("SECRET","192.0.2.77","privatepeer","NEVER_EXPORT","foreign_component","unknown-hidden-service"):
            self.assertNotIn(secret,output)

    def test_security_diagnostics_are_fail_closed_and_source_bounded(self):
        self.security_data["sources"] = {
            "network": {"available": True, "stale": False, "detail": "PRIVATE_KEY"},
            "security": {"available": False, "stale": True, "detail": "PASSWORD"},
            "spamhaus_live_state": {"available": False, "stale": False, "detail": "SECRET"},
            "spamhaus": {"available": True, "stale": False},
            "core_live": {"available": True, "stale": False},
        }
        self.security_data["components"]["dns"] = {
            "state": "healthy", "observed": True, "enforcement_verified": False}
        self.security_data["components"]["firewall"] = {
            "state": "unknown", "observed": True, "enforcement_verified": False}
        self.dump()
        view = summarize(self.core, self.security, now=self.now)
        by_name = {item["name"]: item for item in view["security"]}
        self.assertEqual(by_name["ids"]["diagnostic"]["tone"], "warning")
        self.assertEqual(by_name["spamhaus"]["diagnostic"]["tone"], "warning")
        self.assertEqual(by_name["dns"]["diagnostic"]["tone"], "good")
        self.assertEqual(by_name["firewall"]["diagnostic"]["tone"], "warning")
        self.assertEqual(by_name["fail2ban"]["diagnostic"]["tone"], "warning")
        self.assertTrue(any(check["status"] == "unavailable"
                            for check in by_name["spamhaus"]["diagnostic"]["source_checks"]))
        self.assertNotIn("PASSWORD", json.dumps(view))
        self.assertNotIn("PRIVATE_KEY", json.dumps(view))
        self.assertNotIn("SECRET", json.dumps(view))

    def test_positive_state_without_source_proof_is_not_green(self):
        self.security_data["components"]["dns"] = {
            "state": "healthy", "observed": True,
            "metrics": {"recent_events": 2}}
        self.dump()
        view = summarize(self.core, self.security, now=self.now)
        item = next(x for x in view["security"] if x["name"] == "dns")
        self.assertEqual(item["diagnostic"]["tone"], "neutral")
        self.assertEqual(item["diagnostic"]["source_checks"], [])

    def test_stale_sources_cannot_appear_healthy(self):
        older=(self.now-timedelta(minutes=8)).isoformat()
        self.core_data["generated_at"]=older
        self.security_data["generated_at"]=older
        self.dump()
        view=summarize(self.core,self.security,now=self.now)
        self.assertFalse(view["sources"]["core"]["fresh"])
        self.assertFalse(view["sources"]["network_defense"]["fresh"])
        self.assertIsNone(view["summary"]["active_services"])
        self.assertIsNone(view["summary"]["interface_up"])
        self.assertIsNone(view["summary"]["security_components_observed"])
        self.assertTrue(all(x["state"]=="stale" for x in view["services"]))
        self.assertTrue(all(x["state"]=="stale" for x in view["security"]))
        self.assertTrue(all(x["diagnostic"]["tone"]=="warning" for x in view["security"]))
        self.assertTrue(all(x["metrics"]=={} for x in view["security"]))
        self.assertTrue(all(x["up"] is None for x in view["interfaces"]))

    def test_invalid_safety_contract_rejected(self):
        self.core_data["traffic_controls_changed"]=True
        self.security_data["traffic_controls_changed"]=True
        self.dump()
        view=summarize(self.core,self.security,now=self.now)
        self.assertFalse(view["sources"]["core"]["available"])
        self.assertFalse(view["sources"]["network_defense"]["available"])
        self.assertEqual(view["services"],[])
        self.assertEqual(view["security"],[])

    def test_missing_and_symlinked_sources_rejected(self):
        self.core.unlink()
        self.security.unlink()
        self.core.symlink_to(Path(self.temp.name)/"secrets")
        view=summarize(self.core,self.security,now=self.now)
        self.assertFalse(view["sources"]["core"]["available"])
        self.assertFalse(view["sources"]["network_defense"]["available"])

    def test_sanitized_host_metrics_and_invalid_source(self):
        root=Path(self.temp.name)
        load=root/"loadavg";mem=root/"meminfo";up=root/"uptime"
        load.write_text("0.42 0.2 0.1 1/200 500\n")
        mem.write_text("MemTotal: 8192000 kB\nMemAvailable: 4096000 kB\nPrivateValue: DO_NOT_EXPORT\n")
        up.write_text("37200.0 0.0\n")
        result=read_metrics(loadavg=load,meminfo=mem,uptime=up,disk=str(root))
        self.assertTrue(result["available"])
        self.assertEqual(result["load_1m"],0.42)
        self.assertEqual(result["memory_used_percent"],50.0)
        self.assertEqual(result["uptime_seconds"],37200)
        self.assertNotIn("DO_NOT_EXPORT",json.dumps(result))
        load.write_text("bad input")
        self.assertFalse(read_metrics(loadavg=load,meminfo=mem,uptime=up,disk=str(root))["available"])

    def test_api_requires_token_and_preserves_g2_candidate_routes(self):
        root=Path(self.temp.name)
        ui=root/"index.html";ui.write_text("<!doctype html><title>G3 test</title>")
        store=CandidateStore(root/"candidate.sqlite")
        server=G3Server(("127.0.0.1",0),ui,store,TOKEN,self.core,self.security)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        base=f"http://127.0.0.1:{server.server_port}"
        def request(path,token=TOKEN):
            q=urllib.request.Request(base+path,headers={"X-Edge1-Token":token})
            try:
                with urllib.request.urlopen(q,timeout=3) as result:
                    return result.status,json.loads(result.read())
            except urllib.error.HTTPError as err:
                return err.code,json.loads(err.read())
        self.assertEqual(request("/api/operations","invalid")[0],401)
        status,view=request("/api/operations")
        self.assertEqual(status,200)
        self.assertEqual(view["schema"],"edge1-operations-g3.v1")
        self.assertIn("host",view)
        self.assertIn("memory_used_percent",view["host"])
        self.assertEqual(request("/api/state")[0],200)
        self.assertEqual(request("/api/apply")[0],404)


if __name__=="__main__":
    unittest.main()
