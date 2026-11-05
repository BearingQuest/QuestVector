"""Opt-in live test of narrative generation against a local Ollama server.

The live test is skipped unless ``QV_OLLAMA_LIVE=1`` is set, so the default
suite and CI never need a running server (see ``docs/DEVELOPMENT.md``).
Optional settings:

* ``QV_OLLAMA_MODEL``: model tag, already pulled (default:
  ``DEFAULT_OLLAMA_MODEL``, currently ``gemma4:12b-it-q4_K_M``).
* ``QV_OLLAMA_HOST``: server URL (default: ``http://localhost:11434``).
* ``QV_OLLAMA_TIMEOUT``: seconds to wait (default: the provider's default).

It uses only the synthetic dossier in ``tests/fixtures/live_narrative``,
shared with ``test_remote_live.py``. It checks the plumbing (a non-empty
answer, no error), not accuracy, and prints the answer for scoring by hand
against the fixture's ``answer_key.json`` (run with ``-s`` to see it).
Automatic accuracy checks belong to backlog item 5.

The fixture checks below always run, so a broken fixture fails in CI.
"""

from __future__ import annotations

import os

import pytest
from live_narrative import (
    CAPABILITIES_SENT,
    DOSSIER_FILES,
    FIXTURES,
    narrative_prompt,
    print_narrative,
    trap_forms,
)

from questvector.core.llm import (
    DEFAULT_OLLAMA_HOST,
    DEFAULT_OLLAMA_MODEL,
    create_narrative_generator,
)
from questvector.core.markdown_parser import parse_dossier

# --- Fixture checks (always run, no network) ---------------------------------


def test_fixture_dossier_reaches_the_model_whole() -> None:
    dossier = parse_dossier(FIXTURES)

    assert dossier.capabilities
    assert len(dossier.capabilities) <= CAPABILITIES_SENT


@pytest.mark.parametrize("filename", DOSSIER_FILES)
def test_fixture_trap_keywords_are_absent_from_the_dossier(filename: str) -> None:
    text = (FIXTURES / filename).read_text(encoding="utf-8").lower()

    for name, forms in trap_forms().items():
        assert not any(form in text for form in forms), f"{name} appears in {filename}"


def test_fixture_trap_keywords_are_in_the_job_description() -> None:
    text = (FIXTURES / "job_description.txt").read_text(encoding="utf-8").lower()

    for name, forms in trap_forms().items():
        assert any(form in text for form in forms), f"{name} missing from the job description"


def test_fixture_prompt_contains_dossier_and_job_description() -> None:
    prompt = narrative_prompt()

    assert "Prometheus and Grafana" in prompt
    assert "HashiCorp Vault" in prompt


# --- Live test (opt-in) -------------------------------------------------------


@pytest.mark.live
@pytest.mark.skipif(
    os.environ.get("QV_OLLAMA_LIVE") != "1",
    reason="live Ollama test; set QV_OLLAMA_LIVE=1 with a local server running",
)
def test_ollama_generates_narrative_from_synthetic_dossier() -> None:
    timeout = os.environ.get("QV_OLLAMA_TIMEOUT")
    model = os.environ.get("QV_OLLAMA_MODEL") or DEFAULT_OLLAMA_MODEL
    generator = create_narrative_generator(
        "ollama",
        model=model,
        host=os.environ.get("QV_OLLAMA_HOST") or DEFAULT_OLLAMA_HOST,
        timeout=float(timeout) if timeout else None,
    )

    # An unreachable server or missing model raises LLMError and fails the
    # test: the user opted in, so a skip would hide the problem.
    narrative = generator.generate(narrative_prompt())

    assert narrative.strip()
    print_narrative("ollama", model, narrative)
