"""Execute the SAM workflow's actual admission shell without credentials/network."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github/workflows/capturebrief-sam-current-access.yml'
SHA = 'a' * 40
OTHER = 'b' * 40
BEFORE = 'Verify immutable main observation source'
AFTER = 'Revalidate current main after observation'


def step(text, name):
    marker = '      - name: ' + name + '\n'
    if marker not in text:
        raise AssertionError('Missing workflow step: ' + name)
    tail = text.split(marker, 1)[1]
    return tail.split('\n      - ', 1)[0]


def shell(text, name):
    body = step(text, name)
    match = re.search(r'^        run: (.+)$', body, re.M)
    if not match:
        raise AssertionError('Missing run body: ' + name)
    if match[1] != '|':
        return match[1]
    return '\n'.join(line[10:] for line in body[match.end():].splitlines()
                     if line.startswith('          '))


@unittest.skipUnless(os.name == "posix" and shutil.which("bash") and shutil.which("timeout"),
                     "The credentialed workflow runs on Ubuntu and requires POSIX shell tooling")
class SamRuntimeSourcePolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding='utf-8')

    def run_guard(self, name=BEFORE, **changes):
        with tempfile.TemporaryDirectory() as directory:
            fake_git = Path(directory) / 'git'
            fake_git.write_text(
                '#!/bin/sh\n'
                'case "$1" in\n'
                ' rev-parse) printf "%s\\n" "$FAKE_HEAD" ;;\n'
                ' ls-remote) printf "%s\\n" "$*" >> "$FAKE_CALLS"; '
                'printf "%s\\n" "$FAKE_REMOTE"; exit "$FAKE_EXIT" ;;\n'
                ' *) exit 90 ;;\nesac\n', encoding='utf-8')
            fake_git.chmod(0o700)
            env = {'PATH': directory + os.pathsep + os.defpath,
                   'GITHUB_REPOSITORY': 'P00NSMASHER/capturebrief',
                   'GITHUB_REF': 'refs/heads/main', 'GITHUB_EVENT_NAME': 'push',
                   'GITHUB_SHA': SHA, 'EXPECTED_SHA': SHA, 'FAKE_HEAD': SHA,
                   'FAKE_REMOTE': SHA + '\trefs/heads/main', 'FAKE_EXIT': '0',
                   'FAKE_CALLS': str(Path(directory) / 'calls')}
            env.update(changes)
            result = subprocess.run(['bash', '-c', shell(self.text, name)],
                                    env=env, capture_output=True, text=True, timeout=5)
            calls = Path(env['FAKE_CALLS'])
            return result, calls.read_text() if calls.exists() else ''

    def test_exact_current_source_passes_push_and_dispatch(self):
        for event in ('push', 'workflow_dispatch'):
            result, _ = self.run_guard(GITHUB_EVENT_NAME=event)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_stale_rerun_is_rejected(self):
        result, _ = self.run_guard(FAKE_REMOTE=OTHER + '\trefs/heads/main')
        self.assertNotEqual(result.returncode, 0, 'Stale main must not access SAM credentials')

    def test_wrong_checkout_is_rejected(self):
        result, _ = self.run_guard(FAKE_HEAD=OTHER)
        self.assertNotEqual(result.returncode, 0)

    def test_mismatched_event_sha_is_rejected(self):
        result, _ = self.run_guard(GITHUB_SHA=OTHER)
        self.assertNotEqual(result.returncode, 0)

    def test_untrusted_context_rejected_before_remote_access(self):
        for changes in ({'GITHUB_REPOSITORY': 'other/capturebrief'},
                        {'GITHUB_REF': 'refs/heads/candidate'},
                        {'GITHUB_EVENT_NAME': 'pull_request'},
                        {'GITHUB_EVENT_NAME': 'pull_request_target'},
                        {'GITHUB_EVENT_NAME': 'workflow_run'}):
            with self.subTest(changes=changes):
                result, calls = self.run_guard(**changes)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(calls, '')

    def test_remote_error_empty_ambiguous_and_wrong_ref_rejected(self):
        for changes in ({'FAKE_EXIT': '1'}, {'FAKE_REMOTE': ''},
                        {'FAKE_REMOTE': SHA + '\trefs/heads/other'},
                        {'FAKE_REMOTE': SHA + '\trefs/heads/main\n' + OTHER + '\trefs/heads/main'}):
            with self.subTest(changes=changes):
                result, _ = self.run_guard(**changes)
                self.assertNotEqual(result.returncode, 0)

    def test_lookup_is_bounded_and_uses_fixed_public_repository(self):
        result, calls = self.run_guard()
        self.assertEqual(result.returncode, 0)
        self.assertIn('timeout 20s git ls-remote', shell(self.text, BEFORE))
        self.assertIn('https://github.com/P00NSMASHER/capturebrief.git refs/heads/main', calls)
        self.assertNotIn('SAM_API_KEY', step(self.text, BEFORE))

    def test_post_probe_check_rejects_main_advance(self):
        result, _ = self.run_guard(AFTER, FAKE_REMOTE=OTHER + '\trefs/heads/main')
        self.assertNotEqual(result.returncode, 0)
        result, _ = self.run_guard(AFTER)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(shell(self.text, BEFORE), shell(self.text, AFTER))

    def test_probe_and_publication_are_both_admission_gated(self):
        before = step(self.text, BEFORE)
        after = step(self.text, AFTER)
        self.assertIn('id: source_before', before)
        self.assertIn('id: source_after', after)
        self.assertLess(self.text.index(BEFORE), self.text.index('SAM_API_KEY:'))
        self.assertLess(self.text.index('SAM_API_KEY:'), self.text.index(AFTER))
        for name in ('Report only the bounded observation outcome', 'Retain only the redacted access receipt'):
            body = step(self.text, name)
            self.assertIn("steps.source_before.outcome == 'success'", body)
            self.assertIn("steps.source_after.outcome == 'success'", body)

    def test_offline_contract_runs_guard_tests_and_tracks_their_changes(self):
        self.assertIn('tests.test_sam_runtime_source_policy', self.text)
        self.assertEqual(self.text.count('- tests/test_sam_runtime_source_policy.py'), 2)
        self.assertIn('${{ github.run_attempt }}', self.text)


if __name__ == '__main__':
    unittest.main()
