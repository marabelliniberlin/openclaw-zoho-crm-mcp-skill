#!/usr/bin/env python3
"""Build a correct Zoho CRM record URL for any module.

Resolves the org (zgid) via getOrganization and the module tab name via
getModules, then prints the record permalink. Never hand-assemble these
URLs: the tab segment is not always the module api_name (Events -> Meetings,
Sales_Orders -> SalesOrders, custom modules -> CustomModuleN).

Setup:
  export ZOHO_CRM_MCP_URL="https://your-org-zoho-crm-xxxxx.zohomcp.eu/mcp/YOUR_TOKEN/message"

Usage:
  python3 scripts/record_url.py Leads 407625000068467001
  python3 scripts/record_url.py Deals 407625000012345678 --json
  python3 scripts/record_url.py Events 407625000012345678 --dc com
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from mcp_endpoint import EndpointResolutionError, EndpointSelector, add_endpoint_arguments

ENDPOINT = EndpointSelector("crm", ("ZOHO_CRM_MCP_URL", "ZOHO_MCP_URL"))

DATA_CENTERS = ("eu", "com", "in", "com.au", "com.cn", "jp", "sa", "com.br")


def positive_int(value):
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def record_id(value):
    cleaned = value.strip()
    if not cleaned.isdigit():
        raise argparse.ArgumentTypeError(
            "record ID must be the numeric Zoho CRM record id (digits only)"
        )
    return cleaned


def data_center(value):
    cleaned = value.strip().lower()
    if cleaned not in DATA_CENTERS:
        raise argparse.ArgumentTypeError(
            "data center must be one of: " + ", ".join(DATA_CENTERS)
        )
    return cleaned


def build_parser():
    parser = argparse.ArgumentParser(
        description="Build a correct Zoho CRM record URL (resolves zgid and tab name)."
    )
    parser.add_argument(
        "module",
        help="CRM module api_name (e.g. Leads, Contacts, Deals, Events)",
    )
    parser.add_argument(
        "record_id",
        type=record_id,
        help="numeric CRM record id",
    )
    parser.add_argument(
        "--dc",
        type=data_center,
        default="eu",
        metavar="DC",
        help="Zoho data center domain suffix (default: eu)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print JSON with url, zgid, module, and tab name",
    )
    parser.add_argument(
        "--timeout",
        type=positive_int,
        default=30,
        help="MCP call timeout in seconds (default: 30)",
    )
    add_endpoint_arguments(parser)
    return parser


def mcporter_call(tool, args, timeout=30):
    try:
        mcp_url = ENDPOINT.get()
    except EndpointResolutionError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    cmd = [
        "mcporter",
        "call",
        f"{mcp_url}.{tool}",
        "--args",
        json.dumps(args, ensure_ascii=False),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    except FileNotFoundError:
        return {"error": "mcporter executable not found"}
    except subprocess.TimeoutExpired:
        return {"error": "mcporter call timed out"}

    if result.returncode != 0:
        return {"error": result.stderr.strip() or "mcporter call failed"}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"error": result.stdout + result.stderr}


def unwrap(result, key):
    """Return the list under data.<key> or <key> across MCP envelope variants."""
    if not isinstance(result, dict):
        return []
    payload = result.get("data", result)
    if isinstance(payload, dict):
        entries = payload.get(key)
    else:
        entries = None
    if not isinstance(entries, list):
        return []
    return entries


def fetch_zgid(timeout):
    result = mcporter_call("ZohoCRM_getOrganization", {}, timeout=timeout)
    if isinstance(result, dict) and result.get("error"):
        raise RuntimeError(f"getOrganization failed: {result['error']}")
    for org in unwrap(result, "org"):
        zgid = org.get("zgid")
        if zgid:
            return str(zgid)
    raise RuntimeError("getOrganization returned no zgid")


def fetch_module(module_api_name, timeout):
    # No query_params on purpose: the fields filter is rejected by the live API.
    result = mcporter_call("ZohoCRM_getModules", {}, timeout=timeout)
    if isinstance(result, dict) and result.get("error"):
        raise RuntimeError(f"getModules failed: {result['error']}")
    wanted = module_api_name.strip().lower()
    for module in unwrap(result, "modules"):
        if str(module.get("api_name", "")).lower() == wanted:
            tab_name = module.get("module_name") or module.get("api_name")
            return str(tab_name), str(module.get("api_name"))
    raise RuntimeError(f"module '{module_api_name}' not found in getModules")


def build_url(dc, zgid, tab_name, record_id_value):
    return f"https://crm.zoho.{dc}/crm/org{zgid}/tab/{tab_name}/{record_id_value}"


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    ENDPOINT.configure(args)

    try:
        zgid = fetch_zgid(args.timeout)
        tab_name, api_name = fetch_module(args.module, args.timeout)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    url = build_url(args.dc, zgid, tab_name, args.record_id)

    if args.json:
        print(
            json.dumps(
                {
                    "url": url,
                    "zgid": zgid,
                    "module": api_name,
                    "tab_name": tab_name,
                    "record_id": args.record_id,
                },
                ensure_ascii=False,
            )
        )
    else:
        print(url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
