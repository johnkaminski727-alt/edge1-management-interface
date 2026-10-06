import json, tempfile, unittest
from pathlib import Path
from server.edge1_navigation_registry import connect, import_registry
from server.edge1_navigation_admin import update_module, list_audit
class T(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory(); self.db=Path(self.t.name)/'n.sqlite'; self.out=Path(self.t.name)/'n.json'
  reg={'contract':'wwcx.edge1-operator-navigation.v1','schema_version':1,'safety':{'navigation_grants_authorization':False,'generic_execution_authorized':False,'production_traffic_authorized':False,'mutations_enabled':False,'unknown_status_is_healthy':False},'modules':[{'id':'mail-room','label':'Mail Room','section':'Email','sort_order':1,'browser_route':'/edge1-ops/mail-room/','candidate_route':None,'runtime_route':'/edge1-ops/mail-room/','availability':'accepted_live','authorization':'authenticated_admin','description':'x','palette':True,'toolbox':True,'evidence_status':'live','menu_visibility':'primary','dashboard_visibility':True,'enabled':True,'theme':'dark'}]}
  with connect(self.db) as c: import_registry(c,reg,replace=True)
 def tearDown(self): self.t.cleanup()
 def test_update_audit_export(self):
  r=update_module('mail-room',{'label':'Mail','sort_order':9,'enabled':False},actor='admin',request_id='r1',db=self.db,output=self.out)
  self.assertEqual(r['changed_fields'],['enabled','label','sort_order'])
  self.assertEqual(json.loads(self.out.read_text())['modules'],[])
  self.assertEqual(list_audit(self.db)[0]['module_id'],'mail-room')
 def test_route_requires_confirmation(self):
  with self.assertRaisesRegex(ValueError,'confirmation'): update_module('mail-room',{'browser_route':'/new/'},actor='admin',request_id='r2',db=self.db,output=self.out)
  r=update_module('mail-room',{'browser_route':'/new/','confirm_route_change':True},actor='admin',request_id='r3',db=self.db,output=self.out)
  self.assertEqual(r['module']['browser_route'],'/new/')
 def test_rejects_api_route(self):
  with self.assertRaisesRegex(ValueError,'implementation'): update_module('mail-room',{'browser_route':'/api/nope/','confirm_route_change':True},actor='admin',request_id='r4',db=self.db,output=self.out)
if __name__=='__main__': unittest.main()
