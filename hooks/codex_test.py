import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import codex

ROOT = Path(codex.ROOT)


class HookTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, {"PLUGIN_DATA": self.directory.name}).start()
        self.where = patch.object(codex, "where", return_value=(5, "elsewhere")).start()
        self.real_launch = codex.launch
        self.launch = patch.object(codex, "launch").start()
        self.path = Path(codex.state_path("session-1"))
        self.event("UserPromptSubmit")

    def event(self, name, **fields):
        codex.handle({"session_id": "session-1", "turn_id": "turn-1",
                      "hook_event_name": name, **fields})

    def notification(self):
        _, _, sound, repeat, gain, away = self.launch.call_args.args
        return sound, repeat, gain, away

    def test_main_completion_and_duplicate(self):
        self.event("Stop")
        self.assertEqual(self.notification(), ("Glass", 3, "0.4", False))
        self.event("Stop")
        self.assertEqual(self.launch.call_count, 1)

    def test_foreground_quick_turn_is_silent_and_cancels_reminder(self):
        self.where.return_value = (600, "away")
        self.event("PermissionRequest", tool_name="Bash")
        previous = self.launch.call_args.args[1]
        self.where.return_value = (5, "watching")
        with patch.object(codex.time, "time", return_value=100):
            self.event("UserPromptSubmit", turn_id="turn-2")
        with patch.object(codex.time, "time", return_value=109.999):
            self.event("Stop", turn_id="turn-2")
        self.assertEqual(self.launch.call_count, 1)
        self.assertFalse(codex.active(self.path, previous))

    def test_foreground_long_turn_rings_once_without_ducking(self):
        self.where.return_value = (5, "watching")
        with patch.object(codex.time, "time", return_value=100):
            self.event("UserPromptSubmit")
        with patch.object(codex.time, "time", return_value=110):
            self.event("Stop")
        self.assertEqual(self.notification(), ("Glass", 1, "1", False))

    def test_away_completion_has_stronger_ducking_and_reminders(self):
        self.where.return_value = (600, "away")
        self.event("Stop")
        self.assertEqual(self.notification(), ("Glass", 3, "0.2", True))

    def test_question_and_permission_do_not_ring_twice(self):
        for tool in ["request_user_input", "request_user_input_async", "mcp__app__AskUserQuestion"]:
            with self.subTest(tool=tool):
                self.launch.reset_mock()
                self.event("PreToolUse", tool_name=tool)
                self.assertEqual(self.notification(), ("Ping", 1, "0.4", False))
                self.event("PermissionRequest", tool_name=tool)
                self.assertEqual(self.launch.call_count, 1)

    def test_permission_rings_even_during_a_quick_foreground_turn(self):
        self.where.return_value = (5, "watching")
        self.event("PermissionRequest", tool_name="Bash")
        self.assertEqual(self.notification(), ("Ping", 1, "1", False))

    def test_tool_completion_stops_waiting_reminders(self):
        self.event("PermissionRequest", tool_name="Bash")
        token = self.launch.call_args.args[1]
        self.event("PostToolUse", tool_name="apply_patch")
        self.assertTrue(codex.active(self.path, token))
        self.event("PostToolUse", tool_name="Bash")
        self.assertFalse(codex.active(self.path, token))

    def test_async_question_return_does_not_mean_the_person_answered(self):
        self.event("PreToolUse", tool_name="request_user_input_async")
        token = self.launch.call_args.args[1]
        self.event("PostToolUse", tool_name="request_user_input_async")
        self.assertTrue(codex.active(self.path, token))
        self.event("UserPromptSubmit", turn_id="turn-2")
        self.assertFalse(codex.active(self.path, token))

    def test_subagent_completion_and_regular_tools_stay_silent(self):
        self.event("SubagentStop", agent_id="child")
        self.event("Stop", agent_id="child")
        self.event("PreToolUse", tool_name="Bash")
        self.launch.assert_not_called()

    def test_interrupt_cancels_reminders_and_stays_silent(self):
        self.event("PermissionRequest", tool_name="Bash")
        token = self.launch.call_args.args[1]
        self.event("Interrupt")
        self.assertFalse(codex.active(self.path, token))
        self.event("Stop")
        self.assertEqual(self.launch.call_count, 1)

    def test_new_turn_cancels_reminders_and_ignores_old_events(self):
        self.event("Stop")
        token = self.launch.call_args.args[1]
        self.event("UserPromptSubmit", turn_id="turn-2")
        self.assertFalse(codex.active(self.path, token))
        self.event("PermissionRequest", turn_id="turn-2", tool_name="Bash")
        current = self.launch.call_args.args[1]
        for name in ["Stop", "Interrupt", "PostToolUse", "PermissionRequest"]:
            self.event(name, tool_name="Bash")
        self.assertTrue(codex.active(self.path, current))
        self.assertEqual(self.launch.call_count, 2)

    def test_session_end_cancels_reminders_and_cleans_state(self):
        self.event("Stop")
        token = self.launch.call_args.args[1]
        self.event("SessionEnd")
        self.assertFalse(self.path.exists())
        self.assertFalse(codex.active(self.path, token))

    def test_sessions_are_independent_and_session_ids_cannot_escape_directory(self):
        self.event("Stop")
        token = self.launch.call_args.args[1]
        self.event("UserPromptSubmit", session_id="../../other-session")
        self.assertTrue(codex.active(self.path, token))
        self.assertEqual(Path(codex.state_path("../../other-session")).parent, self.path.parent)

    def test_waiting_directory_exists_only_while_a_session_waits_on_a_tool(self):
        waiting = self.path.parent / "waiting"
        self.event("PermissionRequest", tool_name="Bash")
        self.event("UserPromptSubmit", session_id="session-2")
        self.event("PermissionRequest", session_id="session-2", tool_name="Bash")
        self.event("PostToolUse", tool_name="Bash")
        self.assertTrue(waiting.is_dir())
        self.event("Stop", session_id="session-2")
        self.assertFalse(waiting.exists())
        self.event("PreToolUse", tool_name="request_user_input_async")
        self.assertFalse(waiting.exists())
        for name in ["UserPromptSubmit", "Interrupt", "SessionEnd"]:
            with self.subTest(name=name):
                self.event("UserPromptSubmit")
                self.event("PermissionRequest", tool_name="Bash")
                self.assertTrue(waiting.is_dir())
                self.event(name)
                self.assertFalse(waiting.exists())

    def test_dead_sessions_leave_nothing_behind_for_long(self):
        self.event("PermissionRequest", tool_name="Bash")
        marker = self.path.parent / "waiting" / self.path.name
        old = time.time() - 8 * 24 * 3600
        os.utime(marker, (old, old))
        os.utime(self.path, (old, old))
        self.event("UserPromptSubmit", session_id="session-2")
        self.event("PostToolUse", session_id="session-2", tool_name="Bash")
        self.assertFalse(marker.exists())
        self.event("SessionEnd", session_id="session-2")
        self.assertEqual(sorted(os.listdir(self.path.parent)), ["lock", "waiting"])

    def test_corrupt_state_still_answers_in_json(self):
        self.path.write_text('{"turn": "turn-1", "started": "yesterday"}')
        self.event("Stop")
        self.assertEqual(self.notification(), ("Glass", 3, "0.4", False))
        with patch.object(sys, "argv", ["codex.py"]), patch.object(codex, "handle", side_effect=TypeError("bad")), \
                patch.object(sys, "stdin", io.StringIO("{}")), \
                patch.object(sys, "stdout", new_callable=io.StringIO) as output:
            codex.main()
        self.assertEqual(json.loads(output.getvalue()), {"systemMessage": "turn-ding: bad"})

    def test_missing_session_and_unknown_event_are_ignored(self):
        codex.handle({"hook_event_name": "Stop"})
        self.event("SomethingElse")
        self.launch.assert_not_called()

    def test_hook_returns_json_without_approving_or_blocking(self):
        for value in [self.path.read_text(), "{}", "[]", "broken JSON"]:
            with self.subTest(value=value), patch.object(sys, "argv", ["codex.py"]), \
                    patch.object(sys, "stdin", io.StringIO(value)), \
                    patch.object(sys, "stdout", new_callable=io.StringIO) as output:
                codex.main()
                response = json.loads(output.getvalue())
                self.assertNotIn("decision", response)
                self.assertNotIn("continue", response)

    def test_launch_passes_worker_arguments_and_closes_inherited_pipes(self):
        with patch.object(subprocess, "Popen") as process:
            self.real_launch(self.path, "token", "Glass", 3, "0.4", True)
        argv = process.call_args.args[0]
        self.assertEqual(argv[2:], ["--play", str(self.path), "token", "Glass", "3", "0.4", "1"])
        self.assertEqual(process.call_args.kwargs["stdin"], subprocess.DEVNULL)
        self.assertEqual(process.call_args.kwargs["stdout"], subprocess.DEVNULL)
        with patch.object(sys, "argv", argv[1:]), patch.object(codex, "play") as play:
            codex.main()
        play.assert_called_once_with(str(self.path), "token", "Glass", 3, "0.4", True)


class PlaybackTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(patch.stopall)
        self.run = patch.object(subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "", "")).start()

    def test_helper_uses_the_same_audio_settings(self):
        codex.ring("Glass", 3, "0.4")
        self.assertEqual(self.run.call_args.args[0], [str(codex.HELPER),
                         "/System/Library/Sounds/Glass.aiff", "3", "0.5", "0.4"])

    def test_helper_failure_falls_back_to_afplay(self):
        for failure in [subprocess.CompletedProcess([], 1, "", "failed"), OSError("missing helper"),
                        subprocess.TimeoutExpired("helper", 10)]:
            with self.subTest(failure=failure):
                self.run.reset_mock()
                self.run.side_effect = [failure] + [subprocess.CompletedProcess([], 0, "", "")] * 3
                codex.ring("Ping", 3, "0.4")
                self.assertEqual([call.args[0] for call in self.run.call_args_list[1:]],
                                 [["/usr/bin/afplay", "-v", "4", "-t", "0.5", "/System/Library/Sounds/Ping.aiff"]] * 3)

    def test_failed_fallback_reports_the_reason(self):
        self.run.return_value = subprocess.CompletedProcess([], 1, "", "no output device")
        with self.assertRaisesRegex(OSError, "no output device"):
            codex.ring("Glass", 3, "0.4")

    def test_timeouts_follow_the_ring_settings(self):
        with patch.object(codex, "RING_SECONDS", "2"):
            self.run.side_effect = [subprocess.CompletedProcess([], 1, "", "")] + \
                [subprocess.CompletedProcess([], 0, "", "")] * 10
            codex.ring("Glass", 10, "0.4")
        self.assertEqual([call.kwargs["timeout"] for call in self.run.call_args_list], [27] + [7] * 10)

    def test_presence_boundaries_and_locked_screen(self):
        for state, expected in [("59 0 1", (59, "watching")), ("60 0 1", (60, "elsewhere")),
                                ("179 0 1", (179, "elsewhere")), ("180 0 0", (180, "away")),
                                ("5 1 1", (5, "away"))]:
            with self.subTest(state=state):
                self.run.return_value = subprocess.CompletedProcess([], 0, state, "")
                self.assertEqual(codex.where(), expected)

    def test_unavailable_state_uses_normal_notification(self):
        for result in [subprocess.CompletedProcess([], 1, "600 1 1", ""),
                       subprocess.CompletedProcess([], 0, "nan 0 1", ""),
                       subprocess.CompletedProcess([], 0, "broken", ""),
                       OSError("missing helper"), subprocess.TimeoutExpired("state", 1)]:
            with self.subTest(result=result):
                self.run.side_effect = [result]
                self.assertEqual(codex.where(), (0, "elsewhere"))

    def test_five_reminders_then_exit(self):
        with patch.object(codex, "active", return_value=True), \
                patch.object(codex, "where", return_value=(600, "away")), \
                patch.object(codex, "ring") as ring, \
                patch.object(codex.time, "monotonic", side_effect=[0, 60, 120, 180, 240, 300]):
            codex.play(Path("state"), "token", "Glass", 3, "0.2", True)
        self.assertEqual([call.args for call in ring.call_args_list],
                         [("Glass", 3, "0.2")] + [("Glass", 1, "0.2")] * 5)

    def test_recent_input_or_unavailable_state_stops_reminders(self):
        for idle in [59, 0]:
            with self.subTest(idle=idle), patch.object(codex, "active", return_value=True), \
                    patch.object(codex, "where", return_value=(idle, "elsewhere")), \
                    patch.object(codex, "ring") as ring, \
                    patch.object(codex.time, "monotonic", side_effect=[0, 60]):
                codex.play(Path("state"), "token", "Glass", 3, "0.2", True)
                ring.assert_called_once_with("Glass", 3, "0.2")

    def test_cancelled_worker_never_rings(self):
        with patch.object(codex, "active", return_value=False), patch.object(codex, "ring") as ring:
            codex.play(Path("state"), "old-token", "Glass", 3, "0.2", True)
        ring.assert_not_called()

    def test_cancellation_during_wait_stops_worker_without_another_ring(self):
        with patch.object(codex, "active", side_effect=[True, False]), \
                patch.object(codex, "ring") as ring, \
                patch.object(codex.time, "monotonic", return_value=0):
            codex.play(Path("state"), "token", "Glass", 3, "0.2", True)
        ring.assert_called_once_with("Glass", 3, "0.2")


class PackagingTests(unittest.TestCase):
    def test_codex_manifest_overrides_the_claude_module_hooks(self):
        manifest = json.loads((ROOT / ".codex-plugin/plugin.json").read_text())
        hooks = json.loads((ROOT / manifest["hooks"]).read_text())["hooks"]
        self.assertIn("Stop", hooks)
        self.assertNotIn("SubagentStop", hooks)
        matcher = hooks["PreToolUse"][0]["matcher"]
        for tool in ["request_user_input", "request_user_input_async", "mcp__app__AskUserQuestion"]:
            self.assertRegex(tool, matcher)
        self.assertIsNone(re.search(matcher, "Bash"))
        self.assertEqual(json.loads((ROOT / "hooks/hooks.json").read_text()),
                         {"modules": ["./register.ts"]})

    def test_tool_completion_skips_python_unless_a_session_waits(self):
        command = json.loads((ROOT / "hooks/codex.json").read_text())["hooks"]["PostToolUse"][0]["hooks"][0]["command"]
        event = json.dumps({"session_id": "s", "turn_id": "t", "hook_event_name": "PostToolUse", "tool_name": "Bash"})
        with tempfile.TemporaryDirectory() as data:
            for shell in ["/bin/sh", "/bin/zsh", "/bin/bash"]:
                run = lambda env: subprocess.run([shell, "-c", command], env={**os.environ, **env}, input=event,
                                                 capture_output=True, text=True, timeout=3)
                skipped = run({"PLUGIN_ROOT": "/nonexistent", "PLUGIN_DATA": data})
                self.assertEqual((skipped.returncode, skipped.stdout, skipped.stderr), (0, "", ""))
                os.makedirs(os.path.join(data, "codex", "waiting"))
                handled = run({"PLUGIN_ROOT": str(ROOT), "PLUGIN_DATA": data})
                self.assertEqual((handled.returncode, handled.stdout), (0, "{}\n"))
                os.rmdir(os.path.join(data, "codex", "waiting"))
                env = {key: value for key, value in os.environ.items() if key != "PLUGIN_DATA"}
                unset = subprocess.run([shell, "-c", command], env={**env, "PLUGIN_ROOT": str(ROOT), "TMPDIR": data},
                                       input=event, capture_output=True, text=True, timeout=3)
                self.assertEqual((unset.returncode, unset.stdout), (0, "{}\n"))

    def test_native_command_launches_real_worker_from_a_path_with_spaces(self):
        with tempfile.TemporaryDirectory(prefix="turn ding ") as directory:
            root = Path(directory)
            (root / "hooks").mkdir()
            (root / "bin").mkdir()
            (root / "hooks/codex.py").write_text((ROOT / "hooks/codex.py").read_text())
            helper = root / "bin/turn-ding"
            helper.write_text(
                f"#!{sys.executable}\n"
                "import json, os, sys\n"
                "if sys.argv[1] == 'state':\n"
                "    print('5 0 0')\n"
                "else:\n"
                "    with open(os.environ['TURN_DING_TEST_OUTPUT'], 'w') as output:\n"
                "        json.dump(sys.argv[1:], output)\n"
            )
            helper.chmod(0o755)
            output = root / "played.json"
            env = {**os.environ, "PLUGIN_ROOT": str(root), "PLUGIN_DATA": str(root / "data"),
                   "TURN_DING_TEST_OUTPUT": str(output)}
            hooks = json.loads((ROOT / "hooks/codex.json").read_text())["hooks"]
            for name in ["UserPromptSubmit", "Stop"]:
                result = subprocess.run(hooks[name][0]["hooks"][0]["command"], shell=True,
                                        env=env, input=json.dumps({"session_id": "integration",
                                        "turn_id": "turn", "hook_event_name": name}),
                                        capture_output=True, text=True, timeout=3)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout), {})
            deadline = time.monotonic() + 3
            while not output.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue(output.exists(), "playback worker did not invoke the helper")
            self.assertEqual(json.loads(output.read_text()),
                             ["/System/Library/Sounds/Glass.aiff", "3", "0.5", "0.4"])


if __name__ == "__main__":
    unittest.main()
