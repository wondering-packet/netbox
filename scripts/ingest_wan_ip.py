import pynetbox
import urllib3
import json
import os
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# load credentials from github secrets

NETBOX_URL = os.environ["NETBOX_URL"]
API_TOKEN = os.environ["NETBOX_TOKEN"]

# intitialze netbox object
nb = pynetbox(NETBOX_URL, token=API_TOKEN)
nb.http_session.verify = False

# testing block

response = nb.tenancy.tenants.all()
all_tenants = list(response)

for each_tenant in all_tenants:
    print(
        f"ID: {each_tenant.id}\tName: {each_tenant.name}\tDescription: {each_tenant.description}")
