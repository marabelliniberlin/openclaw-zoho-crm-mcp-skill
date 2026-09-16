# Multi-account endpoint profiles

The helper CLIs support one simple default endpoint and any number of named Zoho accounts. This is runtime-neutral and works anywhere Python and `mcporter` are available, including OpenClaw and Hermes.

## Resolution order

The MCP endpoint is selected in this order:

1. `--mcp-url URL`
2. `--profile NAME`
3. app-specific or generic profile environment variable
4. app-specific endpoint environment variable

Profile selection uses `--profile`, then `ZOHO_<APP>_MCP_PROFILE`, then `ZOHO_MCP_PROFILE`. The profile file uses `--profiles-file`, then `ZOHO_MCP_PROFILES_FILE`, then `~/.config/zoho-mcp/profiles.json`.

Endpoint environment variables:

- CRM: `ZOHO_CRM_MCP_URL`, then legacy `ZOHO_MCP_URL`
- People: `ZOHO_PEOPLE_MCP_URL`
- Books: `ZOHO_BOOKS_MCP_URL`

Books organization IDs use `--organization-id`, then the selected profile's `organization_id`, then `ZOHO_BOOKS_ORGANIZATION_ID`, then `ZOHO_ORGANIZATION_ID`.

## Profile file

Create `~/.config/zoho-mcp/profiles.json`:

```json
{
  "version": 1,
  "profiles": {
    "acme": {
      "services": {
        "crm": {"env": "ACME_CRM_MCP_URL"},
        "people": {"env": "ACME_PEOPLE_MCP_URL"},
        "books": {
          "env": "ACME_BOOKS_MCP_URL",
          "organization_id": "123456789"
        }
      }
    },
    "acme-subsidiary": {
      "services": {
        "people": {"url_file": "secrets/acme-subsidiary-people.url"}
      }
    }
  }
}
```

Each service must define exactly one endpoint source:

- `env`: read the URL from the named environment variable. Recommended when a secret manager injects environment variables.
- `url_file`: read the URL from a local file. Relative paths are resolved from the profile file's directory.
- `url`: store the endpoint directly in the JSON file. Supported for small local installations, but the file then contains a credential.

Lock down local files and never commit them:

```bash
chmod 700 ~/.config/zoho-mcp
chmod 600 ~/.config/zoho-mcp/profiles.json
```

## Usage

```bash
# Single account: no profile needed
export ZOHO_PEOPLE_MCP_URL="https://your-org-zoho-people.example/mcp/YOUR_TOKEN/message"
python3 scripts/list_employees.py

# Named account
python3 scripts/list_employees.py --profile acme

# Select a profile for every compatible helper in one process
export ZOHO_MCP_PROFILE=acme
python3 scripts/list_employees.py

# One-off override
python3 scripts/list_employees.py --mcp-url "https://your-org-zoho-people.example/mcp/YOUR_TOKEN/message"
```

Avoid `--mcp-url` on shared systems because command-line arguments can appear in shell history and process listings. Prefer an injected environment variable, `env`, or `url_file`.

## Agent routing rule

When a task names a customer, subsidiary, or organization, select the matching profile explicitly. Never fall back to another account after an authentication, scope, or lookup error. Before writes, verify the target account with a harmless read or live tool discovery.
