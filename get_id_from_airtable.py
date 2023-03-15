import os
import requests
import json
from pyairtable.orm import Model, fields
from pydantic import BaseModel
import re

api_key = os.environ["api_key"]
base_id = os.environ["base_id"]

url = "https://api.airtable.com/v0/meta/bases/appG1QEArAVGABdjm/tables"

payload = {}

headers = {
    "Authorization": "Bearer {}".format(os.environ["meta_key"]),
    "Cookie": "brw=brwCwx8u9KwIzkmiJ; AWSALB=ay99AB8vnr+eFIkJZDmokIXwcpikQrt2KgtIchwf73Al3UvLwd3xTehb+lkZ9UIiDWr1e+d9Czv7R3kdYz+KkK+zb2qN8uxXp2hKjZG/e1zfTSIQDl/BsKhZB7f9; AWSALBCORS=ay99AB8vnr+eFIkJZDmokIXwcpikQrt2KgtIchwf73Al3UvLwd3xTehb+lkZ9UIiDWr1e+d9Czv7R3kdYz+KkK+zb2qN8uxXp2hKjZG/e1zfTSIQDl/BsKhZB7f9",
}

# tables = response.json()['tables']

# with open("table_schema.json", "w", encoding="utf-8") as f:
#    json.dump(tables, f, ensure_ascii=False, indent=2)


def get_model_class(base_id):
    response = requests.request("GET", url, headers=headers, data=payload)

    # Check if response is successful
    if response.status_code == 200:
        # Parse json data into pydantic models
        class Field(BaseModel):
            fldid: str
            name: str
            type: str
            link: str | None

        class Table(BaseModel):
            tblid: str
            name: str
            fields: list[Field]

        class Base(BaseModel):
            tables: list[Table]

        tables = response.json()["tables"]
        for table in tables:
            table["tblid"] = table["id"]
            for field in table["fields"]:
                field["fldid"] = field["id"]
                field["link"] = None
                if any(
                    x == field["type"]
                    for x in ["formula", "rollup", "multipleLookupValues"]
                ):
                    field["type"] = None
                    # if field.get("options", {}).get("result") is not None:
                    #    field['type'] = field['options']['result']['type']
                    # elif field['type'] == 'formula':
                    #    field['type'] = "text"
                    # else:
                    #    field['type'] = ""

                elif any(
                    x == field["type"]
                    for x in [
                        "singleLineText",
                        "multilineText",
                        "richText",
                        "multipleSelects",
                        "singleSelect",
                        "url",
                    ]
                ):
                    field["type"] = "Text"
                elif any(
                    x == field["type"]
                    for x in [
                        "autoNumber",
                        "number",
                        "currency",
                        "percent",
                        "duration",
                        "rating",
                    ]
                ):
                    if (
                        field["type"] == "autoNumber"
                        or field["options"].get("precision") == 0
                    ):
                        field["type"] = "Integer"
                    else:
                        field["type"] = "Float"
                elif any(x == field["type"] for x in ["button", "multipleAttachments"]):
                    field["type"] = None
                    # field['type'] = ""
                elif any(x == field["type"] for x in ["multipleRecordLinks"]):
                    field["type"] = "Link"
                    if field["options"].get("linkedTableId") is not None:
                        field["link"] = field["options"]["linkedTableId"]
                    else:
                        field["link"] = table["name"].replace(" ", "")

        test_text = ""
        for field in tables[6]["fields"]:
            if field["type"] is not None:
                new_name = "_".join(field["name"].split(" "))
                new_name = "_".join(
                    [x.lower() for x in re.split(r"(?<!^)(?=[A-Z])", new_name)]
                )

                test_text += (
                    new_name
                    + " = "
                    + 'fields.{}Field("{}")'.format(
                        field["type"].capitalize(), field["id"]
                    )
                    + "\n"
                )

        with open("test_text.txt", "w", encoding="utf-8") as f:
            f.write(test_text)

        for table in tables:
            for field in table["fields"]:
                if field["type"] == "formula":
                    print("wtf")
        base = Base.parse_obj({"tables": tables})

        # Create model class for first table in base (you can modify this logic as needed)
        table = base.tables[0]

        # Define model attributes based on table fields
        attrs = {}

        for field in table.fields:
            field_name = field.name.lower().replace(" ", "_")
            field_type = getattr(fields, field.type.capitalize() + "Field")
            if field.type == "Link":
                continue
                # attrs[field_name] = field_type(field.id, model=field.link)
            else:
                attrs[field_name] = field_type(field.fldid)

        # Define meta class based on base id, table name and api key
        meta_attrs = {"base_id": base_id, "table_name": table.name, "api_key": api_key}

        meta_class = type("Meta", (), meta_attrs)

        attrs["Meta"] = meta_class

        # Create model class based on attributes
        model_class = type(table.name.replace(" ", ""), (Model,), attrs)

        return model_class

    else:
        raise Exception(f"Request failed with status code {response.status_code}")


get_model_class(base_id)

type_list = []

for table in tables:
    for field in table["fields"]:
        type_thing = field.get("type")
        if type_list is not None and type_thing not in type_list:
            type_list.append(type_thing)
        result = field.get("options", {}).get("result", {})
        if result is not None:
            result = result.get("type")
        if result is not None and result not in type_list:
            type_list.append(result)

print(type_list)

for field in tables[7]["fields"]:
    Field(field)

for table in tables:
    print(table["id"], table["name"], len(table["fields"]))
