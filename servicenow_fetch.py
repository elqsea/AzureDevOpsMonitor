import requests
import json
import os
from datetime import datetime

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")

with open(CONFIG_FILE, "r", encoding="utf-8") as f:
    config = json.load(f)

SNOW_CFG   = config.get("servicenow", {})
INSTANCE   = SNOW_CFG.get("instance", "")
USERNAME   = SNOW_CFG.get("username", "")
PASSWORD   = SNOW_CFG.get("password", "")
QUERY      = SNOW_CFG.get("query", "active=true")
LIMIT      = SNOW_CFG.get("limit", 500)
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), config.get("output_dir", "output"))
INC_LATEST = os.path.join(OUTPUT_DIR, "inc_latest.json")

FIELDS = (
    "number,short_description,description,priority,state,"
    "category,assigned_to,sys_created_on,sys_updated_on"
)

SNOW_BASE = f"https://{INSTANCE}.service-now.com/api/now/table/incident"


def fetch_incidents():
    """Fetch incidents from ServiceNow Table API."""
    params = {
        "sysparm_query":  QUERY,
        "sysparm_fields": FIELDS,
        "sysparm_limit":  LIMIT,
        "sysparm_display_value": "true",
    }
    r = requests.get(
        SNOW_BASE,
        auth=(USERNAME, PASSWORD),
        params=params,
        headers={"Accept": "application/json"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("result", [])


def _load_existing_states():
    """Load status/notes/devops_id from the previous run to preserve manual edits."""
    if not os.path.exists(INC_LATEST):
        return {}
    with open(INC_LATEST, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {
        item["inc_number"]: {
            "status":    item.get("status", "pendiente"),
            "devops_id": item.get("devops_id"),
            "notes":     item.get("notes", ""),
        }
        for item in data.get("items", [])
    }


def _map_priority(raw):
    mapping = {"1": "1 - Crítica", "2": "2 - Alta", "3": "3 - Moderada",
               "4": "4 - Baja", "5": "5 - Planificación"}
    return mapping.get(str(raw), str(raw))


def _map_state(raw):
    mapping = {"1": "New", "2": "In Progress", "3": "On Hold",
               "6": "Resolved", "7": "Closed", "8": "Canceled"}
    return mapping.get(str(raw), str(raw))


def process_incidents(raw_items):
    existing = _load_existing_states()
    items = []
    for r in raw_items:
        num = r.get("number", "")
        prev = existing.get(num, {})
        items.append({
            "inc_number":   num,
            "title":        r.get("short_description", ""),
            "description":  r.get("description", ""),
            "priority":     _map_priority(r.get("priority", "")),
            "state":        _map_state(r.get("state", "")),
            "category":     r.get("category", ""),
            "assigned_to":  r.get("assigned_to", {}).get("display_value", "") if isinstance(r.get("assigned_to"), dict) else r.get("assigned_to", ""),
            "created_date": r.get("sys_created_on", ""),
            "updated_date": r.get("sys_updated_on", ""),
            "status":       prev.get("status", "pendiente"),
            "devops_id":    prev.get("devops_id"),
            "notes":        prev.get("notes", ""),
        })
    return items


def save_inc_json(items):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    payload = {
        "last_updated": datetime.now().isoformat(),
        "instance":     INSTANCE,
        "total_items":  len(items),
        "items":        items,
    }
    with open(INC_LATEST, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
    print(f"  INC JSON → {INC_LATEST}")
    return payload


def run_once():
    print(f"\nFetching incidents from ServiceNow ({INSTANCE})…")
    raw = fetch_incidents()
    print(f"  Found {len(raw)} incident(s)")
    items = process_incidents(raw)
    pending  = sum(1 for i in items if i["status"] == "pendiente")
    found    = sum(1 for i in items if i["status"] == "encontrado")
    print(f"  Pendientes: {pending} | Encontrados: {found}")
    save_inc_json(items)


if __name__ == "__main__":
    run_once()
