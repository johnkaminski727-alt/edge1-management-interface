import importlib.util
import json
import pathlib
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).parents[1]
CONTROLLER_SCRIPT = ROOT / 'server/edge1_release_controller.py'
INSTALLER_SCRIPT = ROOT / 'deploy/install_edge1_release_controller.py'
LIVE_SHELL = ROOT / 'tools/mcp/edge1-live-shell/src/index.js'
NAVIGATION = ROOT / 'config/edge1_operator/navigation_registry.json'

controller_spec = importlib.util.spec_from_file_location('edge1_release_controller', CONTROLLER_SCRIPT)
rc = importlib.util.module_from_spec(controller_spec)
assert controller_spec.loader is not None
controller_spec.loader.exec_module(rc)

installer_spec = importlib.util.spec_from_file_location('edge1_release_installer', INSTALLER_SCRIPT)
installer = importlib.util.module_from_spec(installer_spec)
assert installer_spec.loader is not None
installer_spec.loader.exec_module(installer)


class ReleaseControllerTests(unittest.TestCase):
    def make_controller(self, root: pathlib.Path) -> rc.ReleaseController:
        source = root / 'source'
        runtime = root / 'runtime'
        state = root / 'state'
        backups = root / 'backups'
        web = root / 'web'
        for path in (source, runtime / 'releases', state, backups, web):
            path.mkdir(parents=True, exist_ok=True)
        return rc.ReleaseController(
            source_root=source,
            runtime_root=runtime,
            state_root=state,
            backup_root=backups,
            web_root=web,
            runner=lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, '', ''),
            health_reader=lambda: {
                'status': 'ok',
                'repository_root_stable': True,
                'mutations_enabled': False,
            },
            sleep=lambda _seconds: None,
        )

    def test_target_must_be_exact_lowercase_sha(self):
        good = 'a' * 40
        self.assertEqual(rc.valid_sha(good), good)
        for bad in ('main', 'a' * 39, 'A' * 40, ('a' * 40) + ';id', '../' + ('a' * 40)):
            with self.subTest(bad=bad), self.assertRaises(rc.ReleaseError):
                rc.valid_sha(bad)

    def test_runtime_pointers_are_bounded_to_commit_named_releases(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            c = self.make_controller(root)
            target = 'b' * 40
            release = c.releases_root / target
            release.mkdir()
            c._replace_link(c.current_link, release)
            with mock.patch.object(c, 'release_head', return_value=target):
                self.assertEqual(c.current_sha(), target)
            outside = root / ('c' * 40)
            outside.mkdir()
            with self.assertRaises(rc.ReleaseError):
                c._replace_link(c.current_link, outside)

    def test_status_fails_closed_on_unstable_or_mutating_operations_api(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            c = self.make_controller(root)
            target = 'd' * 40
            with mock.patch.object(c, 'source_snapshot', return_value={
                'available': True, 'branch': 'main', 'head': target, 'dirty': False, 'origin_main': target,
            }), mock.patch.object(c, 'current_sha', return_value=target), mock.patch.object(c, 'previous_sha', return_value=None), mock.patch.object(c, '_service_active', return_value=True), mock.patch.object(c, '_listener_hosts', return_value=['127.0.0.1']):
                c.health_reader = lambda: {'status': 'ok', 'repository_root_stable': True, 'mutations_enabled': False}
                healthy = c.status()
                self.assertTrue(healthy['healthy'])
                self.assertFalse(healthy['action_required'])
                self.assertFalse(healthy['automatic_promotion'])

                c.health_reader = lambda: {'status': 'ok', 'repository_root_stable': False, 'mutations_enabled': False}
                unstable = c.status()
                self.assertFalse(unstable['healthy'])
                self.assertTrue(unstable['action_required'])

                c.health_reader = lambda: {'status': 'ok', 'repository_root_stable': True, 'mutations_enabled': True}
                mutating = c.status()
                self.assertFalse(mutating['healthy'])

    def test_postflight_rejects_non_loopback_listener(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            c = self.make_controller(root)
            target = 'e' * 40
            with mock.patch.object(c, 'current_sha', return_value=target), mock.patch.object(c, '_service_active', return_value=True), mock.patch.object(c, '_listener_hosts', side_effect=lambda port: ['0.0.0.0'] if port == 8097 else ['127.0.0.1']):
                with self.assertRaises(rc.ReleaseError):
                    c._postflight_once(target)

    def test_failed_promotion_attempts_exact_automatic_rollback(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            c = self.make_controller(root)
            old = '1' * 40
            target = '2' * 40
            for sha in (old, target):
                release = c.releases_root / sha
                (release / 'deploy/edge1-release-controller').mkdir(parents=True)
                (release / 'server').mkdir(parents=True)
                (release / 'deploy/edge1-release-controller/edge1-operations-api-release.conf').write_text('[Service]\n')
                (release / 'deploy/edge1-release-controller/edge1-operator-mcp-release.conf').write_text('[Service]\n')
                (release / 'server/edge1_release_controller.py').write_text('# controller\n')

            operations_dropin = root / 'etc/ops.conf'
            operator_dropin = root / 'etc/operator.conf'
            pointer_calls = []
            wait_calls = []

            def fake_wait(sha, *args, **kwargs):
                wait_calls.append(sha)
                if sha == target:
                    raise rc.ReleaseError('synthetic postflight failure')
                return {'target': sha}

            with mock.patch.object(rc.os, 'geteuid', return_value=0), \
                 mock.patch.object(rc, 'OPERATIONS_DROPIN', operations_dropin), \
                 mock.patch.object(rc, 'OPERATOR_DROPIN', operator_dropin), \
                 mock.patch.object(c, 'require_target', return_value=(target, {'head': target})), \
                 mock.patch.object(c, 'prepare', return_value={'status': 'prepared'}), \
                 mock.patch.object(c, 'current_sha', return_value=old), \
                 mock.patch.object(c, 'previous_sha', return_value=None), \
                 mock.patch.object(c, '_replace_link', side_effect=lambda link, release: pointer_calls.append((link.name, release.name if release else None))), \
                 mock.patch.object(c, '_install_dropin', return_value='a' * 64), \
                 mock.patch.object(c, '_restart_services'), \
                 mock.patch.object(c, 'wait_postflight', side_effect=fake_wait):
                with self.assertRaises(rc.ReleaseError) as caught:
                    c.promote(target)

            self.assertIn('automatic rollback succeeded', str(caught.exception))
            self.assertEqual(wait_calls, [target, old])
            self.assertIn(('current', target), pointer_calls)
            self.assertIn(('current', old), pointer_calls)
            state = json.loads(c.state_file.read_text())
            self.assertEqual(state['status'], 'failed')
            self.assertTrue(state['automatic_rollback_succeeded'])

    def test_installer_rejects_credential_bearing_http_remote(self):
        self.assertTrue(installer.safe_remote_url('git@github.com:example/repo.git'))
        self.assertTrue(installer.safe_remote_url('https://github.com/example/repo.git'))
        self.assertTrue(installer.safe_remote_url('/srv/git/repo.git'))
        self.assertFalse(installer.safe_remote_url('https://user:secret@example.invalid/repo.git'))
        self.assertFalse(installer.safe_remote_url('ftp://example.invalid/repo.git'))

    def test_live_shell_exposes_named_release_actions_only(self):
        text = LIVE_SHELL.read_text(encoding='utf-8')
        self.assertIn("server.registerTool('edge1_release'", text)
        self.assertIn("z.enum(['status', 'reconcile', 'rollback_last'])", text)
        self.assertIn('EDGE1_RELEASE_TARGET_SHA', text)
        self.assertIn("/usr/local/libexec/edge1-release-controller", text)
        self.assertIn("git -C \"$repo\" worktree add --detach", text)
        self.assertIn('EDGE1_ENABLE_RAW_SHELL', text)
        self.assertNotIn("inputSchema: z.object({ command: z.string().min(1).max(4000) })\n  }, async ({ command }) => {\n    return resultPayload('release'", text)

    def test_release_manager_ui_and_registry_stay_staged_until_live_acceptance(self):
        page = (ROOT / 'src/web/release-manager/index.html').read_text(encoding='utf-8')
        self.assertIn('Release Manager', page)
        self.assertIn('Automatic promotion: OFF', page)
        self.assertIn('./status.json', page)
        registry = json.loads(NAVIGATION.read_text(encoding='utf-8'))
        module = next(item for item in registry['modules'] if item['id'] == 'release-manager')
        self.assertIsNone(module['browser_route'])
        self.assertEqual(module['availability'], 'staged_disabled')
        self.assertFalse(module['palette'])
        self.assertEqual(module['candidate_route'], '/edge1-status/release-manager/')

    def test_service_dropins_pin_both_control_planes_to_one_current_pointer(self):
        ops = (ROOT / 'deploy/edge1-release-controller/edge1-operations-api-release.conf').read_text()
        operator = (ROOT / 'deploy/edge1-release-controller/edge1-operator-mcp-release.conf').read_text()
        self.assertIn('WorkingDirectory=/opt/edge1-runtime/current', ops)
        self.assertIn('Environment=EDGE1_OPS_ROOT=/opt/edge1-runtime/current', ops)
        self.assertIn('/opt/edge1-runtime/current/server/edge1_operations_api.py', ops)
        self.assertIn('WorkingDirectory=/opt/edge1-runtime/current', operator)
        self.assertIn('server.edge1_operator_http', operator)


if __name__ == '__main__':
    unittest.main()
