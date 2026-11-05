# 0018. Anthropic requests switch thinking off for models that think by default

- **Status:** Accepted
- **Date:** 2026-11-04

## Context
The Anthropic default model changed from `claude-sonnet-4-5`, which retires
on 30 Nov 2026, to its recommended replacement, `claude-sonnet-5-5`
([model deprecations](https://platform.claude.com/docs/en/about-claude/model-deprecations),
checked 4 Nov 2026). Claude Sonnet 4.5 ran without thinking unless asked.
Claude Sonnet 5.5 runs adaptive thinking on any request with no `thinking`
field, at `high` effort by default. Its thinking counts toward `max_tokens`
([Sonnet 5.5 migration guide](https://platform.claude.com/docs/en/models/sonnet-5-5/migration-guide)).

QuestVector caps narrative generation at 600 tokens. [ADR-0012](0012-ollama-thinking-off.md)
found that thinking models on Ollama spent the whole limit reasoning and
returned nothing. Claude Sonnet 5.5 is likely to hit the same failure.

On Claude Sonnet 5.5, `thinking: {"type": "disabled"}` returns a 400 error.
The documented way to turn thinking off is
`thinking: {"type": "between_tools"}`. It's accepted at `low`, `medium` and
`high` effort, takes no other field, and with no tools the response contains
only text. Other Claude models reject `between_tools`. A `QV_ANTHROPIC_MODEL`
override or a vault model set to another Claude model would then get a 400.

Options considered:
- **A. Send `between_tools` only for a short, explicit list of model ids.**
  Today that list is `claude-sonnet-5-5`. Every other model gets the
  request it got before.
- **B. Always send `between_tools`.** Simplest, but it breaks every other
  Claude model with a 400.
- **C. Send nothing, and raise the token limit.** Thinking then spends
  output tokens, which are billed, and the limit no longer bounds the
  summary.
- **D. Ask the Models API what the model supports first.** It costs an
  extra request on every generation.

## Decision
`AnthropicNarrativeGenerator` sends `thinking={"type": "between_tools"}`
when the model id is in `ANTHROPIC_THINKING_OFF_MODELS`
(`questvector/core/llm.py`), and sends no `thinking` field otherwise. Effort
is not set, so the request runs at the model's default, `high`, where
`between_tools` is accepted. This applies ADR-0012's reasoning to Anthropic.

It also adds clearer errors, like the Ollama provider has:
`stop_reason == "refusal"` raises "The model declined to write this
narrative", even when partial text came back. A response with no text and
`stop_reason == "max_tokens"` names the token limit.

The `anthropic` SDK minimum rises to 2.0, the first major release to send
API version `2026-10-21`, so installs match the 2.x SDK that the mocked
tests and `uv.lock` (2.2.0, which has the `between_tools` type) use. Nothing
in QuestVector's calls needed changing for 2.x.

## Consequences
- The default model answers within the token limit, and output-token
  spend stays bounded.
- A new Claude model that thinks by default has to be added to the list by
  hand. Until it is, it runs with thinking on, and if the 600-token limit
  runs out, the error says so.
- Mocked tests cover both paths: the setting is sent for each listed model
  and omitted for any other.
- Server-side refusal fallback (a beta that retries a declined request on
  another model) is not used. A decline is reported to the user instead.
- **Live result, 5 Nov 2026:** the owner ran backlog item 8's opt-in live
  test against `claude-sonnet-5-5` on the synthetic fixtures. Thinking off
  worked: the request was accepted, and an answer came back within the
  600-token limit, in the first person with no invented facts.
- **Finding from that run:** after the summary, the model appended an
  italic note saying it didn't claim Datadog, HashiCorp Vault or SOC 2 (the
  fixture's trap keywords). It isn't summary text, and in a real export it
  would put those keywords in the resume. This decision doesn't cause or fix
  it; it's recorded in backlog item 5 (the narrative must contain only the
  summary).
