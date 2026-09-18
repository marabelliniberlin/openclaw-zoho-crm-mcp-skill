# Contributing

Contributions from humans and agents are explicitly welcome. Issues and pull requests are both wanted. Prefer a pull request when you can implement and verify the fix.

## Issue

Use an issue for a reproducible defect, incomplete documentation, a live-schema mismatch, a broken helper or workflow, incorrect COQL or field guidance, or a missing profile Action.

1. Search open issues and link an existing match.
2. Otherwise run `scripts/report_skill_issue.py`; use `--help` for its interface.
3. State expected and actual behavior plus minimal reproduction details.
4. Return the issue URL.

Do not file skill issues for endpoint, authentication or profile setup, rate limits, transient service failures, timeouts, organization-specific fields, or unsupported Zoho CRM operations.

## Pull request

Use a pull request for a verified improvement or fix.

1. Branch from `main` and keep the change focused.
2. Add or update tests for behavior changes.
3. Run `python3 -m unittest discover -s tests`.
4. Run the skill validator.
5. Open the pull request with `gh pr create` and link its issue when present.

## Requirements

- Use an authenticated GitHub CLI (`gh`) with the required repository access.
- Never submit MCP URLs, tokens, record content, contacts, or customer data.
- Keep `SKILL.md` short and imperative. Put reference material in `references/` and deterministic logic in `scripts/`.
- Preserve compatibility with `mcporter` and existing helper interfaces.
