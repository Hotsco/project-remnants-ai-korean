"""Supplement recognized NPC dialogue only, using short-lived game observations."""
import json
import logging
import math
from pathlib import Path
import re
import time

ROOT = Path(__file__).resolve().parent
MARKER = "NPCFW_LUNA_DIALOGUE_V1"
CONTEXT_FILE = "NPCFW_LunaContext.json"
MAX_AGE_MS = 10000
MAX_FILE_BYTES = 131072
IDENTITY = re.compile(
    r"^You are (.+?), an adult survivor in Project Zomboid, speaking to (.+?)\. "
    r"You are a person, never an AI assistant", re.M)
SPOKEN = "\nPLAYER'S LATEST SPOKEN LINE:\n"
ENDING = "\nReply only as SELF to that spoken line."


def normalized(text):
    return re.sub(r"\s+", " ", text).strip()


def spoken_line(content):
    if not isinstance(content, str):
        return None
    if content.startswith("AUTHORITATIVE GAME CONTEXT (data, not dialogue):\n"):
        if SPOKEN not in content or not content.endswith(ENDING):
            return None
        # Split only the first delimiter: player text cannot replace game facts.
        return content.split(SPOKEN, 1)[1][:-len(ENDING)]
    return content


def read_observation(path, npc, player, line, now_ms):
    """Unknown, stale, partial, or mismatched data must never become current facts."""
    try:
        with path.open("rb") as stream:
            raw = stream.read(MAX_FILE_BYTES + 1)
        if len(raw) > MAX_FILE_BYTES:
            return None
        data = json.loads(raw.decode("utf-8-sig"))
        if not isinstance(data, dict) or data.get("schema") != 1:
            return None
        records = data.get("records")
        if not isinstance(records, list) or len(records) > 8:
            return None
        for row in reversed(records):
            if not isinstance(row, dict):
                continue
            stamp = row.get("captured_ms")
            if type(stamp) not in (float, int) or not math.isfinite(stamp):
                continue
            if not 0 <= now_ms - stamp <= MAX_AGE_MS:
                continue
            if row.get("npc") != npc or row.get("player") != player:
                continue
            if not isinstance(row.get("line"), str) or normalized(row["line"]) != normalized(line):
                continue
            facts = row.get("facts")
            if isinstance(facts, dict):
                result = dict(facts)
                # The helicopter has no normal-mode Lua getter. Only current-session
                # engine lifecycle records may supply this event state.
                result.pop("base_helicopter_active", None)
                result.pop("base_helicopter_distance_tiles", None)
                active = helicopter_from_log(path.parent.parent / "console.txt", row.get("session"))
                if active is not None:
                    result["base_helicopter_active"] = active
                return result
    except (OSError, ValueError, UnicodeError, RecursionError):
        pass
    return None


def helicopter_from_log(path, session):
    if not isinstance(session, str) or not re.fullmatch(r"[0-9]{10,17}", session):
        return None
    try:
        # Bounded tail scan; if the session marker has fallen out, state is unknown.
        # No timestamps, frame counters, installation versions, or absolute paths
        # are assumed. Never use an event from before this world-session marker.
        with path.open("rb") as stream:
            stream.seek(0, 2)
            size = stream.tell()
            start = max(0, size - 8 * 1024 * 1024)
            stream.seek(start)
            raw = stream.read(8 * 1024 * 1024)
        if start:
            raw = raw.partition(b"\n")[2]
        if not raw.endswith(b"\n"):
            raw = raw.rpartition(b"\n")[0]
        current, active = None, None
        # Skip unrelated bytes before decoding and parsing. Rescan each request
        # so truncation, rotation and a new world session cannot leave cached facts.
        for raw_line in raw.splitlines():
            if b"chopper:" not in raw_line and b"[NPCFW Luna Context] session " not in raw_line:
                continue
            line = raw_line.decode("utf-8", errors="replace")
            match = re.match(r"^LOG\s*:\s*.*?\bf:\d+>\s*(.*?)\s*$", line)
            if not match:
                continue
            message = match[1]
            marker = re.fullmatch(r"\[NPCFW Luna Context\] session ([0-9]{10,17})", message)
            if marker:
                current, active = marker[1], None
            elif current == session:
                if message == "chopper: activated":
                    active = True
                elif message == "chopper: deactivated":
                    active = False
                elif re.fullmatch(r"chopper: state (Arriving|Hovering|Searching|Leaving) -> (Arriving|Hovering|Searching|Leaving)", message):
                    active = True
        return active if current == session else None
    except OSError:
        return None


def observation_text(facts):
    """Only typed, allowlisted observations reach the model; no arbitrary file prose."""
    lines = []
    for key, label in (("npc_indoors", "SELF is indoors"),
                       ("npc_in_vehicle", "SELF is in a vehicle"),
                       ("npc_sitting", "SELF is sitting")):
        value = facts.get(key)
        if type(value) is bool:
            lines.append(f"{label}: {str(value).lower()}.")
    visible = facts.get("visible_zombies_12_tiles")
    if type(visible) is int and 0 <= visible <= 10000:
        lines.append(f"Visible living zombies within 12 tiles on SELF's floor: {visible}. "
                     "This is not a count of hidden or distant zombies.")
    active = facts.get("base_helicopter_active")
    if type(active) is bool:
        lines.append(f"Base-game helicopter event active: {str(active).lower()}.")
        lines.append("This flag covers only the base-game helicopter. It does not establish "
                     "audibility, visibility, its purpose, or whether it has seen anyone. "
                     "An inactive flag does not rule out aircraft from other mods. "
                     "An active event is consistent with the speaker reporting a helicopter; "
                     "do not replace that report with an invented sound.")
    if not lines:
        return ""
    return ("Supplemental observations captured for this exact conversation start:\n" +
            "\n".join(lines) + "\nUnlisted sounds/events were not measured, not proven absent.")


def enhance(doc, context_path=None, now_ms=None, guidance_path=None):
    """Fail open on unknown Remnants formats; retain messages, budgets, and actions."""
    if any(key in doc for key in ("response_format", "tools", "functions")):
        return False
    messages = doc.get("messages")
    if not isinstance(messages, list) or len(messages) < 2:
        return False
    first, last = messages[0], messages[-1]
    if not isinstance(first, dict) or not isinstance(last, dict):
        return False
    system = first.get("content")
    if first.get("role") != "system" or not isinstance(system, str):
        return False
    identity = IDENTITY.search(system)
    if not identity or MARKER in system or "ACTION CONTRACT:" in system:
        return False
    if "Conversation is talk only" not in system or last.get("role") != "user":
        return False
    line = spoken_line(last.get("content"))
    if line is None or line.startswith("Rewrite your last response as "):
        return False
    try:
        guidance = (guidance_path or ROOT / "dialogue-guidance.txt").read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        return False
    if not guidance.strip() or len(guidance) > 8000:
        return False
    extra = ""
    if context_path is not None:
        facts = read_observation(context_path, *identity.groups(), line,
                                 time.time() * 1000 if now_ms is None else now_ms)
        if facts is not None:
            extra = observation_text(facts)
    first["content"] = system + "\n\n" + MARKER + "\n" + guidance.strip()
    if extra:
        # Use a system-owned data section; never rewrite the player's actual speech.
        first["content"] += "\n\n" + extra
    logging.info("NPC dialogue guidance applied; fresh observations=%s", bool(extra))
    return True
