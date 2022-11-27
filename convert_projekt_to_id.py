import pyairtable
import json
import os
import copy

api_key = os.environ["api_key"]
base_id = os.environ["base_id"]

with open("output.json", "r") as f:
    data = json.load(f)

all_records = pyairtable.Table(api_key, base_id, "Leveranser").all()

new_data = copy.deepcopy(data)
for record_id, fields in data.items():
    if record_id[:3] != "rec":
        continue

    for record in all_records:
        if record["id"] == record_id:
            new_data[record_id].update({"Projekt": record["fields"]["Projekt"][0]})
            break

with open("output.json", "w", encoding="utf-8") as f:
    json.dump(new_data, f, ensure_ascii=False, indent=2)
