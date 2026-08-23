from __future__ import annotations
import time
import unittest
from unittest.mock import patch
from server import ava_admin_functions_sync as sync


class AvaAdminFunctionsSyncTests(unittest.TestCase):
    def test_reconcile_enables_changed_gate(self):
        expiry = int(time.time()) + 900
        calls = []
        def fake(capability, arguments=None, confirmed=False):
            calls.append((capability, arguments, confirmed))
            if capability == 'shell.gate.status':
                return {'status':'completed','result':{'host':'edge1','enabled':False,'reason':'not_enabled'}}
            return {'status':'completed','result':{'host':'edge1','enabled':True,'expires_at_unix':expiry,'generation':4}}
        with patch.object(sync, 'broker_call', side_effect=fake):
            result = sync.reconcile_control('edge1_shell', {'desired_enabled':True,'desired_expires_at':expiry,'generation':4,'requested_by':'Admin'})
        self.assertTrue(result['observed_enabled'])
        self.assertEqual(calls[-1][0], 'shell.gate.set')
        self.assertTrue(calls[-1][2])

    def test_reconcile_does_not_rewrite_matching_gate(self):
        expiry = int(time.time()) + 900
        with patch.object(sync, 'broker_call', return_value={'status':'completed','result':{'host':'business159','enabled':True,'expires_at_unix':expiry,'generation':2}}) as call:
            result = sync.reconcile_control('business159_shell', {'desired_enabled':True,'desired_expires_at':expiry,'generation':2,'requested_by':'Admin'})
        self.assertTrue(result['observed_enabled'])
        self.assertEqual(call.call_count, 1)

    def test_expired_desired_state_closes_gate(self):
        calls=[]
        def fake(capability, arguments=None, confirmed=False):
            calls.append((capability,arguments,confirmed))
            if capability == 'shell.gate.status':
                return {'status':'completed','result':{'host':'edge1','enabled':True,'expires_at_unix':int(time.time())+60,'generation':1}}
            return {'status':'completed','result':{'host':'edge1','enabled':False,'reason':'not_enabled'}}
        with patch.object(sync,'broker_call',side_effect=fake):
            result=sync.reconcile_control('edge1_shell',{'desired_enabled':True,'desired_expires_at':int(time.time())-1,'generation':2,'requested_by':'Admin'})
        self.assertFalse(result['observed_enabled'])
        self.assertFalse(calls[-1][1]['enabled'])


if __name__ == '__main__':
    unittest.main()
