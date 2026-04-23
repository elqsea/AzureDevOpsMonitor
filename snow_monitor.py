"""
ServiceNow Live Monitor — HTTP server + background poller.
Run: python snow_monitor.py
Open: http://localhost:8765
"""
import base64
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE  = os.path.join(BASE_DIR, "config.json")
COOKIES_FILE = os.path.join(BASE_DIR, "cookies.json")
DASHBOARD    = os.path.join(BASE_DIR, "dashboard.html")

DUMMY_ITEMS = [
    {
        "number": "INC0099001",
        "short_description": "Caída del servicio de autenticación en producción",
        "priority": "1", "priority_label": "1 - Crítica",
        "state": "In Progress", "assigned_to": "Luis García",
        "category": "Software", "urgency": "1", "impact": "1",
        "caller_id": "María López",
        "sys_created_on": "2026-04-22 08:15:00",
        "sys_updated_on": "2026-04-22 09:40:00",
    },
    {
        "number": "INC0099002",
        "short_description": "Error de timeout en pagos con tarjeta Visa",
        "priority": "2", "priority_label": "2 - Alta",
        "state": "New", "assigned_to": "Carlos Mendoza",
        "category": "Software", "urgency": "1", "impact": "2",
        "caller_id": "Pedro Ruiz",
        "sys_created_on": "2026-04-22 09:00:00",
        "sys_updated_on": "2026-04-22 09:05:00",
    },
    {
        "number": "INC0099003",
        "short_description": "Reportes lentos en horas pico — tiempo >10s",
        "priority": "3", "priority_label": "3 - Moderada",
        "state": "In Progress", "assigned_to": "Ana Torres",
        "category": "Performance", "urgency": "2", "impact": "2",
        "caller_id": "Sofía Vega",
        "sys_created_on": "2026-04-21 14:30:00",
        "sys_updated_on": "2026-04-22 08:00:00",
    },
]

PRIORITY_MAP = {"1": "1 - Crítica", "2": "2 - Alta", "3": "3 - Moderada",
                "4": "4 - Baja", "5": "5 - Planificación"}
STATE_MAP    = {"1": "New", "2": "In Progress", "3": "On Hold",
                "6": "Resolved", "7": "Closed", "8": "Canceled"}


def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    snow = cfg.get("servicenow", {})
    if not snow:
        print("[ERROR] config.json no tiene la sección 'servicenow'.")
        sys.exit(1)
    return cfg


def _load_cookies():
    """Load session cookies and X-UserToken saved by get_snow_cookies.py."""
    if not os.path.exists(COOKIES_FILE):
        raise FileNotFoundError(
            "cookies.json no encontrado. "
            "Ejecuta: python get_snow_cookies.py"
        )
    with open(COOKIES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    cookies = data.get("cookies", {})
    if not cookies:
        raise ValueError("cookies.json está vacío. Ejecuta: python get_snow_cookies.py")
    cookie_header = "; ".join(f"{k}={v}" for k, v in cookies.items())
    user_token    = data.get("user_token", "")
    return cookie_header, user_token


def fetch_incidents(cfg):
    snow = cfg["servicenow"]
    if cfg.get("use_dummy_data"):
        return DUMMY_ITEMS

    instance = snow["instance"]
    query    = snow.get("query", "active=true^stateNOT IN6,7,8")
    limit    = snow.get("limit", 500)

    if cfg.get("use_cookie_auth"):
        return _fetch_via_jsonv2(instance, query, limit)
    else:
        return _fetch_via_rest(snow, instance, query, limit)


def _fetch_via_jsonv2(instance, query, limit):
    """
    Usa la API JSONv2 legacy de ServiceNow, que acepta cookies de sesion SSO
    sin requerir x-usertoken ni Basic Auth.
    URL: /incident.do?JSONv2&sysparm_action=getRecords&...
    """
    cookie_header, user_token = _load_cookies()
    params = (
        f"sysparm_action=getRecords"
        f"&sysparm_query={urllib.request.quote(query)}"
        f"&sysparm_limit={limit}"
    )
    url = f"https://{instance}.service-now.com/incident.do?JSONv2&{params}"
    headers = {
        "Cookie":  cookie_header,
        "Accept":  "application/json",
        "Referer": f"https://{instance}.service-now.com/",
    }
    if user_token:
        headers["X-UserToken"] = user_token

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())
            return data.get("records", [])
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise RuntimeError(
                f"Error {exc.code}: sesion expirada o sin permisos. "
                "Ejecuta: python get_snow_cookies.py"
            ) from exc
        raise


def _fetch_via_rest(snow, instance, query, limit):
    """Autenticacion Basic Auth para instancias sin SSO."""
    fields = snow.get(
        "fields",
        "number,short_description,priority,state,assigned_to,"
        "category,urgency,impact,caller_id,sys_created_on,sys_updated_on",
    )
    params = (
        f"sysparm_query={urllib.request.quote(query)}"
        f"&sysparm_fields={urllib.request.quote(fields)}"
        f"&sysparm_limit={limit}"
        f"&sysparm_display_value=true"
    )
    url = f"https://{instance}.service-now.com/api/now/table/incident?{params}"
    username = snow.get("username", "")
    password = snow.get("password", "")
    token    = base64.b64encode(f"{username}:{password}".encode()).decode()
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Basic {token}", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())["result"]


def _display(field):
    # REST API devuelve {"display_value": ..., "value": ...}
    # JSONv2 devuelve strings directamente
    if isinstance(field, dict):
        return field.get("display_value") or field.get("value", "")
    return str(field or "")


def process_incidents(raw):
    items = []
    for r in raw:
        pri_raw  = _display(r.get("priority", ""))
        pri_num  = str(pri_raw).split(" ")[0] if pri_raw else ""
        state_raw = _display(r.get("state", ""))

        items.append({
            "number":            _display(r.get("number", "")),
            "short_description": _display(r.get("short_description", "")),
            "priority":          pri_num,
            "priority_label":    PRIORITY_MAP.get(pri_num, pri_raw),
            "state":             STATE_MAP.get(state_raw, state_raw),
            "assigned_to":       _display(r.get("assigned_to", "")),
            "category":          _display(r.get("category", "")),
            "urgency":           _display(r.get("urgency", "")),
            "impact":            _display(r.get("impact", "")),
            "caller_id":         _display(r.get("caller_id", "")),
            "sys_created_on":    _display(r.get("sys_created_on", "")),
            "sys_updated_on":    _display(r.get("sys_updated_on", "")),
        })
    return items


def write_snow_latest(items, output_dir, cfg, error=None):
    os.makedirs(output_dir, exist_ok=True)
    payload = {
        "last_updated":  datetime.now().isoformat(timespec="seconds"),
        "instance":      cfg["servicenow"].get("instance", "dummy"),
        "total_items":   len(items),
        "fetch_status":  "error" if error else "ok",
        "error":         error,
        "items":         items,
    }
    dest = os.path.join(output_dir, "snow_latest.json")
    tmp  = dest + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
    os.replace(tmp, dest)
    return dest


def poll_loop(cfg, output_dir):
    interval = cfg["servicenow"].get("poll_interval_seconds", 30)
    while True:
        time.sleep(interval)
        try:
            raw   = fetch_incidents(cfg)
            items = process_incidents(raw)
            write_snow_latest(items, output_dir, cfg)
            ts = datetime.now().strftime("%H:%M:%S")
            mode = "[dummy]" if cfg.get("use_dummy_data") else ""
            print(f"  [{ts}] Poll OK — {len(items)} incident(s) {mode}")
        except Exception as exc:
            print(f"  [WARN] Poll error: {exc}")
            try:
                write_snow_latest([], output_dir, cfg, error=str(exc))
            except Exception:
                pass


class SnowHandler(BaseHTTPRequestHandler):
    output_dir = ""

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/":
            self._serve_file(DASHBOARD, "text/html; charset=utf-8")
        elif path == "/snow":
            self._serve_snow_json()
        elif path == "/health":
            self._send_json({"status": "ok", "ts": datetime.now().isoformat()})
        else:
            self.send_error(404)

    def _serve_file(self, filepath, content_type):
        try:
            with open(filepath, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except FileNotFoundError:
            self.send_error(404, f"File not found: {filepath}")

    def _serve_snow_json(self):
        snow_path = os.path.join(self.output_dir, "snow_latest.json")
        if os.path.exists(snow_path):
            with open(snow_path, "rb") as f:
                data = f.read()
        else:
            data = json.dumps(
                {"items": [], "fetch_status": "error", "error": "No data yet — first poll pending"}
            ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache, no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, obj):
        data = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"  [{ts}] {self.address_string()} {fmt % args}")


def main():
    cfg        = load_config()
    snow       = cfg["servicenow"]
    port       = snow.get("server_port", 8765)
    output_dir = os.path.join(BASE_DIR, cfg.get("output_dir", "output"))

    print("=" * 52)
    print("  ServiceNow Monitor en Vivo")
    print(f"  Instancia : {snow.get('instance','—')} {'[DUMMY]' if cfg.get('use_dummy_data') else ''}")
    print(f"  Intervalo : {snow.get('poll_interval_seconds', 30)}s")
    print(f"  Puerto    : {port}")
    print("=" * 52)

    # First blocking poll so first page load has data
    print("  Primer poll...")
    try:
        raw   = fetch_incidents(cfg)
        items = process_incidents(raw)
        dest  = write_snow_latest(items, output_dir, cfg)
        print(f"  {len(items)} incident(s) → {dest}")
    except Exception as exc:
        print(f"  [WARN] Primer poll fallido: {exc}")
        write_snow_latest([], output_dir, cfg, error=str(exc))

    # Background poller thread
    t = threading.Thread(target=poll_loop, args=(cfg, output_dir), daemon=True)
    t.start()

    # HTTP server
    SnowHandler.output_dir = output_dir
    server = HTTPServer(("", port), SnowHandler)
    print(f"\n  Dashboard → http://localhost:{port}")
    print(f"  Datos     → http://localhost:{port}/snow")
    print(f"  Health    → http://localhost:{port}/health")
    print("\n  Ctrl+C para detener.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Monitor detenido.")


if __name__ == "__main__":
    main()
