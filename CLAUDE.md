# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

Automated monitor that pulls all Work Items from an Azure DevOps project via the REST API, extracts **RCA** and **Timeline** data (from custom fields, description, or comments), and produces:
- `output/devops_latest.json` — always-fresh JSON snapshot
- `output/devops_latest.xlsx` — Excel with two sheets: full list + RCA-only summary
- `output/dashboard.html` — self-contained HTML dashboard with the JSON data embedded

## Setup & Run

```bash
# Install dependencies (one time)
pip install -r requirements.txt

# Run once (fetch + save outputs)
python -c "import monitor_devops; monitor_devops.run_once()"

# Run continuous loop (default 30 min interval)
python monitor_devops.py
```

On Windows, double-click `run_once.bat` or `run_monitor.bat` instead.

## Configuration (`config.json`)

| Key | Description |
|---|---|
| `pat_token` | Azure DevOps Personal Access Token (needs *Work Items Read*) |
| `organization` | Azure DevOps org name (from `dev.azure.com/<org>`) |
| `project` | Project name inside the org |
| `interval_minutes` | Loop interval; default `30` |
| `output_dir` | Where files are saved; default `"output"` |
| `rca_field_keywords` | Lowercase substrings matched against field names and description to detect RCA |
| `timeline_field_keywords` | Same, for Timeline detection |
| `work_item_types` | Filter by type (e.g. `["User Story", "Bug"]`); empty list = all types |

## Architecture

```
monitor_devops.py
  ├── fetch_all_ids()          — WIQL query → list of work item IDs
  ├── fetch_items_batch()      — batched GET /workitems?$expand=All (200/req)
  ├── fetch_item_comments()    — GET /workitems/{id}/comments
  ├── extract_rca_timeline()   — searches field names → description → comments
  ├── process_items()          — maps raw API response to clean dicts
  ├── save_json()              — writes timestamped + latest JSON
  ├── save_excel()             — writes timestamped + latest XLSX (2 sheets)
  ├── save_dashboard()         — injects JSON blob into dashboard.html template
  └── run_once() / main()      — orchestrates one pass / infinite loop
```

**RCA/Timeline extraction order:**
1. Field name contains a keyword (e.g. `Custom.RCA`) — highest confidence
2. Keyword found inside `System.Description` text — 500-char window extracted
3. Keyword found inside any comment — same windowing

**Dashboard (`dashboard.html`)** is a template with two sentinel comments:
```
// DATA_START
const DEVOPS_DATA = {...};
// DATA_END
```
`save_dashboard()` uses `re.sub` to replace the block between those sentinels with fresh data each run. The generated file is written to `output/dashboard.html` and is fully self-contained (open directly in browser, no server needed).

## Azure DevOps API

- Auth: HTTP Basic with empty username and PAT as password (`base64(":{PAT}")`)
- WIQL endpoint: `POST /wit/wiql?api-version=7.2-preview.2`
- Items endpoint: `GET /wit/workitems?ids={csv}&$expand=All&api-version=7.2-preview.3`
- Comments endpoint: `GET /wit/workitems/{id}/comments?api-version=7.2-preview.4`
- Max 200 IDs per items request — `fetch_items_batch` handles batching automatically

Official reference: https://learn.microsoft.com/en-us/rest/api/azure/devops/wit

## Development Rules

**Before any change to API endpoints, parameters, or api-version values, consult the official Microsoft documentation:**
- WIQL: https://learn.microsoft.com/en-us/rest/api/azure/devops/wit/wiql/query-by-wiql
- Work Items: https://learn.microsoft.com/en-us/rest/api/azure/devops/wit/work-items/list
- Comments: https://learn.microsoft.com/en-us/rest/api/azure/devops/wit/comments/get-comments

This applies to: endpoint paths, query parameters, `api-version` values, request/response field names, and authentication headers. Always verify against the docs before modifying `monitor_devops.py`.
