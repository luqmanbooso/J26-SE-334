"""Convert AndroR2 reproduction scripts into the neutral C4 trace format.

AndroR2 (https://github.com/SageSELab/AndroR2) ships, per bug report, a metadata
file (a Python-style dict, not strict JSON) and a UiAutomator Java script. Only
statements that map to a C4 action are converted. Everything else is recorded in
the ``conversion`` block of the trace so coverage can be reported honestly.

The scripts carry no timestamps. Steps get ordinal timestamps, one second apart,
and every step is flagged ``synthetic_time``.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path("scripts/reproducing_script_project/app/src/androidTest/java/edu/sage/android")
BASE_TIME = datetime(2000, 1, 1, tzinfo=timezone.utc)
_UI_ACTION_CALLS = ("pressHome", "pressRecentApps", "pressEnter", "pressMenu", "openNotification",
                    "openQuickSettings", "startActivityFromHomeScreen", "setOrientationLeft",
                    "setOrientationRight", "setOrientationNatural", "pressDPad", "drag", "longClick")
_IGNORED = re.compile(r"^(?:TimeUnit\.\w+\.sleep|Thread\.sleep|\w+\.sleep|assert\w*|\w+\.wait|\w+\.waitForIdle)\b")
_CONSTANT = re.compile(r'(?:static\s+)?final\s+String\s+(\w+)\s*=\s*"((?:[^"\\]|\\.)*)"\s*;')
_PACKAGE = re.compile(r'(?:PACKAGE_NAME|BASIC_SAMPLE_PACKAGE)\s*=\s*"([^"]+)"')
_BINDING = re.compile(r"^(?:(?:final\s+)?[\w.<>\[\]]+\s+)?(\w+)\s*=\s*(.+)$", re.S)
_CONTROL = re.compile(r"^(?:try\b|finally\b|catch\s*\([^)]*\)|[{}])\s*")
_Target = tuple[dict[str, str], bool, str]  # locator, approximate, selector text


def _split_arguments(text: str) -> list[str]:
    """Split call arguments at top-level commas, ignoring commas inside strings or parentheses."""
    parts: list[str] = []
    depth, quote, start, index = 0, False, 0, 0
    while index < len(text):
        char = text[index]
        if quote:
            if char == "\\":
                index += 1
            elif char == '"':
                quote = False
        elif char == '"':
            quote = True
        elif char in "([":
            depth += 1
        elif char in ")]":
            depth -= 1
        elif char == "," and depth == 0:
            parts.append(text[start:index].strip())
            start = index + 1
        index += 1
    last = text[start:].strip()
    return [*parts, last] if last or parts else []


def convert_dataset(
    root: str | Path,
    *,
    failure_types: tuple[str, ...] = ("crash",),
    only_complete: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Convert every report under ``root`` and return the traces and a coverage report."""
    base = Path(root)
    traces: list[dict[str, Any]] = []
    problems: Counter[str] = Counter()
    skipped: dict[str, str] = {}
    scripts = steps_converted = steps_dropped = 0
    for path in sorted((base / "metadata").glob("*.json"), key=lambda item: _sort_key(item.stem)):
        metadata = _read_metadata(path)
        if metadata is None:
            skipped[path.stem] = "metadata is not a readable dict"
            continue
        if metadata.get("failure_type") not in failure_types:
            skipped[path.stem] = f"failure_type {metadata.get('failure_type')!r} not selected"
            continue
        script = base / SCRIPT_DIR / f"Script{path.stem}.java"
        if not script.is_file():
            skipped[path.stem] = "script file not found"
            continue
        scripts += 1
        trace = convert_script(script.read_text(encoding="utf-8", errors="replace"), metadata)
        # Coverage counts every script read, including ones filtered out below.
        steps_converted += trace["conversion"]["steps_converted"]
        steps_dropped += len(trace["conversion"]["dropped"])
        for item in trace["conversion"]["dropped"]:
            problems[item["reason"]] += 1
        if only_complete and trace["conversion"]["dropped"]:
            skipped[path.stem] = "has statements that cannot be converted"
            continue
        if not trace["steps"]:
            skipped[path.stem] = "no convertible steps"
            continue
        traces.append(trace)
    report = {
        "scripts_read": scripts,
        "traces_written": len(traces),
        "fully_converted": sum(not trace["conversion"]["dropped"] for trace in traces),
        "steps_converted": steps_converted,
        "steps_dropped": steps_dropped,
        "dropped_reasons": dict(sorted(problems.items(), key=lambda item: -item[1])),
        "skipped": skipped,
        "failure_types": list(failure_types),
    }
    return traces, report


def convert_script(java: str, metadata: dict[str, Any]) -> dict[str, Any]:
    """Convert one script into a trace record."""
    constants = {name: _unescape(value) for name, value in _CONSTANT.findall(java)}
    package = next(iter(_PACKAGE.findall(java)), None)
    steps: list[dict[str, Any]] = []
    dropped: list[dict[str, str]] = []
    variables: dict[str, _Target | None] = {}
    phase = "setup"
    comment = ""
    for kind, text in _tokens("\n".join(_test_bodies(java))):
        if kind == "comment":
            lowered = text.lower()
            if "setup gui" in lowered:
                phase = "setup"
            elif "bug-specific" in lowered or "bug specific" in lowered:
                phase = "bug"
            elif lowered.startswith("assertion"):
                phase = "assertions"
            comment = text
            continue
        binding = _binding(text, constants)
        if binding is not None:
            variables[binding[0]] = binding[1]
            continue
        converted, reason = _statement(text, constants, variables)
        if converted is not None:
            index = len(steps)
            step = {
                "timestamp": (BASE_TIME + timedelta(seconds=index)).isoformat().replace("+00:00", "Z"),
                "synthetic_time": True,
                "phase": phase,
                "name": comment or converted["action"],
                **converted,
            }
            steps.append(step)
        elif reason:
            dropped.append({"statement": _squash(text)[:160], "reason": reason})
        comment = ""
    failure_type = str(metadata.get("failure_type", "unknown"))
    return {
        "trace_id": f"andror2-{metadata.get('id')}",
        "app_version": metadata.get("commit_id"),
        "os_version": metadata.get("android_os"),
        "app_package": package,
        "app_apk": f"apks/{metadata.get('id')}.apk",
        "dataset": {"name": "andror2", "failure_type": failure_type, "issue": metadata.get("github_issue")},
        "steps": steps,
        "failure": {"type": f"andror2.{failure_type}", "message": f"{failure_type} reported in issue {metadata.get('github_issue')}"},
        "conversion": {"steps_converted": len(steps), "dropped": dropped,
                       "gui_actions_in_dataset": metadata.get("gui_actions")},
    }


def _binding(text: str, constants: dict[str, str]) -> tuple[str, _Target | None] | None:
    """Recognise ``Type name = dev.findObject(...)`` and ``name = dev.wait(Until.findObject(...), n)``."""
    match = _BINDING.match(_strip_control(_squash(text)))
    if not match:
        return None
    right = match.group(2).strip()
    inner = (re.fullmatch(r"\w+\.wait\(\s*Until\.findObject\((.*)\)\s*,\s*\w+\s*\)", right, re.S)
             or re.fullmatch(r"\w+\.findObject\((.*)\)", right, re.S))
    if not inner:
        return None
    target = _target(inner.group(1), constants)
    return match.group(1), (None if isinstance(target, str) else target)


def _target(expression: str, constants: dict[str, str]) -> _Target | str:
    """Resolve a ``UiSelector`` chain or ``By.res/desc/text`` to a locator, or return the reason it fails."""
    expression = expression.strip()
    if expression.startswith("new UiSelector()"):
        calls = _selector(expression)
        if calls is None:
            return "findObject argument is not a UiSelector chain"
        locator, approximate = _locator(calls)
        if not locator:
            return "selector has no text, id, description, or instance-only form"
        return locator, approximate, _squash(expression)
    match = re.fullmatch(r"By\.(res|desc|text)\((.*)\)", expression, re.S)
    if not match:
        return "findObject argument is not a UiSelector chain"
    values = [_value(argument, constants) for argument in _split_arguments(match.group(2))]
    if not values or None in values or len(values) > 2:
        return "By selector argument is not a string literal or constant"
    if match.group(1) == "res":
        resource = values[0] if len(values) == 1 else f"{values[0]}:id/{values[1]}"
        return {"resource_id": resource}, False, _squash(expression)
    return {"content_desc" if match.group(1) == "desc" else "text": values[0]}, False, _squash(expression)


def _step(target: _Target, method: str, argument: str, constants: dict[str, str]) -> tuple[dict[str, Any] | None, str | None]:
    locator, approximate, selector = target
    step: dict[str, Any] = {"selector": selector, **locator}
    if approximate:
        step["approximate_locator"] = True
    if method in ("setText", "legacySetText"):
        value = _value(argument, constants)
        if value is None:
            return None, "typed value is not a string literal or constant"
        return {**step, "action": "input", "value": value}, None
    if method == "click" and argument.strip():
        return None, "click with an argument (long press)"
    return {**step, "action": "tap"}, None


def _strip_control(text: str) -> str:
    """Drop leading ``try``, ``catch (...)``, ``finally`` and braces that wrap a statement."""
    text = text.strip()
    while True:
        stripped = _CONTROL.sub("", text, count=1).strip()
        if stripped == text:
            return text
        text = stripped


def _statement(
    text: str, constants: dict[str, str], variables: dict[str, _Target | None] | None = None
) -> tuple[dict[str, Any] | None, str | None]:
    """Return a converted step, or ``(None, reason)`` for a UI action that cannot be represented."""
    text = _strip_control(_squash(text))
    if not text:
        return None, None
    match = re.match(r"^\w+\.findObject\((.*)\)\.(click|clickAndWaitForNewWindow|setText|legacySetText)\((.*)\)$", text, re.S)
    if match is None:
        match = re.match(r"^\w+\.wait\(\s*Until\.findObject\((.*)\)\s*,\s*\w+\s*\)\.(click|clickAndWaitForNewWindow|setText|legacySetText)\((.*)\)$",
                         text, re.S)
    if match:
        target = _target(match.group(1), constants)
        if isinstance(target, str):
            return None, target
        return _step(target, match.group(2), match.group(3), constants)
    match = re.match(r"^(\w+)\.(click|clickAndWaitForNewWindow|setText|legacySetText)\((.*)\)$", text, re.S)
    if match and variables is not None and match.group(1) in variables:
        target = variables[match.group(1)]
        if target is None:
            return None, "variable has no resolved locator"
        return _step(target, match.group(2), match.group(3), constants)
    if _IGNORED.match(text):
        return None, None
    if re.match(r"^\w+\.click\(\s*-?\d+\s*,\s*-?\d+\s*\)$", text):
        return None, "coordinate tap"
    if re.match(r"^\w+\.swipe\(", text) or re.match(
        r"^\w+\.findObject\(.*\)\.(?:swipe(?:Up|Down|Left|Right)|scrollForward|scrollBackward|fling\w*)\(", text, re.S
    ):
        return {"action": "scroll"}, None
    if re.match(r"^\w+\.pressBack\(\)$", text):
        return {"action": "back"}, None
    call = re.match(r"^(?:\w+\.)?(\w+)\(", text)
    if call and call.group(1) in _UI_ACTION_CALLS:
        return None, f"{call.group(1)} has no C4 action"
    if re.match(r"^if\s*\(", text) and (".click(" in text or ".setText(" in text):
        return None, "conditional action"
    if ".findObject(" in text or ".click(" in text:
        return None, "unrecognized UI statement"
    return None, None


def _selector(expression: str) -> list[tuple[str, str]] | None:
    expression = expression.strip()
    if not expression.startswith("new UiSelector()"):
        return None
    calls: list[tuple[str, str]] = []
    rest = expression[len("new UiSelector()"):]
    position = 0
    while position < len(rest):
        match = re.compile(r"\s*\.(\w+)\(").match(rest, position)
        if not match:
            return None if rest[position:].strip() else calls
        end = _close_paren(rest, match.end() - 1)
        if end is None:
            return None
        calls.append((match.group(1), rest[match.end():end].strip()))
        position = end + 1
    return calls


def _locator(calls: list[tuple[str, str]]) -> tuple[dict[str, str], bool]:
    named: dict[str, str] = {}
    for method, argument in calls:
        named.setdefault(method, argument)
    extras = {"instance", "index"} & set(named)
    for method, key in (("resourceId", "resource_id"), ("text", "text"), ("description", "content_desc")):
        value = _string_literal(named.get(method))
        if value is not None:
            return {key: value}, bool(extras)
    allowed = {"className", "clickable", "instance"}
    if set(named) <= allowed and ("className" in named or "clickable" in named):
        class_name = _string_literal(named.get("className"))
        instance_text = named.get("instance", "0")
        instance = int(instance_text) if instance_text.isdigit() else None
        if instance is None or ("className" in named and class_name is None):
            return {}, False
        predicate = "[@clickable='true']" if named.get("clickable") == "true" else ""
        if "clickable" in named and named["clickable"] != "true":
            return {}, False
        return {"xpath": f"(//{class_name or '*'}{predicate})[{instance + 1}]"}, False
    return {}, False


def _value(argument: str, constants: dict[str, str]) -> str | None:
    literal = _string_literal(argument.strip())
    if literal is not None:
        return literal
    return constants.get(argument.strip())


def _string_literal(text: str | None) -> str | None:
    if text is None:
        return None
    match = re.fullmatch(r'"((?:[^"\\]|\\.)*)"', text.strip(), re.S)
    return _unescape(match.group(1)) if match else None


def _unescape(value: str) -> str:
    return value.replace('\\"', '"').replace("\\\\", "\\").replace("\\n", "\n").replace("\\t", "\t")


def _char_literal_end(text: str, index: int) -> int:
    """Index of the closing quote when a Java char literal starts at ``index``, else ``index``."""
    if text[index + 1:index + 2] == "\\":
        end = index + (7 if text[index + 2:index + 3] == "u" else 3)
    else:
        end = index + 2
    return end if text[end:end + 1] == "'" else index


def _close_paren(text: str, open_index: int) -> int | None:
    depth, index, quote = 0, open_index, False
    while index < len(text):
        char = text[index]
        if quote:
            if char == "\\":
                index += 1
            elif char == '"':
                quote = False
        elif char == '"':
            quote = True
        elif char == "'":
            index = _char_literal_end(text, index)
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return None


def _test_bodies(java: str) -> list[str]:
    """Return the bodies of every ``@Test`` method, in source order."""
    bodies: list[str] = []
    for match in re.finditer(r"@Test\b", java):
        brace = java.find("{", match.end())
        if brace == -1:
            continue
        depth, index, quote = 0, brace, False
        while index < len(java):
            char = java[index]
            if quote:
                if char == "\\":
                    index += 1
                elif char == '"':
                    quote = False
            elif char == '"':
                quote = True
            elif char == "'":
                index = _char_literal_end(java, index)
            elif java.startswith("//", index):
                index = java.find("\n", index) - 1 if java.find("\n", index) != -1 else len(java)
            elif java.startswith("/*", index):
                end = java.find("*/", index)
                index = len(java) if end == -1 else end + 1
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    bodies.append(java[brace + 1:index])
                    break
            index += 1
    return bodies


def _tokens(body: str) -> list[tuple[str, str]]:
    """Split a method body into line comments and ``;``-terminated statements."""
    tokens: list[tuple[str, str]] = []
    current: list[str] = []
    index, quote = 0, False
    while index < len(body):
        char = body[index]
        if quote:
            current.append(char)
            if char == "\\" and index + 1 < len(body):
                current.append(body[index + 1])
                index += 1
            elif char == '"':
                quote = False
        elif char == '"':
            quote = True
            current.append(char)
        elif char == "'":
            end = _char_literal_end(body, index)
            current.append(body[index:end + 1])
            index = end
        elif body.startswith("//", index):
            end = body.find("\n", index)
            end = len(body) if end == -1 else end
            tokens.append(("comment", body[index + 2:end].strip()))
            index = end
        elif body.startswith("/*", index):
            end = body.find("*/", index)
            index = len(body) if end == -1 else end + 1
        elif char == ";":
            tokens.append(("stmt", "".join(current)))
            current = []
        else:
            current.append(char)
        index += 1
    return tokens


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _sort_key(stem: str) -> tuple[int, str]:
    return (int(stem), stem) if stem.isdigit() else (10**9, stem)


def _read_metadata(path: Path) -> dict[str, Any] | None:
    try:
        value = ast.literal_eval(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m evaluation.andror2_import")
    parser.add_argument("--dataset", required=True, help="Path to a clone of SageSELab/AndroR2")
    parser.add_argument("--out", required=True, help="Directory that receives traces.jsonl and conversion_report.json")
    parser.add_argument("--failure-types", nargs="+", default=["crash"], choices=("crash", "output", "gui"))
    parser.add_argument("--only-complete", action="store_true",
                        help="Keep only traces in which every UI action was converted")
    args = parser.parse_args(argv)
    if not (Path(args.dataset) / "metadata").is_dir():
        print(f"{args.dataset} has no metadata directory; point --dataset at the AndroR2 clone", file=sys.stderr)
        return 2
    traces, report = convert_dataset(args.dataset, failure_types=tuple(args.failure_types),
                                     only_complete=args.only_complete)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "traces.jsonl").write_text(
        "".join(json.dumps(trace, sort_keys=True) + "\n" for trace in traces), encoding="utf-8")
    (out / "conversion_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("scripts_read", "traces_written", "fully_converted",
                                                    "steps_converted", "steps_dropped")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
