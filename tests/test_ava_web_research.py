import json
import sys
import unittest
from pathlib import Path
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server import ava_web_research as web
import test_ava_readonly_gateway as fixtures
from server import ava_agent_controller as agent

class AvaWebResearchTests(unittest.TestCase):
    def test_only_safe_cited_urls_become_evidence(self):
        payload={"output":[{"type":"message","content":[{"type":"output_text","text":"Cited evidence",
            "annotations":[{"type":"url_citation","url":u,"title":"source"} for u in
                           ["https://docs.python.org/3/","javascript:alert(1)","https://127.0.0.1/x","https://x.internal/y","https://user:pass@example.org/","https://docs.python.org/3/"]]}]}]}
        evidence=web.extract_evidence(payload)
        self.assertEqual(len(evidence["sources"]),1)
        self.assertEqual(evidence["sources"][0]["locator"],"https://docs.python.org/3/")

    def test_no_citation_is_not_verified_web_evidence(self):
        with self.assertRaises(RuntimeError):
            web.extract_evidence({"output":[]})

    def test_research_sends_only_public_query(self):
        response=mock.MagicMock()
        response.__enter__.return_value.read.return_value=json.dumps({"output":[{"type":"message","content":[{"type":"output_text","text":"Evidence","annotations":[{"type":"url_citation","url":"https://example.org/","title":"example"}]}]}]}).encode()
        with mock.patch.object(web.urllib.request,"urlopen",return_value=response) as call:
            web.research("Public weather facts",api_key="test",model="existing-model",contains_secret=lambda q:False)
        payload=json.loads(call.call_args.args[0].data)
        self.assertEqual(payload["input"],"Public weather facts")
        self.assertFalse(payload["store"])
        self.assertEqual(payload["tools"][0]["type"],"web_search")

    def test_scope_gate_precedes_web_execution(self):
        gateway=fixtures.AvaReadonlyGatewayTests().load()
        with mock.patch.object(gateway,"public_web_research") as search:
            status,result=gateway.process_chat({"request_id":"web-test","message":"hello","include_web":True,"web_query":"public","user":{"scopes":[]}})
            self.assertEqual(status,403)
            search.assert_not_called()

    def test_private_message_never_becomes_public_query(self):
        gateway=fixtures.AvaReadonlyGatewayTests().load()
        with mock.patch.object(gateway,"public_web_research",return_value={"text":"public","sources":[]}) as search, mock.patch.object(gateway,"_call_openai",return_value=("answer",[])):
            status,_=gateway.process_chat({"request_id":"web-test","message":"PRIVATE CONTEXT","include_web":True,"web_query":"public query","user":{"scopes":["web:search"]}})
        self.assertEqual(status,200)
        self.assertEqual(search.call_args.args[0],"public query")

    def test_controller_can_only_narrow_web_access(self):
        payload={"request_id":"web-test","message":"private task","agent_auto_route":True,"include_web":False,"web_query":"unused","user":{"scopes":["chat:general","web:search"]}}
        plan=agent.build_plan(payload)
        prepared=agent.prepare_gateway_request(payload,plan)
        self.assertFalse(prepared["include_web"])
        self.assertNotIn("web:search",prepared["user"]["scopes"])
        self.assertNotIn("web_query",prepared)

    def test_routing_uses_the_original_message_not_private_context(self):
        payload={"request_id":"routing-test","routing_message":"Hello","message":"SERVER CONTEXT: search the network service health","agent_auto_route":True,"include_library":True,"include_edge1_status":True,"library_collections":["operations"],"user":{"scopes":["chat:general","library:search","edge1:status:read"]}}
        plan=agent.build_plan(payload)
        self.assertFalse(plan.source_flags["include_library"])
        self.assertFalse(plan.source_flags["include_edge1_status"])

    def test_explicit_public_query_remains_selected(self):
        payload={"request_id":"public-query","routing_message":"Summarize the findings","agent_auto_route":True,"include_web":True,"web_query":"Python backup documentation","user":{"scopes":["chat:general","web:search"]}}
        plan=agent.build_plan(payload)
        prepared=agent.prepare_gateway_request(payload,plan)
        self.assertTrue(prepared["include_web"])
        self.assertIn("web:search",prepared["user"]["scopes"])
