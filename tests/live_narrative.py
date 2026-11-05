"""Shared helpers for the opt-in live narrative tests.

Both ``test_ollama_live.py`` and ``test_remote_live.py`` send the same prompt,
built from the synthetic dossier and job description in
``tests/fixtures/live_narrative``. Nothing in that folder is real career
data. ``answer_key.json`` there is for scoring output by hand; automatic
accuracy checks belong to backlog item 5.
"""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

from questvector.config import CAPABILITIES_FILENAME, CHRONOLOGY_FILENAME, IMPACT_FILENAME
from questvector.core import matcher
from questvector.core.llm import build_narrative_prompt
from questvector.core.markdown_parser import parse_dossier
from questvector.core.templates import load_template

FIXTURES = Path(__file__).parent / "fixtures" / "live_narrative"
DOSSIER_FILES = (CAPABILITIES_FILENAME, CHRONOLOGY_FILENAME, IMPACT_FILENAME)
# qv export --narrative sends this many capability bullets (questvector/cli.py).
CAPABILITIES_SENT = 20


def answer_key() -> dict[str, object]:
    """Load the fixture's answer key."""
    return json.loads((FIXTURES / "answer_key.json").read_text(encoding="utf-8"))


def trap_forms() -> dict[str, list[str]]:
    """Return each trap keyword's spellings, lowercased."""
    traps = answer_key()["trap_keywords"]
    assert isinstance(traps, dict)
    return {name: [form.lower() for form in forms] for name, forms in traps.items()}


def narrative_prompt() -> str:
    """Build the prompt exactly as ``qv export --narrative`` does."""
    dossier = parse_dossier(FIXTURES)
    jd_text = (FIXTURES / "job_description.txt").read_text(encoding="utf-8")
    job_description = matcher.parse_job_description(jd_text, source="job_description.txt")
    template_file = resources.files("questvector.data.starter_templates") / "devops-senior-mgr.qv-mission.yaml"
    with resources.as_file(template_file) as template_path:
        template = load_template(template_path)
    dossier_context = "\n".join(c.text for c in dossier.capabilities[:CAPABILITIES_SENT])
    return build_narrative_prompt(dossier_context, job_description.raw_text, tone_style=template.tone_style)


def print_narrative(provider: str, model: str, narrative: str) -> None:
    """Print a live narrative for scoring by hand (shown with ``pytest -s``)."""
    print(f"\n--- {provider} narrative ({model}); score against {FIXTURES / 'answer_key.json'} ---")
    print(narrative)
    print("--- end ---")
