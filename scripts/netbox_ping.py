import os
import sys
import requests

NETBOX_URL = os.environ.get("NETBOX_URL")
NETBOX_TOKEN = os.environ.get("NETBOX_TOKEN")

if not NETBOX_URL or not NETBOX_TOKEN:
    print("Missing NETBOX_URL or NETBOX_TOKEN env vars.")
    sys.exit(2)

url = f"{NETBOX_URL.rstrip('/')}/api/"
headers = {"Authorization": f"Token {NETBOX_TOKEN}"}

r = requests.get(url, headers=headers, timeout=15, verify=False)
print("Status:", r.status_code)
print("Body (first 200 chars):", r.text[:200])

r.raise_for_status()
print("✅ NetBox API reachable + token accepted.")
