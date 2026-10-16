"""Optional API parameter rules, independent of NPC dialogue and model access."""
from fnmatch import fnmatchcase
import json
import logging
from pathlib import Path

RULES_PATH = Path(__file__).with_name("model-rules.json")
FIELDS = {"match", "token_parameter", "default_reasoning", "drop_parameters",
          "drop_sampling_with_reasoning"}
PARAMETERS = {"reasoning_effort", "temperature", "top_p"}


def load_rules(path):
    # Read on each request so custom names/rules do not require a code update.
    try:
        if path.stat().st_size > 32768:
            raise ValueError("Model rules are too large")
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict) or data.get("schema") != 1:
            raise ValueError("Unknown model rules schema")
        rules = data.get("rules")
        if not isinstance(rules, list) or len(rules) > 100:
            raise ValueError("Invalid model rules")
        for rule in rules:
            if not isinstance(rule, dict) or set(rule) - FIELDS:
                raise ValueError("Invalid model rule")
            matches = rule.get("match")
            if (not isinstance(matches, list) or not matches or len(matches) > 100
                    or any(not isinstance(p, str) or not 1 <= len(p) <= 200 for p in matches)):
                raise ValueError("Invalid model matches")
            if rule.get("token_parameter", "max_tokens") not in ("max_tokens", "max_completion_tokens"):
                raise ValueError("Invalid token parameter")
            if "default_reasoning" in rule and rule["default_reasoning"] not in (
                    "none", "minimal", "low", "medium", "high", "xhigh", "max"):
                raise ValueError("Invalid reasoning default")
            drop = rule.get("drop_parameters", [])
            if not isinstance(drop, list) or any(not isinstance(p, str) or p not in PARAMETERS for p in drop):
                raise ValueError("Invalid parameter removal")
            if type(rule.get("drop_sampling_with_reasoning", False)) is not bool:
                raise ValueError("Invalid sampling rule")
        return rules
    except (OSError, UnicodeError, ValueError, TypeError):
        logging.warning("Model parameter rules unavailable; keeping API parameters unchanged")
        return []


def adapt_parameters(doc, rules_path=None):
    """Unknown models retain their parameters; never change model, messages or budgets."""
    model = doc.get("model", "")
    if not isinstance(model, str):
        raise ValueError("Invalid model")
    # Gateways may prefix a provider name, e.g. openai/gpt-6-sol.
    name = model.lower().rsplit("/", 1)[-1]
    for rule in load_rules(rules_path or RULES_PATH):
        if not any(fnmatchcase(name, pattern.lower()) for pattern in rule["match"]):
            continue
        before = doc.copy()
        target = rule.get("token_parameter")
        if target:
            source = "max_tokens" if target == "max_completion_tokens" else "max_completion_tokens"
            if source in doc:
                limit = doc.pop(source)
                doc.setdefault(target, limit)
        if "default_reasoning" in rule:
            doc.setdefault("reasoning_effort", rule["default_reasoning"])
        if rule.get("drop_sampling_with_reasoning") and doc.get("reasoning_effort") != "none":
            doc.pop("temperature", None)
            doc.pop("top_p", None)
        for field in rule.get("drop_parameters", []):
            doc.pop(field, None)
        return doc != before
    return False
