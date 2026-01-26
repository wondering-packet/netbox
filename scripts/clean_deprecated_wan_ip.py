# read the instrucitons.md for script overview & logic

import pynetbox
import urllib3
import json
import os
from datetime import date, datetime
from pprint import pprint
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Load credentials

NETBOX_URL = os.environ["NETBOX_URL"]
API_TOKEN = os.environ["NETBOX_TOKEN"]
RUN_ID = os.environ["RUN_ID"]

# intitialze netbox object
nb = pynetbox.api(NETBOX_URL, token=API_TOKEN)
nb.http_session.verify = False

# counter
records_processed_b = 0
# list to collect clean up logs
cleanup_logs = []

# create artifiact directory if it doens't exist:
folder_path = f"./artifacts-cleanup/{RUN_ID}"
os.makedirs(folder_path, exist_ok=True)
# function to collect artifacts:


def col_artifacts(artifacts, file_name):
    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    artifact_file = f"{folder_path}/{timestamp}_{file_name}"
    with open(artifact_file, "w") as f:
        json.dump(artifacts, f, indent=4)

# takes in last_seen value (str), normalizes it & returns how old the last seen is.


def last_seen_in_days(last_seen, address):
    if last_seen is None:
        return None
    else:
        try:
            last_seen_normalized = datetime.fromisoformat(
                str(last_seen)).date()
            return (date.today() - last_seen_normalized).days
        except Exception as e:
            print(
                f"Execption occured during last seen calculation for the address {address}, {type(e)}")
            print(e)
            return None


print("===============================================================")
print("CLEANUP workflow:\n")

for each_ip in nb.ipam.ip_addresses.filter(
        tag="external-sot-github", status="deprecated"):

    address = str(each_ip.address).strip()
    last_seen_days = last_seen_in_days(
        each_ip.custom_fields["last_seen"], str(each_ip.address).strip())
    tags = each_ip.tags

    print("-----------------------------------------------------")
    if last_seen_days is None:
        print(
            f"{address} -- Age: UNKNOWN days -- Requires review (last seen missing)")
        existing_slugs = []
        if tags:
            print(f"\t{address} -- existing tags: ")
            for each_tag in tags:
                print(f"\t\t{each_tag}")
                existing_slugs.append(each_tag.slug)
        if not "review-required" in existing_slugs:
            existing_slugs.append("review-required")
        payload = {"tags": [{"slug": each_tag}
                            for each_tag in existing_slugs]}

        each_ip.update(payload)
        cleanup_logs.append({
            "address": address,
            "action": "marked for review",
            "message": f"{address} -- Age: UNKNOWN days -- Requires review (last seen missing)"
        })
        records_processed_b += 1
    elif last_seen_days >= 90:
        each_ip.delete()
        print(
            f"{address} -- Age: {last_seen_days} days -- Deleted")
        cleanup_logs.append(
            {
                "address": address,
                "action": "deleted",
                "message": f"{address} -- Age: {last_seen_days} days -- Deleted"
            }
        )
        records_processed_b += 1
print("===============================================================")
print(f"Total records processed from NetBox: {records_processed_b}")
print("-----------------------------------------------------")
col_artifacts(cleanup_logs, "cleanup_logs.json")
