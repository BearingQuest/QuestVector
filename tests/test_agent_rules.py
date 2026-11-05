"""Checks on the shared Claude Code settings in .claude/settings.json.

The human gates in CLAUDE.md (the owner reviews and merges every pull
request, and only the owner tags and publishes releases) are backed by deny
rules, and pushes and API calls by ask rules (ADR-0019). The rules match
command text, so they're a guardrail, not a sandbox.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SETTINGS = Path(__file__).parent.parent / ".claude" / "settings.json"

REQUIRED_DENY = {
    "Bash(rm -rf *)",
    "Bash(gh pr merge:*)",
    "Bash(gh pr review:*)",
    "Bash(git tag:*)",
    "Bash(gh release create:*)",
    "Bash(gh release edit:*)",
    "Bash(gh release delete:*)",
    "Bash(gh release upload:*)",
}
REQUIRED_ASK = {"Bash(git push:*)", "Bash(gh pr:*)", "Bash(gh api:*)", "Bash(python3:*)"}

# Options before the subcommand (`gh -R owner/repo pr merge`) slip past the
# prefix rules above. A trailing `*` matches the bare form only when it's the
# rule's only wildcard, hence the pairs.
OPTION_FIRST_DENY = {
    "Bash(gh * pr merge)",
    "Bash(gh * pr merge *)",
    "Bash(gh * pr review)",
    "Bash(gh * pr review *)",
    "Bash(git * tag)",
    "Bash(git * tag *)",
    "Bash(gh * release create)",
    "Bash(gh * release create *)",
    "Bash(gh * release edit)",
    "Bash(gh * release edit *)",
    "Bash(gh * release delete)",
    "Bash(gh * release delete *)",
    "Bash(gh * release upload)",
    "Bash(gh * release upload *)",
}
# Ask, not deny, so a legitimate `git -C … push` still just prompts.
OPTION_FIRST_ASK = {"Bash(git * push)", "Bash(git * push *)"}


def _settings() -> dict[str, Any]:
    data = json.loads(SETTINGS.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _rules(kind: str) -> list[str]:
    rules: list[str] = _settings()["permissions"][kind]
    return rules


def test_schema_line_present() -> None:
    assert _settings()["$schema"] == "https://json.schemastore.org/claude-code-settings.json"


def test_auto_and_bypass_modes_disabled() -> None:
    permissions = _settings()["permissions"]
    assert permissions["disableAutoMode"] == "disable"
    assert permissions["disableBypassPermissionsMode"] == "disable"


def test_human_gates_denied() -> None:
    assert REQUIRED_DENY <= set(_rules("deny"))


def test_human_gates_denied_option_first() -> None:
    assert OPTION_FIRST_DENY <= set(_rules("deny"))


def test_push_pr_api_and_python_ask() -> None:
    assert REQUIRED_ASK <= set(_rules("ask"))


def test_push_asks_option_first() -> None:
    assert OPTION_FIRST_ASK <= set(_rules("ask"))


def test_every_option_first_rule_has_bare_form() -> None:
    for rule in _rules("deny") + _rules("ask"):
        if rule.startswith("Bash(") and " * " in rule and rule.endswith(" *)"):
            bare = rule.removesuffix(" *)") + ")"
            assert bare in _rules("deny") + _rules("ask"), f"{rule} has no bare form {bare}"


def test_no_allow_rules_in_shared_settings() -> None:
    assert not _settings()["permissions"].get("allow")
