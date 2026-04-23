"""
Extractor de cookies de sesión de ServiceNow (SSO).

Uso:
    python get_snow_cookies.py

Captura TODAS las cookies del dominio ServiceNow (necesario para SSO con
proveedores externos como Okta, ADFS, F5, etc.) y las guarda en cookies.json.
"""
import json
import os
import urllib.request

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE  = os.path.join(BASE_DIR, "config.json")
COOKIES_FILE = os.path.join(BASE_DIR, "cookies.json")

# Cookies mínimas esperadas para confirmar sesión activa
SESSION_COOKIES = {"glide_session_store", "JSESSIONID"}


def load_instance():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        return cfg.get("servicenow", {}).get("instance", "")
    except Exception:
        return ""


def try_auto_extract(instance):
    """Extrae TODAS las cookies del dominio desde Chrome o Edge."""
    try:
        import browser_cookie3
    except ImportError:
        print("  [INFO] browser-cookie3 no instalado — usando modo manual.")
        print("         Para instalarlo: pip install browser-cookie3\n")
        return None

    domain = f"{instance}.service-now.com" if instance else "service-now.com"

    for browser_name, loader in [("Chrome", browser_cookie3.chrome), ("Edge", browser_cookie3.edge)]:
        try:
            jar = loader(domain_name=domain)
            found = {c.name: c.value for c in jar}
            if not found:
                continue

            has_session = SESSION_COOKIES & set(found.keys())
            print(f"  [OK] {len(found)} cookie(s) encontradas en {browser_name}.")
            if not has_session:
                print(f"  [WARN] No se encontraron cookies de sesión ({SESSION_COOKIES}).")
                print("         ¿Tienes sesión activa en ServiceNow en este browser?")
            return found
        except Exception as exc:
            print(f"  [WARN] No se pudo leer {browser_name}: {exc}")

    print("  [WARN] No se encontraron cookies automáticamente.")
    return None


def manual_input(instance):
    """
    Modo manual: el usuario pega el header Cookie completo y el X-UserToken
    desde DevTools Network tab.
    """
    print("\nModo manual — sigue estos pasos en Chrome/Edge:")
    print(f"  1. Abre {instance}.service-now.com con sesión activa")
    print("  2. Abre DevTools (F12) → pestaña 'Network'")
    print("  3. Recarga la página (F5)")
    print("  4. Haz clic en cualquier peticion a service-now.com")
    print("  5. En 'Headers' → sección 'Request Headers'")
    print()

    # --- Cookie header ---
    print("  [Paso A] Copia el valor completo de la línea 'cookie:'")
    print("  (Ejemplo: glide_session_store=ABC; JSESSIONID=XYZ; BIGipServer=...)")
    print()
    while True:
        raw = input("  cookie> ").strip()
        if raw:
            break
        print("  [ERROR] No puede estar vacío.")

    cookies = {}
    for part in raw.split(";"):
        part = part.strip()
        if "=" in part:
            name, _, value = part.partition("=")
            cookies[name.strip()] = value.strip()
    print(f"  Parseadas {len(cookies)} cookie(s).")

    # --- X-UserToken ---
    print()
    print("  [Paso B] Busca la línea 'x-usertoken:' en esos mismos Request Headers")
    print("  Si no aparece, busca en otra petición XHR/Fetch del mismo dominio.")
    print("  Déjalo vacío si no lo encuentras.")
    user_token = input("  x-usertoken> ").strip()
    if user_token:
        print("  X-UserToken capturado.")
    else:
        print("  [WARN] Sin X-UserToken — la API podría rechazar la sesión (401).")

    return cookies, user_token


def verify_cookies(cookies, user_token, instance):
    """Petición de prueba para validar las cookies."""
    try:
        cookie_header = "; ".join(f"{k}={v}" for k, v in cookies.items())
        url = (
            f"https://{instance}.service-now.com"
            "/api/now/table/incident?sysparm_limit=1&sysparm_fields=number"
        )
        headers = {"Cookie": cookie_header, "Accept": "application/json"}
        if user_token:
            headers["X-UserToken"] = user_token
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            if "result" in data:
                print("  [OK] Verificación exitosa — las cookies son válidas.")
                return True
            print("  [WARN] Respuesta inesperada:", data)
            return False
    except urllib.error.HTTPError as exc:
        print(f"  [ERROR] HTTP {exc.code} — cookies o token inválidos.")
        print("          Verifica que tengas sesión activa y que el X-UserToken sea correcto.")
        return False
    except Exception as exc:
        print(f"  [ERROR] {exc}")
        return False


def save_cookies(cookies, user_token, instance):
    payload = {"instance": instance, "cookies": cookies, "user_token": user_token}
    with open(COOKIES_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"  Cookies guardadas en: {COOKIES_FILE}")


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
    auto = try_auto_extract(instance)
    if auto:
        cookies = auto
        user_token = ""
    else:
        # 2. Fallback manual
        cookies, user_token = manual_input(instance)

    # 3. Verificar
    if instance:
        print("\n  Verificando cookies contra la API...")
        ok = verify_cookies(cookies, user_token, instance)
        if not ok:
            print("\n  Guardando de todas formas — puedes intentar el monitor y ver si funciona.")
    else:
        print("  [SKIP] Verificación omitida — configura 'instance' en config.json")

    # 4. Guardar
    save_cookies(cookies, user_token, instance)

    print("\n  Siguiente paso:")
    print('  1. En config.json: "use_cookie_auth": true, "use_dummy_data": false')
    print("  2. Ejecuta: python snow_monitor.py  (o run_snow_monitor.bat)")
    print("\n  Las cookies expiran cuando cierras sesión en el browser.")
    print("  Vuelve a ejecutar este script cuando caduquen.\n")


if __name__ == "__main__":
    main()
