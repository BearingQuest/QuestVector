# 0019. Shared Claude Code settings lock agent modes and deny the human gates

- **Status:** Accepted
- **Date:** 2026-11-05

## Context
QuestVector is built by a coding agent (Claude Code) and directed and
reviewed by the owner. `CLAUDE.md` names the steps only the owner takes:
the owner reviews and merges every pull request, and only the owner
creates, pushes or deletes `v*` tags, which trigger and publish releases (ADR-0014). Until now
those gates were instructions only. Nothing in the repository stopped an
agent session from running `gh pr merge` or `git tag`, or from running in
auto or bypass-permissions mode, where it doesn't ask first.

risk-trainer, the owner's other repository, added a shared
`.claude/settings.json` for this in its pull requests #52 and #54 (the
baseline ADR-0011 already follows). Its second pull request closed a gap:
a prefix rule such as `Bash(gh pr merge:*)` doesn't match
`gh -R owner/repo pr merge`, where an option comes before the subcommand.

Options considered:
- **A. A committed `.claude/settings.json` with deny and ask rules in both
  plain and option-first forms, plus the two mode settings.** It applies to
  every session started in the repo, with a test that keeps it in place.
- **B. Instructions in `CLAUDE.md` only.** That's the current state; it
  depends on the agent following them.
- **C. A PreToolUse hook that parses commands.** It's stricter, but it's
  code to maintain, and the permission rules cover the gates.

## Decision
Option A. `.claude/settings.json` sets:
- `permissions.disableAutoMode` and `permissions.disableBypassPermissionsMode`
  to `"disable"` (both keys are confirmed in the Claude Code settings
  reference, 5 Nov 2026).
- **Deny:** `gh pr merge`, `gh pr review` (covers `--approve`), `git tag`,
  and `gh release create`, `edit`, `delete` and `upload` (`edit
  --draft=false` is how a release is published). Each one is in its plain
  form (`Bash(gh pr merge:*)`) and both option-first forms (`Bash(gh * pr
  merge)` and `Bash(gh * pr merge *)`). A trailing `*` matches the bare
  command only when it's the rule's only wildcard, which is why the pairs
  are needed. Also `Bash(rm -rf *)`, part of the new-project baseline: the
  dossier and vault live outside the repository, so a recursive force
  delete has no routine use here.
- **Ask:** `git push` (plain and option-first), `gh pr`, `gh api` and
  `python3`. These are asked rather than denied, because the agent pushes
  branches and opens pull requests in normal work.
- **No allow rules** in the shared file. Personal allows stay in each
  person's untracked `.claude/settings.local.json`.

`tests/test_agent_rules.py` requires both mode settings and every deny and
ask rule, checks that each option-first rule has its bare form, and that the
shared file has no allow rules.

## Consequences
- **A guardrail, not a sandbox.** The rules match command text. A command
  phrased another way, such as `uv run python` instead of `python3`, a shell
  alias, or a script that calls `gh`, isn't matched. The GitHub ruleset on
  `main` and the tag ruleset remain the real enforcement for merges, pushes
  to `main` and tags.
- **The mode settings are a team default.** They apply from the project
  file, but only managed settings make them binding; anyone can edit or
  delete a project file. Deny and ask rules apply without workspace
  trust, and an allow rule in a local file doesn't outrank them.
- Pushes to `main` and ruleset changes through `gh api -X PUT` are asked,
  not denied: a text pattern for them is easy to sidestep, so the prompt is
  the check.
- `git tag -l` (read-only) is blocked along with tag creation. Use
  `git describe` or `gh release list` instead.
- The agent now prompts before every `gh pr` command, including `create`
  and `view`.
- Revisit if the gates in `CLAUDE.md` change, or if a new approve or publish
  command is added.
