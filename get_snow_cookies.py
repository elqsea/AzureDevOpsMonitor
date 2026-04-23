"""
Extractor de cookies de sesión de ServiceNow (SSO).

Uso:
    python get_snow_cookies.py

Guarda glide_session_store y JSESSIONID en cookies.json.
Requiere haber iniciado sesión en ServiceNow en Chrome o Edge.
"""
import json
import os
import sys

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE  = os.path.join(BASE_DIR, "config.json")
COOKIES_FILE = os.path.join(BASE_DIR, "cookies.json")

REQUIRED_COOKIES = ["glide_session_store", "JSESSIONID"]


def load_instance():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        return cfg.get("servicenow", {}).get("instance", "")
    except Exception:
        return ""


def try_auto_extract(instance):
    """Intenta extraer cookies automáticamente desde Chrome o Edge."""
    try:
        import browser_cookie3
    except ImportError:
        print("  [INFO] browser-cookie3 no instalado — usando modo manual.")
        print("         Para instalarlo: pip install browser-cookie3\n")
        return None

    domain = f"{instance}.service-now.com" if instance else "service-now.com"
    found = {}

    for browser_name, loader in [("Chrome", browser_cookie3.chrome), ("Edge", browser_cookie3.edge)]:
        try:
            jar = loader(domain_name=domain)
            for cookie in jar:
                if cookie.name in REQUIRED_COOKIES:
                    found[cookie.name] = cookie.value
            if len(found) == len(REQUIRED_COOKIES):
                print(f"  [OK] Cookies encontradas en {browser_name}.")
                return found
            found.clear()
        except Exception as exc:
            print(f"  [WARN] No se pudo leer {browser_name}: {exc}")

    if found:
        missing = [c for c in REQUIRED_COOKIES if c not in found]
        print(f"  [WARN] Solo se encontraron algunas cookies. Faltan: {missing}")
    else:
        print("  [WARN] No se encontraron cookies automáticamente.")
    return None


def manual_input():
    """Solicita las cookies manualmente al usuario."""
    print("\nModo manual — abre DevTools (F12) → Application → Cookies")
    print(f"→ Busca el dominio de tu instancia ServiceNow\n")

    cookies = {}
    for name in REQUIRED_COOKIES:
        while True:
            value = input(f"  Pega el valor de '{name}': ").strip()
            if value:
                cookies[name] = value
                break
            print("  [ERROR] El valor no puede estar vacío.")
    return cookies


def save_cookies(cookies, instance):
    payload = {
        "instance": instance,
        "cookies":  cookies,
    }
    with open(COOKIES_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"\n  Cookies guardadas en: {COOKIES_FILE}")


def verify_cookies(cookies, instance):
    """Hace una petición de prueba para validar que las cookies funcionan."""
    try:
        import urllib.request
        cookie_header = "; ".join(f"{k}={v}" for k, v in cookies.items())
        url = f"https://{instance}.service-now.com/api/now/table/incident?sysparm_limit=1&sysparm_fields=number"
        req = urllib.request.Request(url, headers={
            "Cookie": cookie_header,
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            if "result" in data:
                print("  [OK] Verificación exitosa — las cookies son válidas.")
                return True
            print("  [WARN] Respuesta inesperada:", data)
            return False
    except Exception as exc:
        print(f"  [ERROR] Verificación fallida: {exc}")
        print("  Asegúrate de haber iniciado sesión en ServiceNow antes de ejecutar este script.")
        return False


def main():
    print("=" * 52)
    print("  Extractor de Cookies — ServiceNow SSO")
    print("=" * 52)

    instance = load_instance()
    if instance:
        print(f"  Instancia: {instance}.service-now.com\n")
    else:
        print("  [WARN] No se encontró 'instance' en config.json\n")

    # 1. Intento automático
    cookies = try_auto_extract(instance)

    # 2. Fallback manual
    if not cookies:
        cookies = manual_input()

    # 3. Verificar
    if instance:
        print("\n  Verificando cookies contra la API...")
        verify_cookies(cookies, instance)
    else:
        print("\n  [SKIP] Verificación omitida — configura 'instance' en config.json")

    # 4. Guardar
    save_cookies(cookies, instance)

    print("\n  Siguiente paso:")
    print('  1. Abre config.json y pon "use_cookie_auth": true')
    print('  2. Ejecuta: python snow_monitor.py')
    print("\n  Las cookies expiran con tu sesión.")
    print("  Vuelve a ejecutar este script cuando caduquen.\n")


if __name__ == "__main__":
    main()
