"""Codex command hooks. Playback runs separately so dialogs open immediately."""

from __future__ import annotations

# Every hook pays for what is imported here, so only the cheap modules are;
# the rest are imported where a sound is about to play.
import fcntl
import json
import os
import sys
import time


# Keep the listening experience the same as hooks/register.ts.
SOUNDS = "/System/Library/Sounds"
REPEAT = 3
ASK_REPEAT = 1
RING_SECONDS = "0.5"
DUCK_GAIN = "0.4"
WATCHING_SECONDS = 60
AWAY_SECONDS = 180
QUICK_TURN_MS = 10_000
AWAY_DUCK_GAIN = "0.2"
REMIND_EVERY_SECONDS = 60
REMIND_TIMES = 5
FALLBACK_VOLUME = "4"

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
HELPER = os.path.join(ROOT, "bin", "turn-ding")
QUESTIONS = {"request_user_input", "request_user_input_async", "AskUserQuestion"}
EVENTS = {"UserPromptSubmit", "Stop", "PreToolUse", "PermissionRequest",
          "PostToolUse", "Interrupt", "SessionEnd"}
# Reminders last five minutes, so a waiting marker older than this is left
# over from a session that died; state files are kept much longer.
STALE_WAITING_SECONDS = 600
STALE_STATE_SECONDS = 7 * 24 * 3600
MAX_LOG_BYTES = 64 * 1024


def is_question(tool: str) -> bool:
    return tool.rsplit("__", 1)[-1] in QUESTIONS


def where() -> tuple[float, str]:
    """Query before detaching, while the session's app is still an ancestor."""
    import math
    import subprocess
    try:
        result = subprocess.run(
            [HELPER, "state"], capture_output=True, text=True, timeout=1
        )
        idle, locked, front = map(float, result.stdout.split())
        if result.returncode or not math.isfinite(idle) or idle < 0:
            raise ValueError("invalid state")
        presence = (
            "away" if locked == 1 or idle >= AWAY_SECONDS
            else "watching" if front == 1 and idle < WATCHING_SECONDS
            else "elsewhere"
        )
        return idle, presence
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return 0, "elsewhere"


def ring(sound: str, repeat: int, gain: str) -> None:
    import subprocess
    file = os.path.join(SOUNDS, sound + ".aiff")
    seconds = float(RING_SECONDS)
    try:
        # The rings, the slide down and back up, and room to spare.
        result = subprocess.run(
            [HELPER, file, str(repeat), RING_SECONDS, gain],
            capture_output=True, text=True, timeout=repeat * seconds + 7,
        )
        if result.returncode == 0:
            return
    except (OSError, subprocess.TimeoutExpired):
        pass
    for _ in range(repeat):
        result = subprocess.run(
            ["/usr/bin/afplay", "-v", FALLBACK_VOLUME, "-t", RING_SECONDS, file],
            capture_output=True, text=True, timeout=seconds + 5,
        )
        if result.returncode:
            raise OSError(f"afplay exited {result.returncode}: {result.stderr.strip()}")


def state_path(session: str) -> str:
    # Store only timing/cancellation data, never prompts or transcript contents.
    data = os.environ.get("PLUGIN_DATA")
    if not data:
        import tempfile
        data = os.path.join(tempfile.gettempdir(), f"turn-ding-{os.getuid()}")
    directory = os.path.join(data, "codex")
    os.makedirs(directory, mode=0o700, exist_ok=True)
    # Session ids are UUIDs; anything else is hashed so it cannot leave the directory.
    if not (len(session) <= 64 and session.isascii() and session.replace("-", "").isalnum()):
        import hashlib
        session = hashlib.sha256(session.encode()).hexdigest()
    return os.path.join(directory, session + ".json")


def read_state(path: str) -> dict:
    try:
        with open(path) as file:
            value = json.load(file)
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def write_state(path: str, state: dict) -> None:
    # Atomic replacement keeps the playback worker from seeing partial JSON.
    temporary = path + ".tmp"
    with open(temporary, "w") as file:
        json.dump(state, file)
    os.replace(temporary, path)


def waiting_directory(path: str) -> str:
    return os.path.join(os.path.dirname(path), "waiting")


def start_waiting(path: str, state: dict, tool: str) -> None:
    # The waiting directory exists only while some session waits on a tool;
    # the PostToolUse command in codex.json tests for it before starting Python.
    state["waiting_tool"] = tool
    directory = waiting_directory(path)
    os.makedirs(directory, exist_ok=True)
    open(os.path.join(directory, os.path.basename(path)), "w").close()


def stop_waiting(path: str, state: dict) -> None:
    if state.pop("waiting_tool", None) is None:
        return
    directory = waiting_directory(path)
    try:
        os.unlink(os.path.join(directory, os.path.basename(path)))
        os.rmdir(directory)  # Fails, as it should, while another session waits.
    except OSError:
        pass


def sweep(directory: str, seconds: float) -> None:
    try:
        cutoff = time.time() - seconds
        for entry in os.scandir(directory):
            if entry.name.endswith(".log"):
                if entry.stat().st_size > MAX_LOG_BYTES:
                    os.unlink(entry.path)
            elif entry.is_file() and entry.name != "lock" and entry.stat().st_mtime < cutoff:
                os.unlink(entry.path)
    except OSError:
        pass


def launch(path: str, token: str, sound: str, repeat: int, gain: str, away: bool) -> None:
    # No inherited pipes: Codex can finish the hook without waiting for audio.
    # The worker checks the token regularly and lives for at most five reminders.
    import subprocess
    with open(os.path.join(os.path.dirname(path), "notifications.log"), "a") as log:
        subprocess.Popen(
            [sys.executable, os.path.realpath(__file__), "--play", str(path), token,
             sound, str(repeat), gain, "1" if away else "0"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=log,
            start_new_session=True,
        )


def active(path: str, token: str) -> bool:
    return read_state(path).get("notification") == token


def play(path: str, token: str, sound: str, repeat: int, gain: str, away: bool) -> None:
    if not active(path, token):
        return
    started = time.monotonic()
    ring(sound, repeat, gain)
    if not away:
        return
    for count in range(1, REMIND_TIMES + 1):
        deadline = started + count * REMIND_EVERY_SECONDS
        while time.monotonic() < deadline:
            if not active(path, token):
                return
            time.sleep(min(1, max(0, deadline - time.monotonic())))
        if not active(path, token) or where()[0] < REMIND_EVERY_SECONDS:
            return
        ring(sound, 1, AWAY_DUCK_GAIN)


def update(path: str, name: str, turn: object, tool: str, is_subagent: bool):
    """Records the event; returns (token, sound, repeat, turn ms) when it should ring."""
    state = read_state(path)
    if name == "SessionEnd":
        stop_waiting(path, state)
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
        sweep(os.path.dirname(path), STALE_STATE_SECONDS)
        return None
    if name == "UserPromptSubmit":
        stop_waiting(path, state)
        write_state(path, {"turn": turn, "started": time.time()})
        return None
    # A delayed event from an old turn must not stop or notify a new one.
    if turn and state.get("turn") and turn != state["turn"]:
        return None
    if name == "Interrupt":
        state.pop("notification", None)
        stop_waiting(path, state)
        state["interrupted"] = True
        write_state(path, state)
        return None
    if name == "PostToolUse":
        if state.get("waiting_tool") == tool:
            state.pop("notification", None)
            stop_waiting(path, state)
            write_state(path, state)
        else:
            sweep(waiting_directory(path), STALE_WAITING_SECONDS)
        return None
    if name == "PreToolUse" and not is_question(tool):
        return None
    if name == "PermissionRequest" and is_question(tool):
        return None  # PreToolUse already rings for this question.
    stop_waiting(path, state)
    if name == "Stop":
        # Stop is a root event; SubagentStop is intentionally not registered.
        if is_subagent or state.get("interrupted"):
            return None
        if state.get("completed") and state.get("turn") == turn:
            return None
        state["completed"] = True
        started = state.get("started")
        duration = (time.time() - started) * 1000 if isinstance(started, (int, float)) else float("inf")
        sound, repeat = "Glass", REPEAT
    else:
        # Async questions return before the person answers; their reminder
        # is cancelled by the next user prompt or notification instead.
        if not tool.endswith("request_user_input_async"):
            start_waiting(path, state, tool)
        duration = float("inf")
        sound, repeat = "Ping", ASK_REPEAT
    token = os.urandom(16).hex()
    state["notification"] = token
    state.setdefault("turn", turn)
    write_state(path, state)
    return token, sound, repeat, duration


def handle(event: dict) -> None:
    name = event.get("hook_event_name")
    if name not in EVENTS:
        return
    session = event.get("session_id")
    tool = event.get("tool_name", "")
    if not isinstance(session, str) or not session or not isinstance(tool, str):
        return
    path = state_path(session)
    # One lock for every session: it is held only for the short state update,
    # never while asking where the person is or while a sound plays.
    lock = os.open(os.path.join(os.path.dirname(path), "lock"), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX)
        notification = update(path, name, event.get("turn_id"), tool, bool(event.get("agent_id")))
    finally:
        os.close(lock)
    if notification is None:
        return
    token, sound, repeat, duration = notification
    _, presence = where()
    if presence == "watching" and duration < QUICK_TURN_MS:
        return
    gain = AWAY_DUCK_GAIN if presence == "away" else "1" if presence == "watching" else DUCK_GAIN
    launch(path, token, sound, 1 if presence == "watching" else repeat, gain, presence == "away")


def main() -> None:
    if len(sys.argv) == 8 and sys.argv[1] == "--play":
        try:
            play(sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5]),
                 sys.argv[6], sys.argv[7] == "1")
        except Exception as error:
            print(f"turn-ding: {error}", file=sys.stderr)
        return
    try:
        event = json.load(sys.stdin)
        if isinstance(event, dict):
            handle(event)
    except Exception as error:
        # Whatever went wrong, the hook still answers in JSON.
        print(json.dumps({"systemMessage": f"turn-ding: {error}"}))
        return
    # In particular, Stop requires JSON; this never approves or blocks a tool.
    print("{}")


if __name__ == "__main__":
    main()
