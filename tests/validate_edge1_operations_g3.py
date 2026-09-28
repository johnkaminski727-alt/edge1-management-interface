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
from inspect_edge1_security_sources import inspect
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
        self.security_data["sources"] = {}
        self.dump()
        view = summarize(self.core, self.security, now=self.now)
        item = next(x for x in view["security"] if x["name"] == "dns")
        self.assertEqual(item["diagnostic"]["tone"], "neutral")
        self.assertEqual(item["diagnostic"]["source_checks"], [])
        self.assertEqual(item["metrics"], {})

    def test_triage_summary_never_exports_raw_details(self):
        self.security_data["sources"] = {
            "security": {"available": False, "stale": True, "detail": "SECRET_ACCESS"},
            "spamhaus_live_state": {"available": False, "stale": False, "detail": "PRIVATE_ADDRESS"},
            "core_live": {"available": True, "stale": False}}
        self.security_data["components"]["ids"]["detail"] = "PRIVATE_ADDRESS"
        self.dump()
        diagnostic = inspect(self.core, self.security, now=self.now)
        self.assertTrue(diagnostic["read_only"])
        self.assertEqual(diagnostic["schema"], "edge1-security-triage-g3-1.v1")
        self.assertEqual(len(diagnostic["components"]), 7)
        self.assertIn({"name":"security", "state":"unavailable"}, diagnostic["source_checks"])
        self.assertIn({"name":"spamhaus_live_state", "state":"unavailable"}, diagnostic["source_checks"])
        self.assertNotIn("SECRET_ACCESS", json.dumps(diagnostic))
        self.assertNotIn("PRIVATE_ADDRESS", json.dumps(diagnostic))

    def test_unavailable_and_stale_are_separate_source_states(self):
        self.security_data["sources"] = {
            "spamhaus": {"available": False, "stale": True},
            "spamhaus_live_state": {"available": True, "stale": True},
            "core_live": {"available": True, "stale": False},
        }
        self.dump()
        view = summarize(self.core, self.security, now=self.now)
        spamhaus = next(item for item in view["security"] if item["name"] == "spamhaus")
        self.assertEqual(spamhaus["diagnostic"]["tone"], "warning")
        self.assertIn({"name": "spamhaus", "status": "unavailable"},
                      spamhaus["diagnostic"]["source_checks"])
        self.assertIn({"name": "spamhaus_live_state", "status": "stale"},
                      spamhaus["diagnostic"]["source_checks"])
        self.assertEqual(spamhaus["metrics"], {})
        triage = inspect(self.core, self.security, now=self.now)
        self.assertIn({"name": "spamhaus", "state": "unavailable"}, triage["source_checks"])
        self.assertIn({"name": "spamhaus_live_state", "state": "stale"}, triage["source_checks"])

    def test_current_source_adapter_never_proves_component_health(self):
        self.security_data["sources"] = {
            "nftables_live_state": {"available": True, "stale": False,
                                     "file": "/private/network", "detail": "PRIVATE"},
            "fail2ban_live_state": {"available": True, "stale": False,
                                     "detail": "SECRET"},
        }
        self.security_data["components"]["firewall"] = {
            "state": "unknown", "observed": True,
            "enforcement_verified": False, "metrics": {"private": "SECRET"}}
        self.security_data["components"]["fail2ban"] = {
            "state": "unknown", "observed": True,
            "enforcement_verified": False}
        self.dump()
        result = summarize(self.core, self.security, now=self.now)
        by_name = {x["name"]: x for x in result["security"]}
        for key in ("firewall", "fail2ban"):
            entry = by_name[key]
            self.assertEqual(entry["state"], "unknown")
            self.assertEqual(entry["source_adapter"]["state"], "current")
            self.assertEqual(entry["diagnostic"]["tone"], "warning")
            self.assertFalse(entry["enforcement_verified"])
        text = json.dumps(result)
        self.assertNotIn("SECRET", text)
        self.assertNotIn("/private/network", text)

    def test_source_adapters_missing_stale_and_unavailable_fail_closed(self):
        self.security_data["sources"] = {
            "nftables_live_state": {"available": False, "stale": True},
            "fail2ban_live_state": {"available": True, "stale": True}}
        self.dump()
        result = summarize(self.core, self.security, now=self.now)
        entries = {x["name"]: x for x in result["security"]}
        self.assertEqual(entries["firewall"]["source_adapter"]["state"], "unavailable")
        self.assertEqual(entries["fail2ban"]["source_adapter"]["state"], "stale")
        self.security_data["sources"] = {}
        self.dump()
        missing = summarize(self.core, self.security, now=self.now)
        entries = {x["name"]: x for x in missing["security"]}
        self.assertEqual(entries["firewall"]["source_adapter"]["state"], "unverified")
        self.assertEqual(entries["fail2ban"]["source_adapter"]["state"], "unverified")
        self.security_data["generated_at"] = (self.now-timedelta(minutes=8)).isoformat()
        self.security_data["sources"] = {
            "nftables_live_state": {"available": True, "stale": False}}
        self.dump()
        old = summarize(self.core, self.security, now=self.now)
        item = next(x for x in old["security"] if x["name"] == "firewall")
        self.assertEqual(item["source_adapter"]["state"], "stale")

    def test_current_firewall_and_fail2ban_detail_counts_are_bounded(self):
        self.security_data["sources"] = {
            "nftables_live_state": {"available": True, "stale": False},
            "fail2ban_live_state": {"available": True, "stale": False},
            "core_live": {"available": True, "stale": False}}
        self.security_data["components"]["firewall"] = {
            "state": "unknown", "observed": True, "enforcement_verified": False,
            "metrics": {
                "tables": 4, "chains": 9, "rules": 31, "counter_packets": 15,
                "counter_bytes": 8192, "set_elements": 12,
                "families": {"ip": 2, "inet": 2, "hidden": "SECRET"},
                "hooks": {"input": 1, "forward": 1},
                "policies": {"drop": 1},
                "verdicts": {"drop": 3},
                "raw_ruleset": "PRIVATE_FIREWALL",
                "address": "192.0.2.40",
            }}
        self.security_data["components"]["fail2ban"] = {
            "state": "unknown", "observed": True, "enforcement_verified": False,
            "metrics": {
                "service_active": True, "socket_reachable": True,
                "declared_jails": 3, "observed_jails": 3,
                "currently_banned": 4, "total_banned": 91,
                "jail_names": ["PRIVATE_JAIL"], "banned_addresses": "SECRET",
            }}
        self.dump()
        view = summarize(self.core, self.security, now=self.now)
        by_name = {x["name"]: x for x in view["security"]}
        fw = by_name["firewall"]
        f2b = by_name["fail2ban"]
        self.assertEqual(fw["detail_metrics"]["counts"]["rules"], 31)
        self.assertEqual(fw["detail_metrics"]["groups"]["families"]["inet"], 2)
        self.assertEqual(f2b["detail_metrics"]["counts"]["currently_banned"], 4)
        self.assertTrue(f2b["detail_metrics"]["flags"]["socket_reachable"])
        self.assertEqual(fw["state"], "unknown")
        self.assertEqual(fw["diagnostic"]["tone"], "warning")
        self.assertFalse(fw["enforcement_verified"])
        for secret in ("PRIVATE_FIREWALL", "PRIVATE_JAIL", "SECRET",
                       "192.0.2.40", "hidden"):
            self.assertNotIn(secret, json.dumps(view))

    def test_detail_panels_fail_closed_on_source_staleness_and_invalid_counts(self):
        self.security_data["sources"] = {
            "nftables_live_state": {"available": True, "stale": True},
            "fail2ban_live_state": {"available": False, "stale": False}}
        self.security_data["components"]["firewall"] = {
            "state": "unknown", "observed": True,
            "metrics": {"rules": 37}}
        self.security_data["components"]["fail2ban"] = {
            "state": "unknown", "observed": True,
            "metrics": {"currently_banned": 4}}
        self.dump()
        view = summarize(self.core, self.security, now=self.now)
        entries = {x["name"]: x for x in view["security"]}
        self.assertFalse(entries["firewall"]["detail_metrics"]["available"])
        self.assertEqual(entries["firewall"]["detail_metrics"]["counts"], {})
        self.assertFalse(entries["fail2ban"]["detail_metrics"]["available"])
        self.assertEqual(entries["fail2ban"]["detail_metrics"]["counts"], {})
        self.security_data["sources"]["nftables_live_state"]["stale"] = False
        self.security_data["components"]["firewall"]["metrics"] = {
            "tables": True, "rules": -1, "counter_bytes": 10**20}
        self.dump()
        invalid = summarize(self.core, self.security, now=self.now)
        fw = next(x for x in invalid["security"] if x["name"] == "firewall")
        self.assertFalse(fw["detail_metrics"]["available"])
        self.assertIsNone(fw["detail_metrics"]["counts"]["tables"])
        self.assertIsNone(fw["detail_metrics"]["counts"]["rules"])

    def test_g34_toolbox_is_read_only_and_reuses_authenticated_endpoints(self):
        page = (Path(__file__).resolve().parents[1] /
                "src/web/operations-center/operations-workspace-g3.html").read_text()
        for required in ('id="toolbox-sources"', 'id="toolbox-security"',
                         'id="toolbox-audit"', 'id="toolbox-refresh"',
                         'function renderToolbox()', 'renderToolbox();',
                         '"/api/operations"', '"/api/audit"',
                         'No shell execution, Apply'):
            self.assertIn(required, page)
        self.assertNotIn('"/api/apply"', page)
        self.assertNotIn("localStorage", page)
        self.assertNotIn("sessionStorage", page)
        self.assertNotIn('innerHTML=', page)

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
