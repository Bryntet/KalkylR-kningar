from pyairtable import Base
import os
import json
import datetime
import time
import smtplib
import re
from gcsa.google_calendar import GoogleCalendar
import gcsa
from gcsa.event import Event
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def phone_number(nrs: str) -> str:
    return f"{nrs[:3]} {nrs[3:6]} {nrs[6:8]} {nrs[8:10]}"


def delete_event(record_id):
    if os.path.exists("projektkalender.json"):
        with open("projektkalender.json", "r", encoding="utf-8") as f:
            kalender = json.load(f)
        gc = GoogleCalendar(gcal_id, credentials_path="credentials.json")
        gc.delete_event(kalender[record_id]["post"])


def main():
    api_key = os.environ["api_key"]
    base_id = os.environ["base_id"]
    gcal_id = os.environ["gcal_id"]
    # mail_passwd = os.environ["mail_passwd"]
    gc = GoogleCalendar(gcal_id, credentials_path="credentials.json")

    # mail = EmailMessage()
    # mail.add_header('reply-to', 'info@levandevideo.se')
    # s = smtplib.SMTP('mail.levandevideo.se', port=26)
    # s.login('bokning@levandevideo.se', mail_passwd)

    # s.send_message(mail)
    # s.quit()

    base = Base(api_key, base_id)
    projektkalender = base.get_table("Projektkalender")
    people = base.get_table("Frilans")
    adresser = base.get_table("Adressbok")
    leveranser = base.get_table("Leveranser")
    bestallare = base.get_table("Beställare")

    prylartable = base.get_table("Prylar")
    # mail.add_header('Content-Type', 'text/html')
    # ending_of_mail = "<sub>Jag är en robot och lär mig nya saker varje dag, ifall det blev fel så kan du antingen skicka iväg ett mejl till din kontakt på Levande Video eller till <a href='mailto: epost@edvinbryntesson.se'>mig</a> :)</sub>"
    # mail.set_payload('Body of <b>email{}</b>'.format(ending_of_mail))

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

    for person_record in people.all():
        if "E-post" in person_record["fields"].keys():
            emails[person_record["id"]] = person_record["fields"]["E-post"].split(", ")
        if "Name" in person_record["fields"].keys():
            namn[person_record["id"]] = person_record["fields"]["Name"]
        if "telefon nr" in person_record["fields"].keys():
            nrs = person_record["fields"]["telefon nr"]
            phone_numbers[person_record["id"]] = phone_number(nrs)
    lv_emails = [
        epost[0]
        for epost in emails.values()
        if "@levandevideo.se" in epost[0]
        or epost[0] == "grammatokivotio.agios.vasilis@gmail.com"
    ]

    for adress in adresser.all():
        adresser_dict[adress["id"]] = adress["fields"]["Adress"]

    for event in projektkalender.all():
        fields = event["fields"]
        if (
            fields.get("Projekt typ") == "Utrustning"
            or fields.get("Projekt typ") == "Redigerat"
        ):
            break
        if "Alla personal" not in fields.keys():
            fields["Alla personal"] = []
        if "Producent" in fields.keys():
            fields["Alla personal"].extend(fields["Producent"])
        invite_list = [
            email
            for person in fields["Alla personal"]
            if person in emails.keys()
            for email in emails[person]
            if email in lv_emails
        ]
        if "Datum" not in fields.keys():
            continue
        datum = datetime.datetime.fromisoformat(fields["Datum"])
        if datum < datetime.datetime.now():
            continue
        # print(fields['Getin'])
        if type(fields["Getin"]) == dict:
            continue
        getin = datum + datetime.timedelta(seconds=fields["Getin"])
        getout = datum + datetime.timedelta(seconds=fields["Getout"])
        if "Program start" in fields.keys():
            program_start = datum + datetime.timedelta(seconds=fields["Program start"])
            program_slut = datum + datetime.timedelta(seconds=fields["Program slut"])
        else:
            program_start, program_slut = None, None
        if "Status" in fields.keys():
            if fields["Status"] == "Obekräftat projekt":
                status = "tentative"
            elif fields["Status"] == "Avbokat":  # remove or skip cancelled events
                status = "cancelled"
                if event["id"] in kalender.keys():
                    # mail.set_content("""\n"""+ending_of_mail)
                    # mail['Subject'] = 'Gigget den {} har blivit inställt'.format(datum.isoformat())
                    # mail['From'] = 'bokning@levandevideo.se'
                    # mail['To'] = ", ".join(lv_emails)

                    # s.send_message(mail)

                    try:
                        gc.delete_event(kalender[event["id"]]["post"])
                    except Exception as e:
                        print("Error", e)
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
                                for x in leverans_thing["fields"][field]
                            ]
                        ),
                    )
                description += "\n\n"

        # description += "\n"
        paketen = fields.get("Paket", [])
        antal_paket = fields.get("antal paket", [""])[0].split(",")
        prylar = fields.get("Prylar", [])
        antal_prylar = fields.get("antal prylar", [""])[0].split(",")
        paketen_string = "Beställning: \n"
        with open("paket.json", "r") as f:
            paket_dict = json.load(f)
            # if len(paketen) > 0:
            #    paketen_string += ""
            for idx, paket in enumerate(paketen):
                if idx < len(
                    antal_paket
                ):  # and not paket_dict[paket].get('hide from calendar', False):
                    org_paket = paket_dict[paket]["namn3"]
                    regex_thing = re.search(r"([^[]*),? ?( [.*]?)*", org_paket)
                    if regex_thing:
                        paket_namn = regex_thing.group(1)
                        new_reg = re.search(r"((.*), ?|.*)", paket_namn)
                        if new_reg:
                            if new_reg.group(2) is not None:
                                paket_namn = new_reg.group(2)

                    else:
                        paket_namn = org_paket
                    if antal_paket[idx] == "":
                        paketen_string += "1st - " + paket_namn + "\n"
                    else:
                        paketen_string += antal_paket[idx] + "st - " + paket_namn + "\n"
        with open("prylar.json", "r") as f:
            prylar_dict = json.load(f)
            # if len(prylar) > 0:
            #    paketen_string += "Prylar: \n"
            for idx, pryl in enumerate(prylar):
                if idx < len(
                    antal_prylar
                ):  # and not prylar_dict[pryl].get('hide from calendar', False):
                    org_pryl = prylar_dict[pryl]["name_packlista"]
                    regex_thing = re.search(r"([^[]*),? ?( [.*]?)*", org_pryl)
                    if regex_thing:
                        pryl_namn = regex_thing.group(1)
                        new_reg = re.search(r"((.*), ?|.*)", pryl_namn)
                        if new_reg:
                            if new_reg.group(2) is not None:
                                pryl_namn = new_reg.group(2)
                    else:
                        pryl_namn = org_pryl
                    if antal_prylar[idx] == "":
                        paketen_string += "1st - " + pryl_namn + "\n"
                    else:
                        paketen_string += antal_prylar[idx] + "st - " + pryl_namn + "\n"

        if "Beställare from projekt" in leverans_thing["fields"]:
            bestallare_record = bestallare.get(
                leverans_thing["fields"]["Beställare from projekt"][0]
            )["fields"]
            description += "Beställare: {}".format(bestallare_record["Namn"])
            if "Phone" in bestallare_record.keys():
                description += " - {}".format(phone_number(bestallare_record["Phone"]))
            description += "\n\n"
        if program_start is not None:
            description += "Körtider: {}-{}\n".format(
                program_start.strftime("%H:%M"), program_slut.strftime("%H:%M")
            )

        if "köris" in leverans_thing["fields"]:
            description += "Körschema: {}\n\n".format(fields["köris"])
        if "Kommentar till frilans" in leverans_thing["fields"]:
            description += leverans_thing["fields"]["Kommentar till frilans"]

        if paketen_string != "":
            description += "\n" + paketen_string

        description += """\nFör mer information gällande framtida bokningar så kan du kolla här: https://airtable.com/invite/l?inviteId=invJnNIcV8mTqcKR9&inviteToken=92b5c354ee319e7b9b30a85c2d89dd32ec269cb38a4631f51c83befb0b290c87&utm_medium=email&utm_source=product_team&utm_content=transactional-alerts"""

        projektkalender.update(event["id"], {"Calendar description": description})

        if "Status" not in fields:
            continue
        temp_thing = [
            fields["Name2"][0]
            + (" [OBEKRÄFTAT]" if fields["Status"] == "Obekräftat projekt" else "")
            + (" [RIGG]" if fields["Projekt typ"][0] == "Rigg" else ""),
            getin.isoformat("T"),
            getout.isoformat("T"),
            adresser_dict[fields["Adress"][0]] if "Adress" in fields.keys() else "",
            invite_list,
            status,
            description,
        ]

        my_event = Event(
            fields["Name2"][0]
            + (" [OBEKRÄFTAT]" if fields["Status"] == "Obekräftat projekt" else "")
            + (" [RIGG]" if fields["Projekt typ"][0] == "Rigg" else ""),
            getin,
            getout,
            location=adresser_dict[fields["Adress"][0]]
            if "Adress" in fields.keys()
            else "",
            attendees=invite_list,
            status=status,
            description=description,
            # send_updates="all"
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
            kalender[event["id"]] = {
                "pre": temp_thing,
                "post": gc.add_event(my_event).id,
            }
        print(my_event)
    keys_to_del = []
    all_ids = [record["id"] for record in projektkalender.all()]
    for key in kalender.keys():
        if key not in all_ids:
            try:
                gc.delete_event(kalender[key]["post"])
            except:
                pass
            keys_to_del.append(key)
            print("deleted:", key)
    for key in keys_to_del:
        del kalender[key]
    with open("projektkalender.json", "w", encoding="utf-8") as f:
        json.dump(kalender, f, ensure_ascii=False, indent=2)


while __name__ == "__main__":
    main()
    print("Sleeping for 10 minutes")
    time.sleep(600)
