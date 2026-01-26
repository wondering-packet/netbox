import os
import sys
import requests

NETBOX_URL = os.environ["NETBOX_URL"]
API_TOKEN = os.environ["NETBOX_TOKEN"]

if not NETBOX_URL or not API_TOKEN:
    print("Missing NETBOX_URL or NETBOX_TOKEN env vars.")
    sys.exit(2)

url = f"{NETBOX_URL.rstrip('/')}/api/"
headers = {"Authorization": f"Token {API_TOKEN}"}

r = requests.get(url, headers=headers, timeout=15, verify=False)
print("Status:", r.status_code)
print("Body (first 200 chars):", r.text[:200])

r.raise_for_status()
print("SUCCESS: NetBox API reachable & token accepted.")
