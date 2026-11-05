"""Opt-in live test of narrative generation against remote AI providers.

Skipped unless ``QV_LIVE_PROVIDERS`` names the provider, so the default
suite and CI never make a network call (see ``docs/DEVELOPMENT.md``).
Settings:

* ``QV_LIVE_PROVIDERS``: comma-separated provider ids to test, for example
  ``anthropic`` or ``anthropic,gemini``.
* The provider's usual key variable: ``ANTHROPIC_API_KEY``,
  ``OPENAI_API_KEY`` or ``GEMINI_API_KEY``. It's read only here and passed
  only to the provider; it's never printed, logged or put in a failure
  message. An opted-in provider with no key fails rather than skips.
* Optional model override: ``QV_ANTHROPIC_MODEL``, ``QV_OPENAI_MODEL`` or
  ``QV_GEMINI_MODEL`` (default: the provider's registry default).

Each opted-in provider gets one generation call per run, at the
generator's usual token limit, on the synthetic dossier in
``tests/fixtures/live_narrative`` (shared with ``test_ollama_live.py``). The
provider SDKs retry a rate-limit or server error up to 2 times, so a failing
call can mean up to 3 requests. The test checks the plumbing (a non-empty
answer, no error), not accuracy, and prints the answer for scoring by hand
against ``answer_key.json`` (run with ``-s`` to see it).

The harness checks below always run with the provider faked, so they need
no network or key.
"""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace

import pytest
from live_narrative import narrative_prompt, print_narrative

from questvector.core.llm import PROVIDERS, _redact, create_narrative_generator

# Remote provider id -> the environment variable its API key comes from.
KEY_VARIABLES = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
}


def _opted_in() -> set[str]:
    """Return the provider ids named in ``QV_LIVE_PROVIDERS``."""
    raw = os.environ.get("QV_LIVE_PROVIDERS", "")
    return {name.strip().lower() for name in raw.split(",") if name.strip()}


def _generate_live(provider: str, model: str) -> str:
    """Make the one live call for ``provider``, failing cleanly on any problem.

    The key is read here and goes only to the provider factory. Failures use
    ``pytrace=False`` and a redacted message, and are raised outside the
    ``except`` block, so no traceback, local variable or chained exception
    can show the key.
    """
    key_variable = KEY_VARIABLES[provider]
    api_key = os.environ.get(key_variable, "")
    if not api_key:
        pytest.fail(
            f"{provider} is in QV_LIVE_PROVIDERS but {key_variable} isn't set; "
            "see 'Live test against a remote provider' in docs/DEVELOPMENT.md",
            pytrace=False,
        )
    try:
        generator = create_narrative_generator(provider, api_key=api_key, model=model)
        return generator.generate(narrative_prompt())
    # Any failure is reported, redacted: the user opted in, so a skip would hide it.
    except Exception as exc:
        message = _redact(f"{type(exc).__name__}: {exc}", api_key)
    pytest.fail(f"live {provider} call with model '{model}' failed: {message}", pytrace=False)


# --- Harness checks (always run, provider faked, no network) ----------------


def test_live_providers_setting_names_only_remote_providers() -> None:
    unknown = _opted_in() - set(KEY_VARIABLES)

    if unknown:
        pytest.fail(
            f"QV_LIVE_PROVIDERS names unknown provider(s): {', '.join(sorted(unknown))}; "
            f"valid: {', '.join(sorted(KEY_VARIABLES))}",
            pytrace=False,
        )


def test_every_remote_provider_has_a_key_variable() -> None:
    remote = {name for name, spec in PROVIDERS.items() if spec.requires_api_key}

    assert set(KEY_VARIABLES) == remote


def test_missing_key_fails_naming_the_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(pytest.fail.Exception, match="ANTHROPIC_API_KEY isn't set"):
        _generate_live("anthropic", "some-model")


def test_failure_message_never_shows_the_key(monkeypatch: pytest.MonkeyPatch) -> None:
    key = "plainlivekeymarker"
    monkeypatch.setenv("ANTHROPIC_API_KEY", key)

    def _raise(_prompt: str) -> str:
        raise RuntimeError(f"rejected credentials {key}")

    monkeypatch.setattr(
        sys.modules[__name__], "create_narrative_generator", lambda *_a, **_k: SimpleNamespace(generate=_raise)
    )

    with pytest.raises(pytest.fail.Exception) as excinfo:
        _generate_live("anthropic", "some-model")

    assert "rejected credentials [redacted]" in str(excinfo.value)
    assert key not in str(excinfo.value)
    assert excinfo.value.__context__ is None
    assert excinfo.value.__cause__ is None


# --- Live test (opt-in) -------------------------------------------------------


@pytest.mark.live
@pytest.mark.parametrize("provider", sorted(KEY_VARIABLES))
def test_remote_provider_generates_narrative_from_synthetic_dossier(provider: str) -> None:
    if provider not in _opted_in():
        pytest.skip(
            f"live {provider} test; set QV_LIVE_PROVIDERS={provider} and {KEY_VARIABLES[provider]}"
        )
    model = os.environ.get(f"QV_{provider.upper()}_MODEL") or PROVIDERS[provider].default_model

    narrative = _generate_live(provider, model)

    if not narrative.strip():
        pytest.fail(f"live {provider} call with model '{model}' returned an empty narrative", pytrace=False)
    print_narrative(provider, model, narrative)
