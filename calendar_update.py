from pyairtable import Base
import os
import json
import datetime

from gcsa.google_calendar import GoogleCalendar
from gcsa.event import Event

api_key = os.environ["api_key"]
base_id = os.environ["base_id"]
gcal_id = os.environ["gcal_id"]

gc = GoogleCalendar(gcal_id, credentials_path="credentials.json")

base = Base(api_key, base_id)
projektkalender = base.get_table("Projektkalender")
people = base.get_table("Frilans")
adresser = base.get_table("Adressbok")
leveranser = base.get_table("Leveranser")
bestallare = base.get_table("Beställare")

emails = {}
namn = {}
phone_numbers = {}
adresser_dict = {}
SCOPES = ["https://www.googleapis.com/auth/calendar"]

kalender: dict[str, Event] = {}
if os.path.exists("projektkalender.json"):
    with open("projektkalender.json", "r", encoding="utf-8") as f:
        kalender = json.load(f)
else:
    with open("projektkalender.json", "w", encoding="utf-8") as f:
        json.dump({}, f)


def phone_number(nrs: str) -> str:
    return f"{nrs[:3]} {nrs[3:6]} {nrs[6:8]} {nrs[8:10]}"


for person_record in people.all():
    if "E-post" in person_record["fields"].keys():
        emails[person_record["id"]] = person_record["fields"]["E-post"].split(", ")
    if "Name" in person_record["fields"].keys():
        namn[person_record["id"]] = person_record["fields"]["Name"]
    if "telefon nr" in person_record["fields"].keys():
        nrs = person_record["fields"]["telefon nr"]
        phone_numbers[person_record["id"]] = phone_number(nrs)

for adress in adresser.all():
    adresser_dict[adress["id"]] = adress["fields"]["Adress"]
print(emails)

for event in projektkalender.all():
    fields = event["fields"]
    if "Alla personal" not in fields.keys():
        fields["Alla personal"] = []
    if "Producent" in fields.keys():
        fields["Alla personal"].extend(fields["Producent"])
    invite_list = [
        email
        for person in fields["Alla personal"]
        if person in emails.keys()
        for email in emails[person]
    ]
    if "Datum" not in fields.keys():
        continue
    datum = datetime.datetime.fromisoformat(fields["Datum"])
    if datum < datetime.datetime.now():
        continue
    getin = datum + datetime.timedelta(seconds=fields["Getin"])
    getout = datum + datetime.timedelta(seconds=fields["Getout"])
    program_start = datum + datetime.timedelta(seconds=fields["Program start"])
    program_slut = datum + datetime.timedelta(seconds=fields["Program slut"])
    if "Status" in fields.keys():
        if fields["Status"] == "Obekräftat projekt":
            status = "tentative"
        elif fields["Status"] == "Avbokat":  # remove or skip cancelled events
            status = "cancelled"
            if event["id"] in kalender.keys():
                gc.delete_event(event["id"])
                kalender.pop(event["id"])
            continue

        else:
            status = "confirmed"
    else:
        status = "confirmed"
    description = ""
    saker = [
        "Projektledare",
        "producent",
        "Bildproducent",
        "Fotograf",
        "Ljudtekniker",
        "Ljustekniker",
        "Grafikproducent",
        "Animatör",
        "Körproducent",
        "Innehållsproducent",
        "Scenmästare",
        "Tekniskt ansvarig",
    ]
    leverans_thing = leveranser.get(event["fields"]["Leverans"][0])
    for field in saker:
        if field in leverans_thing["fields"].keys():
            if field == "producent":
                description += "Producent: \n{}".format(
                    "\n".join(
                        [
                            (
                                (namn[x] + " - " + phone_numbers[x])
                                if x in phone_numbers.keys()
                                else namn[x]
                            )
                            + "\n"
                            for x in leverans_thing["fields"][field]
                        ]
                    )
                )
            else:
                description += "{}: \n{}".format(
                    field,
                    "\n".join(
                        [
                            (
                                (namn[x] + " - " + phone_numbers[x])
                                if x in phone_numbers.keys()
                                else namn[x]
                            )
                            + "\n"
                            for x in leverans_thing["fields"][field]
                        ]
                    ),
                )
            description += "\n"

    description += "\n"

    if "Beställare" in leverans_thing["fields"]:
        bestallare_record = bestallare.get(leverans_thing["fields"]["Beställare"][0])[
            "fields"
        ]
        description += "Beställare: {}".format(bestallare_record["Namn"])
        if "Phone" in bestallare_record.keys():
            description += " - {}".format(phone_number(bestallare_record["Phone"]))
        description += "\n"
    description += "Körtider: {}-{}\n".format(
        program_start.strftime("%H:%M"), program_slut.strftime("%H:%M")
    )
    if "köris" in leverans_thing["fields"]:
        description += "Körschema: {}\n\n".format(fields["köris"])
    if "Kommentar till frilans" in leverans_thing["fields"]:
        description += leverans_thing["fields"]["Kommentar till frilans"]
    description += """\n\n\nFör mer information gällande framtida bokningar så kan du kolla här: https://airtable.com/invite/l?inviteId=invJnNIcV8mTqcKR9&inviteToken=92b5c354ee319e7b9b30a85c2d89dd32ec269cb38a4631f51c83befb0b290c87&utm_medium=email&utm_source=product_team&utm_content=transactional-alerts"""
    temp_thing = [
        fields["Name2"],
        getin.isoformat(),
        getout.isoformat(),
        adresser_dict[fields["Adress"][0]] if "Adress" in fields.keys() else "",
        invite_list,
        status,
        description,
    ]

    my_event = Event(
        fields["Name2"],
        getin,
        getout,
        location=adresser_dict[fields["Adress"][0]]
        if "Adress" in fields.keys()
        else "",
        attendees=invite_list,
        status=status,
        description=description,
    )
    if event["id"] in kalender.keys():
        temp = kalender[event["id"]]["pre"]
        temp_event = Event(
            temp[0],
            datetime.datetime.fromisoformat(temp[1]),
            datetime.datetime.fromisoformat(temp[2]),
            location=temp[3],
            attendees=temp[4],
            status=temp[5],
            description=temp[6] if len(temp) > 6 else "",
        )
        if temp_event == my_event:
            continue
        else:
            my_event.event_id = kalender[event["id"]]["post"]
            kalender[event["id"]] = {
                "pre": temp_thing,
                "post": gc.update_event(my_event).id,
            }
    else:
        kalender[event["id"]] = {"pre": temp_thing, "post": gc.add_event(my_event).id}

    print(my_event)

with open("projektkalender.json", "w", encoding="utf-8") as f:
    json.dump(kalender, f, ensure_ascii=False, indent=2)
