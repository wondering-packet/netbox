# read the instrucitons.md for script overview & logic

import pynetbox
import urllib3
import json
import os
import ipaddress
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

### ---load data to build A---###
with open("./data/wan_ips.json", "r") as f:
    dataset_a_source = json.load(f)
    # pprint(dataset_a)

# loading relevent data from the source data into the dataset A list.
# this list will be used to create/update IP in netbox.
dataset_a = []
records_processed_a = 0
for platform, ip_data in dataset_a_source.items():
    if platform in {"meraki", "aruba"}:
        for each_ip in ip_data:
            each_ip_filtered = {}
            each_ip_filtered["platform"] = platform
            address = each_ip["ip"].strip()
            if "/" in address:
                normalized_address = str(ipaddress.ip_interface(address))
            else:
                normalized_address = f"{address}/32"
            each_ip_filtered["address"] = normalized_address.strip()
            each_ip_filtered["description"] = each_ip["caption"]
            each_ip_filtered["raw_data"] = each_ip.copy()
            dataset_a.append(each_ip_filtered)
            records_processed_a += 1

# pprint(dataset_a)
print(f"\nTotal records processed from JSON: {records_processed_a}")

### ---load data to build B---###
dataset_b_source = nb.ipam.ip_addresses.all()
dataset_b = []
records_processed_b = 0
for each_ip in dataset_b_source:
    each_ip_filtered = {}
    each_ip_filtered["address"] = str(each_ip.address.strip())
    each_ip_filtered["tags"] = each_ip.tags
    dataset_b.append(each_ip_filtered)
    records_processed_b += 1
# pprint(dataset_b)
print(f"Total records processed from NetBox: {records_processed_b}")

# create artifiact directory if it doens't exist:
folder_path = f"./artifacts/{RUN_ID}"
os.makedirs(folder_path, exist_ok=True)
# function to collect artifacts:


def col_artifacts(artifacts, file_name):
    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    artifact_file = f"{folder_path}/{timestamp}_{file_name}"
    with open(artifact_file, "w") as f:
        json.dump(artifacts, f, indent=4)


### ---reconcilation logic---###
# Case 1: Exists in A but not in B
case_1_ips = []
# Case 2: Exists in both A and B
case_2_ips = []
# Case 3: Exists in B but not in A
case_3_ips = []
payload_update_last_seen = {
    "custom_fields": {
        "last_seen": date.today().isoformat()
    }
}


## --case 1 & case 2 logic--##
print("===============================================================")
print("UPDATE/CREATE workflow:\n")
progress_a = 0
for each_ip_a in dataset_a:
    exists_in_b = False
    raw_ip_a = ipaddress.ip_interface(each_ip_a["address"]).ip
    for each_ip_b in dataset_b:
        raw_ip_b = ipaddress.ip_interface(each_ip_b["address"]).ip
        # print(f"{raw_ip_a} (JSON)<-->{raw_ip_b} (NetBox)")
        ## --case 2 (exists in both A & B)--##
        if raw_ip_a == raw_ip_b:
            ip = nb.ipam.ip_addresses.get(address=each_ip_b["address"])
            if ip is None:  # branch 0
                print(
                    f"NetBox IP not found, address: {each_ip_b['address']}")
                exists_in_b = True
                case_2_ips.append(
                    {
                        "address": each_ip_b['address'],
                        "action": "error",
                        "message": f"NetBox IP not found, address: {each_ip_b['address']}"
                    }
                )
                break
            existing_slugs = []
            if each_ip_b["tags"]:
                print(f"{ip['address']} -- existing tags: ")
                for tag in each_ip_b["tags"]:
                    print(f"\t{tag}")
                    existing_slugs.append(tag.slug)
            if "manual" in existing_slugs:  # branch 1
                print(
                    f"{ip['address']} -- Manual IP -- not managed.")
                case_2_ips.append(
                    {
                        "address": ip['address'],
                        "action": "none",
                        "message": f"{ip['address']} -- Manual IP -- not managed."
                    }
                )
            elif "external-sot-github" in existing_slugs:   # branch 2
                ip.update(payload_update_last_seen)
                print(
                    f"{ip['address']} -- External SoT GitHub -- last seen updated.")
                case_2_ips.append(
                    {
                        "address": ip['address'],
                        "action": "last seen updated",
                        "message": f"{ip['address']} -- External SoT GitHub -- last seen updated."
                    }
                )
            elif "review-required" in existing_slugs:   # branch 3
                ip.update(payload_update_last_seen)
                print(
                    f"{ip['address']} -- Review-Required -- last seen updated.")
                case_2_ips.append(
                    {
                        "address": ip['address'],
                        "action": "last seen updated",
                        "message": f"{ip['address']} -- Review-Required -- last seen updated."
                    }
                )
            else:   # branch 4
                print(f"{ip['address']} -- no existing tags")
                if not "review-required" in existing_slugs:
                    existing_slugs.append("review-required")
                payload = payload_update_last_seen.copy()
                payload["tags"] = [{"slug": each_tag}
                                   for each_tag in existing_slugs]

                ip.update(payload)
                print(f"{ip.address} requires a review.")
                case_2_ips.append(
                    {
                        "address": ip['address'],
                        "action": "last seen updated & review-required tag added",
                        "message": f"{ip['address']} requires a review."
                    }
                )
            exists_in_b = True
            print(
                f"WAN IP processed from JSON: {progress_a+1}/{records_processed_a} | IP: {raw_ip_a}")
            print("-----------------------------------------------------")
            break

    ## --case 1 (exists in A but not in B)--##
    if not exists_in_b:
        payload = {
            "address": each_ip_a["address"],
            "tags": [{"slug": "external-sot-github"},
                     {"slug": each_ip_a["platform"]}],
            "custom_fields": {
                "last_seen": date.today().isoformat()
            },
            "comments": f"{each_ip_a['raw_data']}"
        }
        nb.ipam.ip_addresses.create(**payload)
        print(
            f"{each_ip_a['address']} -- NEW -- created in NetBox.")
        case_1_ips.append(
            {
                "address": each_ip_a["address"],
                "action": "IP created",
                "message": f"{each_ip_a['address']} -- NEW -- created in NetBox."
            }
        )
        print(
            f"WAN IP processed from JSON: {progress_a+1}/{records_processed_a} | IP: {raw_ip_a}")
        print("-----------------------------------------------------")

    progress_a += 1

## --case 3 (exists in B but not in A)--##
print("===============================================================")
print("DEPRECATE workflow:\n")
progress_b = 0
for each_ip_b in dataset_b:
    exists_in_a = False
    raw_ip_b = ipaddress.ip_interface(each_ip_b["address"]).ip
    for each_ip_a in dataset_a:
        raw_ip_a = ipaddress.ip_interface(each_ip_a["address"]).ip
        if raw_ip_a == raw_ip_b:
            exists_in_a = True
            break
    if not exists_in_a:
        existing_slugs = []
        if each_ip_b["tags"]:
            for tag in each_ip_b["tags"]:
                existing_slugs.append(tag.slug)
        if "external-sot-github" in existing_slugs:
            ip = nb.ipam.ip_addresses.get(address=each_ip_b["address"])
            if ip is None:
                print(
                    f"NetBox IP not found, address: {each_ip_b['address']}")
                case_3_ips.append(
                    {
                        "address": each_ip_b["address"],
                        "action": "error",
                        "message": f"NetBox IP not found, address: {each_ip_b['address']}"
                    }
                )
                continue
            ip.update({"status": "deprecated"})
            print(
                f"IP no longer seen in JSON. Status set to deprecated | IP: {ip.address}")
            print("-----------------------------------------------------")
            case_3_ips.append(
                {
                    "address": each_ip_b["address"],
                    "action": "IP status set to 'deprecated'",
                    "message": f"IP no longer seen in JSON. Status set to deprecated | IP: {each_ip_b['address']}"
                }
            )

print("===============================================================")

col_artifacts(case_1_ips, "case_1_artifacts.json")
col_artifacts(case_2_ips, "case_2_artifacts.json")
col_artifacts(case_3_ips, "case_3_artifacts.json")
