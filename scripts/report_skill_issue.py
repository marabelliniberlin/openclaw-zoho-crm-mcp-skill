#!/usr/bin/env python3
"""File a GitHub issue for a defect in the zoho-crm-mcp skill.

Searches open issues first so a caller links an existing report instead of
filing a duplicate, and redacts known credential and personal-data shapes
before anything leaves the machine.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

DEFAULT_REPO = "sprintberlin/openclaw-zoho-crm-mcp-skill"
REPO_ENV = "ZOHO_CRM_SKILL_REPO"

KINDS = (
    "catalog-stale",
    "helper-bug",
    "workflow-wrong",
    "action-missing",
    "coql-wrong",
    "docs-wrong",
)

_REDACTIONS = (
    (re.compile(r"https?://\S*zohomcp\.\S*", re.I), "[REDACTED_MCP_URL]"),
    (re.compile(r"https?://\S+/mcp/\S+"), "[REDACTED_MCP_URL]"),
    (re.compile(r"(?i)\bbearer\s+\S+"), "Bearer [REDACTED]"),
    (re.compile(r"(?i)\b(token|authorization|apikey|api_key)\b\s*[:=]\s*\S+"), r"\1 [REDACTED]"),
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"), "[REDACTED_EMAIL]"),
    (re.compile(r"\b\d{12,}\b"), "[REDACTED_ID]"),
)


def scrub(text):
    """Strip credential and personal-data shapes from caller-supplied text."""
    value = str(text or "")
    for pattern, replacement in _REDACTIONS:
        value = pattern.sub(replacement, value)
    return value.strip()


def resolve_repo(args=None):
    """Return the target repository slug."""
    explicit = getattr(args, "repo", None) if args is not None else None
    return explicit or os.environ.get(REPO_ENV) or DEFAULT_REPO


def run_gh(argv, timeout=30):
    """Run one gh command and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            ["gh", *argv], capture_output=True, text=True, timeout=timeout, check=False
        )
    except FileNotFoundError:
        return 127, "", "gh executable not found"
    except subprocess.TimeoutExpired:
        return 124, "", "gh call timed out"
    return result.returncode, result.stdout, result.stderr


def find_existing(repo, query, timeout=30):
    """Return the first open issue matching query, or None."""
    code, out, err = run_gh(
        [
            "issue",
            "list",
            "--repo",
            repo,
            "--state",
            "open",
            "--search",
            query,
            "--limit",
            "5",
            "--json",
            "number,title,url",
        ],
        timeout=timeout,
    )
    if code != 0:
        return {"error": err.strip() or "gh issue list failed"}
    try:
        found = json.loads(out or "[]")
    except json.JSONDecodeError:
        return {"error": "gh returned invalid JSON"}
    return found[0] if found else None


def build_body(args):
    """Render the issue body from scrubbed fields."""
    sections = [
        ("Kind", args.kind),
        ("Expected", scrub(args.expected)),
        ("Actual", scrub(args.actual)),
        ("Reproduce", scrub(args.repro)),
        ("Helper", scrub(args.helper)),
        ("Action", scrub(args.action)),
        ("Module", scrub(args.module)),
        ("Skill version", scrub(args.skill_version)),
    ]
    body = "\n\n".join(f"### {label}\n{value}" for label, value in sections if value)
    return (
        f"{body}\n\n---\nFiled by an agent using the zoho-crm-mcp skill. "
        "No customer data or MCP endpoint included."
    )


def create_issue(repo, title, body, labels, timeout=30):
    """Create the issue, retrying once without labels when a label is unknown."""
    argv = ["issue", "create", "--repo", repo, "--title", title, "--body", body]
    if labels:
        argv += ["--label", ",".join(labels)]
    code, out, err = run_gh(argv, timeout=timeout)
    if code != 0 and labels and "label" in err.lower():
        code, out, err = run_gh(
            ["issue", "create", "--repo", repo, "--title", title, "--body", body],
            timeout=timeout,
        )
    return code, out, err


def build_parser():
    parser = argparse.ArgumentParser(
        description="File a GitHub issue for a defect in the zoho-crm-mcp skill."
    )
    parser.add_argument("--title", required=True, help="one-line defect summary")
    parser.add_argument("--kind", required=True, choices=KINDS, help="defect category")
    parser.add_argument("--expected", help="what the skill documents or implies")
    parser.add_argument("--actual", help="what the live server or helper did")
    parser.add_argument("--repro", help="minimal steps, no customer data")
    parser.add_argument("--helper", help="helper script involved, e.g. scripts/list_contacts.py")
    parser.add_argument("--action", help="CRM Action involved, e.g. ZohoCRM_searchRecords")
    parser.add_argument("--module", help="CRM module involved, e.g. Deals")
    parser.add_argument("--skill-version", help="skill commit or version")
    parser.add_argument("--search", help="dedupe query (default: the title)")
    parser.add_argument("--label", action="append", default=[], help="repeatable issue label")
    parser.add_argument("--repo", help=f"target repo (default: {REPO_ENV} or {DEFAULT_REPO})")
    parser.add_argument("--force", action="store_true", help="file even when a match exists")
    parser.add_argument("--dry-run", action="store_true", help="print the issue without filing")
    parser.add_argument("--json", action="store_true", help="print JSON instead of text")
    parser.add_argument(
        "--timeout", type=int, default=30, help="gh call timeout in seconds (default: 30)"
    )
    return parser


def emit(payload, as_json):
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    elif payload.get("url"):
        print(f"{payload['status']}: {payload['url']}")
    else:
        print(payload.get("body") or payload.get("status", ""))


def main(argv=None):
    args = build_parser().parse_args(argv)
    repo = resolve_repo(args)
    title = scrub(args.title)
    if not title:
        print("Error: --title is empty after redaction", file=sys.stderr)
        return 1
    body = build_body(args)

    if args.dry_run:
        emit({"status": "dry-run", "repo": repo, "title": title, "body": body}, args.json)
        return 0

    if not args.force:
        existing = find_existing(repo, args.search or title, timeout=args.timeout)
        if isinstance(existing, dict) and existing.get("error"):
            print(f"Error: {existing['error']}", file=sys.stderr)
            return 1
        if existing:
            emit(
                {
                    "status": "existing",
                    "repo": repo,
                    "url": existing.get("url", ""),
                    "title": existing.get("title", ""),
                },
                args.json,
            )
            return 0

    code, out, err = create_issue(repo, title, body, args.label, timeout=args.timeout)
    if code != 0:
        print(f"Error: {err.strip() or 'gh issue create failed'}", file=sys.stderr)
        return 1
    emit({"status": "created", "repo": repo, "url": out.strip()}, args.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
