import datetime
import json
import os
import re
import time

from gcsa.event import Event
from gcsa.google_calendar import GoogleCalendar, SendUpdatesMode
from gcsa.serializers.event_serializer import EventSerializer

import orm
from pyairtable import Base


def dict_symmetric_difference(a, b):
    return {k: a[k] if k in a else b[k] for k in set(a.keys()).symmetric_difference(b.keys())}


def phone_number(nrs: str) -> str:
    return f'{nrs[:3]} {nrs[3:6]} {nrs[6:8]} {nrs[8:10]}'


def delete_event(record_id):
    if os.path.exists('projektkalender.json'):
        with open("projektkalender.json", "r", encoding="utf-8") as f:
            kalender = json.load(f)
        gc = GoogleCalendar(gcal_id, credentials_path='credentials.json')
        gc.delete_event(kalender[record_id]['post'])


api_key = os.environ["api_key"]
base_id = os.environ["base_id"]
gcal_id = os.environ["gcal_id"]
base = Base(api_key, base_id)


def main():
    # mail_passwd = os.environ["mail_passwd"]
    gc = GoogleCalendar(gcal_id, credentials_path='credentials.json')

    # mail = EmailMessage()
    # mail.add_header('reply-to', 'info@levandevideo.se')
    # s = smtplib.SMTP('mail.levandevideo.se', port=26)
    # s.login('bokning@levandevideo.se', mail_passwd)

    # s.send_message(mail)
    # s.quit()

    projektkalender = base.get_table("Projektkalender")
    people = base.get_table("Frilans")
    adresser = base.get_table("Adressbok")
    leveranser = base.get_table("Leveranser")
    bestallare = base.get_table("Beställare")
    new_thing = {}

    prylartable = base.get_table('Prylar')
    # mail.add_header('Content-Type', 'text/html')
    # ending_of_mail = "<sub>Jag är en robot och lär mig nya saker varje dag, ifall det blev fel så kan du antingen skicka iväg ett mejl till din kontakt på Levande Video eller till <a href='mailto: epost@edvinbryntesson.se'>mig</a> :)</sub>"
    # mail.set_payload('Body of <b>email{}</b>'.format(ending_of_mail))

    emails = {}
    namn = {}
    phone_numbers = {}
    adresser_dict = {}
    SCOPES = ['https://www.googleapis.com/auth/calendar']

    kalender: dict[str, dict[str, str]] = {}
    if os.path.exists('projektkalender.json'):
        with open("projektkalender.json", "r", encoding="utf-8") as f:
            kalender = json.load(f)
    else:
        with open("projektkalender.json", "w", encoding="utf-8") as f:
            json.dump({}, f)

    for person_record in people.all():
        if 'E-post' in person_record['fields'].keys():
            emails[person_record['id']] = person_record['fields']['E-post'].split(', ')
        if 'Name' in person_record['fields'].keys():
            namn[person_record['id']] = person_record['fields']['Name']
        if 'telefon nr' in person_record['fields'].keys():
            nrs = person_record['fields']['telefon nr']
            phone_numbers[person_record['id']] = phone_number(nrs)
    lv_emails = [
        epost[0] for epost in emails.values()
        if '@levandevideo.se' in epost[0] or epost[0] == "epost@edvinbryntesson.se"
    ]

    for adress in orm.get_all_in_orm(orm.Adressbok):
        adresser_dict[adress.id] = adress.name

    all_leverans = {x.id: x for x in orm.get_all_in_orm(orm.Leverans)}

    for event in orm.get_all_in_orm(orm.Projektkalender):
        try:
            assert event.leverans_rid is not None

            leverans: orm.Leverans = all_leverans[event.leverans_rid[2:-2]]
            if event.projekt_typ == "Utrustning" or event.projekt_typ == "Redigerat":
                continue
            if leverans.all_personal is None:
                leverans.all_personal = []
            all_people: list[orm.Person] = []
            if leverans.producent is not None:
                all_people.extend(leverans.producent)
            all_people.extend(leverans.all_personal)

            for person in all_people:
                if person.name is None:
                    person.fetch()

            invite_list = [person.epost for person in all_people if person.epost is not None]  # if email in lv_emails]

            if event.datum is None or event.getin is None or event.getout is None:
                continue
            datum = event.datum
            if datum < datetime.datetime.now().date():
                continue
            # print(fields['Getin'])

            getin = datetime.datetime.fromisoformat(datum.isoformat()) + datetime.timedelta(seconds=event.getin)
            getout = datetime.datetime.fromisoformat(datum.isoformat()) + datetime.timedelta(seconds=event.getout)
            if event.program_start is not None and event.program_slut is not None:
                program_start = datetime.datetime.fromisoformat(datum.isoformat()
                                                                ) + datetime.timedelta(seconds=event.program_start)
                program_slut = datetime.datetime.fromisoformat(datum.isoformat()
                                                               ) + datetime.timedelta(seconds=event.program_slut)
            else:
                program_start, program_slut = None, None
            if event.status is not None:
                if event.status == 'Obekräftat projekt':
                    status = 'tentative'
                elif event.status == 'Avbokat':  # remove or skip cancelled events
                    status = 'cancelled'
                    if event.id in kalender.keys():
                        # mail.set_content("""\n"""+ending_of_mail)
                        # mail['Subject'] = 'Gigget den {} har blivit inställt'.format(datum.isoformat())
                        # mail['From'] = 'bokning@levandevideo.se'
                        # mail['To'] = ", ".join(lv_emails)

                        # s.send_message(mail)

                        try:
                            print(f"deleting one")
                            print(f"{event.name2[2:-2]}")
                            kal_del = EventSerializer.to_object(kalender[event.id])

                            gc.delete_event(kal_del)
                            kalender.pop(event.id)
                        except Exception as e:
                            print("Error", e)
                    continue

                else:
                    status = 'confirmed'
            else:
                status = 'confirmed'
            description = ''
            saker = [
                'Projektledare', 'producent', 'Bildproducent', 'Fotograf', 'Ljudtekniker', 'Ljustekniker',
                'Grafikproducent', 'Animatör', 'Körproducent', 'Innehållsproducent', 'Scenmästare', 'Tekniskt_ansvarig'
            ]
            for field in saker:
                if field in leverans.__dict__['_fields'].keys():
                    if field == 'producent':
                        description += "Producent: \n{}".format(
                            "\n".join([((namn[x] + " - " + phone_numbers[x]) if x in phone_numbers.keys() else namn[x])
                                       for x in leverans_thing['fields'][field]])
                        )
                    else:
                        description += "{}: \n{}".format(
                            field,
                            "\n".join([((namn[x] + " - " + phone_numbers[x]) if x in phone_numbers.keys() else namn[x])
                                       for x in leverans_thing['fields'][field]])
                        )
                    description += '\n\n'

            # description += "\n"
            if leverans.pryl_paket is not None:
                paketen = leverans.pryl_paket
            else:
                paketen = []
            if leverans.antal_paket is not None:
                antal_paket = leverans.antal_paket.split(",")
            else:
                antal_paket = []
            if leverans.extra_prylar is not None:
                prylar = leverans.extra_prylar
            else:
                prylar = []
            if leverans.antal_prylar is not None:
                antal_prylar = leverans.antal_prylar.split(",")
            else:
                antal_prylar = []
            paketen_string = "Beställning: \n"
            try:

                for idx, paket in enumerate(paketen):
                    if idx < len(antal_paket):  # and not paket_dict[paket].get('hide from calendar', False):
                        if paket.name is None:
                            try:
                                paket.fetch()
                            except Exception as e:
                                pass
                        assert type(paket.name) is str
                        org_paket = paket.name
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
                for idx, pryl in enumerate(prylar):
                    if idx < len(antal_prylar):  # and not prylar_dict[pryl].get('hide from calendar', False):
                        if pryl.name is None:
                            pryl.fetch()
                        assert type(pryl.name) is str
                        org_pryl = pryl.name
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
            except AssertionError:
                print("assert error :(")

            if leverans.beställare is not None:
                bestallare = leverans.beställare[0]
                description += 'Beställare: {}'.format(bestallare.name)
                if bestallare.phone is not None:
                    description += ' - {}'.format(phone_number(bestallare.phone))
                description += '\n\n'
            if program_start is not None:
                description += 'Körtider: {}-{}\n'.format(
                    program_start.strftime("%H:%M"), program_slut.strftime("%H:%M")
                )

            if event.kommentar_till_frilans is not None:
                description += event.kommentar_till_frilans

            if paketen_string != "":
                description += "\n" + paketen_string

            description += """\nFör mer information gällande framtida bokningar så kan du kolla här: https://airtable.com/invite/l?inviteId=invJnNIcV8mTqcKR9&inviteToken=92b5c354ee319e7b9b30a85c2d89dd32ec269cb38a4631f51c83befb0b290c87&utm_medium=email&utm_source=product_team&utm_content=transactional-alerts"""

            projektkalender.update(event.id, {"Calendar description": description})

            if event.status is None:
                continue
            assert event.name2 is not None

            if leverans.adress is not None and leverans.adress[0].name is None:
                leverans.adress[0].fetch()
                assert leverans.adress[0].name is not None
            else:
                leverans.adress = []

            my_event = Event(
                event.name2[2:-2] + (' [OBEKRÄFTAT]' if event.status == 'Obekräftat projekt' else "") +
                (" [RIGG]" if leverans.typ == "Rigg" else ""),
                getin,
                getout,
                location=leverans.adress[0].name if len(leverans.adress) > 0 else None,
                attendees=invite_list,
                status=status,
                description=description,
                extendedProperties={"private": {
                    "autogenerated": "true"
                }}
            )

            if event.id in kalender.keys() and kalender[event.id].get("id") is not None:
                if event.id == "m12hrq8qq8ii1at6r5bl6llbt8":
                    print("{my_event}")
                before_update: Event = EventSerializer.to_object(kalender[event.id])
                my_event.event_id = before_update.event_id

                pop_thingies = [
                    "sequence", "iCalUID", "htmlLink", "eventType", "visibility", "etag", "kind", "location",
                    "send_updates"
                ]
                formatted_dict = [EventSerializer.to_json(my_event), EventSerializer.to_json(before_update)]

                more_thingies = ["responseStatus", "displayName"]

                for number in (0, 1):
                    for i in range(len(formatted_dict[number]["attendees"])):
                        for popthing in more_thingies:
                            formatted_dict[number]["attendees"][i].pop(popthing, None)

                for person in formatted_dict[1]['attendees']:
                    for key in person:
                        if key != "email":
                            print("fuck")

                for pop_thing in pop_thingies:
                    if pop_thing == "location" and any([
                        x.get("location", "") != "" for x in [formatted_dict[0], formatted_dict[1]]
                    ]):
                        continue
                    formatted_dict[0].pop(pop_thing, None)
                    formatted_dict[1].pop(pop_thing, None)

                ping_conditions = ["attendees", "status", "start", "end", "location"]

                # print(
                #    json.dumps(formatted_dict[0], indent=2),
                #    json.dumps(formatted_dict[1], indent=2)
                # )
                if formatted_dict[0] == formatted_dict[1]:
                    kalender[event.id] = EventSerializer.to_json(before_update)
                    continue
                else:
                    before_update.description = my_event.description
                    gc.update_event(before_update, SendUpdatesMode.NONE)
                    update = SendUpdatesMode.NONE
                    if any(
                        formatted_dict[0].get(dict_key) != formatted_dict[1].get(dict_key)
                        for dict_key in ping_conditions
                    ):
                        update = SendUpdatesMode.ALL
                    my_event = gc.update_event(my_event, update)
                    print(my_event)
            else:
                try:
                    my_event = gc.add_event(my_event, SendUpdatesMode.ALL)
                    print(my_event)
                except:
                    pass
            kalender[event.id] = EventSerializer.to_json(my_event)
        except Exception as e:
            print(e, event)
            if event.leverans_rid[2:-2] == "recQTkEOxpgfazdxN":
                print("HELLO HERE")

    keys_to_del = []
    all_ids = [record["id"] for record in projektkalender.all()]
    for key in kalender.keys():
        if key not in all_ids:
            try:
                gc.delete_event(kalender[key].get('id'))
            except:
                pass
            keys_to_del.append(key)
            print("deleted:", key)
    for key in keys_to_del:
        del kalender[key]
    with open("projektkalender.json", "w", encoding="utf-8") as f:
        json.dump(kalender, f, ensure_ascii=False, indent=2)
    with open("new_calendar.json", "w", encoding="utf-8") as f:
        json.dump(new_thing, f, ensure_ascii=False, indent=2)


error_table = base.get_table("tbl0NUM7MHa2iVmrw")
while __name__ == "__main__":
    if os.environ.get("airtable_debug", "yes") != "no":
        main()
    else:
        try:
            main()
        except Exception as e:
            error_table.create(fields={"fld11NQUETyWAJ7ZR": str(e)})
    print("Sleeping for 10 minutes")
    time.sleep(600)
