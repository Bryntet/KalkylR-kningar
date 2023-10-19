import calendar
import copy
import datetime
import json
import math
import os
import re
import time
import urllib.parse
from operator import itemgetter

import googlemaps
import holidays
import numpy as np
import pandas as pd
import pytz
import requests
from flask import Flask, request
from pyairtable import Base, Table

import orm
from auth_middleware import token_required
from calendar_update import delete_event as cal_del
from folk import Folk

# import google_drive_handler


class Bcolors:
    """Colours!"""

    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


class InvalidMapsAdress(Exception):
    "Raised when the adress is invalid"
    pass


pd.set_option("display.max_columns", None)
pd.set_option("display.max_rows", None)

api_key = os.environ["api_key"]
base_id = os.environ["base_id"]
output_table = Table(api_key, base_id, "Output table")
input_data_table = Table(api_key, base_id, "Input data")
kund_table = Table(api_key, base_id, "Kund")
pryl_table = Table(api_key, base_id, "Prylar")
projekt_table = Table(api_key, base_id, "Projekt")
slutkund_table = Table(api_key, base_id, "Slutkund")
bestallare_table = Table(api_key, base_id, "Beställare")
error_table = Table(api_key, base_id, "tbl0NUM7MHa2iVmrw")

beforeTime = time.time()
output_tables = []
SECRET_KEY = os.environ.get('my_secret')
app = Flask(__name__)

app.config['SECRET_KEY'] = SECRET_KEY


def days_seconds(dt: datetime.datetime) -> int:
    return dt.hour * 60 * 60 + dt.minute * 60 + dt.second


def round_to_nearest_half_hour(dt: datetime.datetime) -> datetime.datetime:
    minute = dt.minute
    if minute < 15:
        minute = 0
    elif 15 <= minute < 45:
        minute = 30
    else:
        minute = 0
        dt += datetime.timedelta(hours=1)
    return dt.replace(minute=minute, second=0, microsecond=0)


def extractor(data, key="id"):
    return [x[key] for x in data]


def check_with_default(data, default):
    if data is not None:
        return data
    else:
        return default


def box_check():
    """Make sure only one latest added box is checked"""

    leveranser = Table(api_key, base_id, "Leveranser")
    all_checked = leveranser.all(view="Icheckat")
    if len(all_checked) == 0:
        record = leveranser.first()['id']
        leveranser.update(record, {"latest added": True})
    while len(all_checked) > 1:
        leveranser.update(all_checked[0]['id'], {"latest added": False})
        del all_checked[0]


class Gig:
    def __init__(self, input_RID):
        self.tid_rapport = []

        with open("config.json", "r", encoding="utf-8") as f:
            config = json.load(f)

        with open("output.json", "r", encoding="utf-8") as f:
            prev_out = json.load(f)

        self.data = orm.input_data()
        self.data.id = input_RID
        self.data.fetch()
        print(self.data)
        self.output_record = orm.Leverans()
        if self.data.uppdateraa:
            self.output_record.id = self.data.uppdateraProjekt[0].id
            self.output_record.fetch()
        else:
            self.output_record.status = "Obekräftat projekt"

        if self.data.ny_slutkund:
            self.slutkund = orm.Slutkund(name=self.data.ny_slutkund)
            self.slutkund.save()
        elif self.data.slutkund is not None:
            self.slutkund = self.data.slutkund[0]
            self.slutkund.fetch()
        else:
            self.slutkund = orm.Slutkund()

        if self.data.ny_beställare_bool:
            if self.data.ny_kund:
                self.kund = orm.Kund(name=self.data.ny_kund)
                self.kund.save()
            else:
                self.kund = self.data.koppla_till_kund[0]
                self.kund.fetch()
            self.bestallare = orm.Bestallare(
                name=self.data.ny_beställare, kund=[self.kund]
            )
            self.bestallare.save()
            self.bestallare.fetch()
            self.output_record.beställare = [self.bestallare]
            self.output_record.kund = [self.kund]
            #get_prylar()
        elif self.data.beställare is not None:
            self.bestallare = self.data.beställare[0]
            self.bestallare.fetch()
            self.bestallare.kund
            self.kund = self.bestallare.kund[0]
            self.kund.fetch()
            self.output_record.beställare = [self.bestallare]
            self.output_record.kund = [self.kund]

        if self.output_record.kund is None:
            self.kund = orm.Kund()
        if self.output_record.beställare is None:
            self.bestallare = None
        self.extra_name = check_with_default(self.data.extra_name, "")
        assert self.data.börja_datum is not None
        self.start_date = self.data.börja_datum.replace(hour=0).astimezone(
            pytz.timezone('Europe/Stockholm')
        )

        if self.data.sluta_datum is not None:
            self.end_date = self.data.sluta_datum.replace(hour=0).astimezone(
                pytz.timezone('Europe/Stockholm')
            )
        else:
            self.end_date = self.start_date
        self.start_date
        self.output_record.sluta_datum = self.end_date
        self.output_record.börja_datum = self.start_date
        self.output_record.name = self.make_name()

        self.person_field_list = [
            'Bildproducent', 'Fotograf', 'Ljudtekniker', 'Ljustekniker',
            'Grafikproducent', 'Animatör', 'Körproducent',
            'Innehållsproducent', 'Scenmästare', 'Tekniskt_ansvarig',
            'Klippare'
        ]

        # Make a dict of all the types of tasks with lists of people recIDs inside
        self.person_dict_grouped = {
            x: getattr(self.data, x)
            for x in self.person_field_list
            if getattr(self.data, x) is not None
        }
        self.person_list = []

        # Make a de-duped list of all the people involved in the gig
        [
            self.person_list.append(item) for sublist in [
                self.person_dict_grouped[key]
                for key in self.person_dict_grouped
            ] for item in sublist if item not in self.person_list
        ]

        if self.data.existerande_adress is not None:
            self.adress = self.data.existerande_adress[0]
        elif self.data.Adress is not None:
            self.adress = orm.Adressbok(name=self.data.Adress)
        else:
            self.adress = orm.Adressbok()

        self.adress_update = False
        self.tid_to_adress_car = None
        #self.tid_to_adress = self.adress.used_time
        self.antal_paket = None
        self.gmaps = googlemaps.Client(key=os.environ["maps_api"])
        self.url = None
        self.dagar_amount = (
            self.output_record.sluta_datum - self.output_record.börja_datum
        ).days + 1
        self.dagar_list: list[tuple[datetime.datetime, datetime.datetime]] = []
        self.extra_gig_tid = None
        self.ob_mult = None
        self.avkastning_gammal = None
        self.tim_budget_personal = None
        self.tim_budget_frilans = None
        self.ob_dict = {}
        self.bad_day_dict = {}
        self.day_dict = {}
        self.dag_längd = None
        self.time_dif = None
        self.avkastning_without_pris = None
        self.hyr_things = None
        self.pryl_fonden = None
        self.output_table = Table(api_key, base_id, "Leveranser")
        self.kalender_table = Table(api_key, base_id, "Projektkalender")
        self.slit_kostnad = None
        self.avkastning = None
        self.pryl_marginal = None
        self.kostnad = None
        self.pryl_kostnad = 0.0
        self.hyr_pris = None
        self.tim_budget = None
        self.restid: float
        self.rigg_timmar: float
        self.begin_earlier: float = self.data.Börja_tidigare if self.data.Börja_tidigare is not None else 0
        self.gig_timmar = 0
        self.tim_pris = None
        if self.data.Projekt is not None:
            self.projekt = self.data.Projekt[0]
        else:
            self.projekt = orm.Projekt()
            self.projekt.save()
        self.specifik_personal = self.person_list
        self.comment = check_with_default(self.data.Anteckning, "")

        self.output_record.Personal = check_with_default(
            self.data.extraPersonal, 0.0
        )
        assert self.output_record.Personal is not None
        self.output_record.extraPersonal = check_with_default(
            self.data.extraPersonal, 0.0
        )

        self.marginal = 0
        self.gig_prylar = {}
        self.pre_gig_prylar = []
        self.projekt_timmar_add = check_with_default(
            self.data.projekt_timmar, 0
        )

        self.projekt_timmar = None
        self.frilans_hyrkostnad = 0
        self.frilans_lista = []

        if self.data.Frilans is not None:
            self.frilans = len(self.data.Frilans)
            with open("frilans.json", "r", encoding="utf-8") as f:
                frilans_list = json.load(f)
            for frilans in self.data.Frilans:
                self.frilans_lista.append(frilans)
        else:
            self.frilans = 0

        self.post_text_kostnad = 0
        self.post_text_pris = 0
        self.output_record.Pryl_pris = 0.0
        self.output_record.Pris = 0.0
        self.in_pris = 0

        self.config = config
        self.start_time = time.time()

        self.update = self.data.uppdateraa if self.data.uppdateraa is not None else False

        #if self.update:
        #    self.name = prev_out[self.g_data("uppdateraProjekt")[0]].get('Gig namn', self.make_name())
        self.extra_prylar = self.data.extraPrylar
        self.prylpaket = self.data.prylPaket

        self.svanis = self.data.Svanis
        for paket in self.prylpaket if self.prylpaket is not None else []:
            if paket.svanis:
                self.svanis = True
                break

        # Take all prylar and put them inside a list
        if self.extra_prylar is not None:
            self.check_prylar()
        # Take all prylar from paket and put them inside a list
        if self.prylpaket is not None:
            self.check_paket()

        # Add accurate count to all prylar and compile them from list to dict
        self.count_them()
        # Modify pryl_pris based on factors such as svanis
        self.pryl_mod(config)

        self.adress_check()
        if self.adress.exists():
            self.output_record.Adress = [self.adress]
        self.rakna_timmar(config)

        self.tid(config)

        self.post_text_func()

        self.personal_rakna(config)

        self.marginal_rakna(config)

        box_check()

        self.output()

        #if self.use_inventarie:
        #self.inventarie()

        self.url_make()

        box_check()

        # self.make_tidrapport()
        self.output_to_json()
        #google_drive_handler.do_one(self.projekt)

        for record in orm.get_all_in_orm(orm.Leverans):
            if record.latest_added and record.id != self.output_record.id:
                record.latest_added = False
                record.save()

    def make_name(self):
        if self.start_date != self.end_date:
            name = self.start_date.strftime(
                "%-y%m%d"
            ) + " ➜ " + self.end_date.strftime("%d%m")
        else:
            name = self.start_date.strftime("%-y%m%d")
        if self.kund.exists():
            if self.kund.name is None:
                self.kund.fetch()
            assert self.kund.name is not None
            name += " | " + self.kund.name
        if self.slutkund.exists():
            if self.slutkund.name is None:
                self.slutkund.fetch()
            if self.kund.exists():
                name += " ➜ "
            assert self.slutkund.name is not None
            name += self.slutkund.name
        if self.extra_name is not None:
            name += " | " + self.extra_name
        return name

    def make_format_for_roles(self):
        with open("folk.json", "r", encoding="utf-8") as f:
            folk = json.load(f)
        out = "## Arbetsroller\n"
        for key, value in self.person_dict_grouped.items():
            out += f"### {key}\n"
            for person in value:
                out += f"### - {person.name}\n"
            out += "\n"
        return out

    def check_prylar(self):
        antal: list[tuple[orm.Prylar, int]] = []

        if self.data.antalPrylar is not None:
            if "," in self.data.antalPrylar:
                antal_list = self.data.antalPrylar.split(",")
                for idx, pryl in enumerate(self.extra_prylar):
                    if idx < len(antal_list):
                        for _ in range(int(antal_list[idx])):
                            self.pre_gig_prylar.append(pryl)
                    else:
                        self.pre_gig_prylar.append(pryl)
            else:
                for idx, pryl in enumerate(self.extra_prylar):
                    if idx == 0:
                        for _ in range(int(self.data.antalPrylar)):
                            self.pre_gig_prylar.append(pryl)
                    else:
                        self.pre_gig_prylar.append(pryl)

        else:
            for pryl in self.data.extraPrylar:
                self.pre_gig_prylar.append(pryl)

    def check_paket(self):
        try:
            self.antal_paket = self.data.antalPaket
            if self.antal_paket:
                try:
                    int(self.antal_paket)
                    self.antal_paket = [self.antal_paket]
                except ValueError:
                    self.antal_paket = self.antal_paket.split(",")
            antal = self.antal_paket
        except KeyError:
            antal = None
        if self.data.prylPaket is not None:
            for paket in self.data.prylPaket:
                if paket.name is None:
                    paket.fetch()
                # Check svanis
                try:
                    if paket.svanis:
                        self.svanis = True
                except KeyError:
                    pass
                # Get personal
                if self.output_record.Personal is None:
                    self.output_record.Personal = 0.0
                self.output_record.Personal += paket.personal if paket.personal is not None else 0.0

                paket.fetch()
                for pryl in paket.get_all_prylar():
                    if pryl.name is None:
                        pryl.fetch()
                    self.pre_gig_prylar.append(pryl)

    def count_them(self):
        self.pryl_lista: list[tuple[orm.Prylar, int]] = []
        new_list = []
        for x in self.pre_gig_prylar:
            if x not in new_list:
                new_list.append(x)
        for pryl in new_list:
            count = 0
            for thing in self.pre_gig_prylar:
                if pryl == thing:
                    count += 1
            self.pryl_lista.append((pryl, count))

    def pryl_mod(self, config):
        if self.output_record.Pryl_pris is None:
            self.output_record.Pryl_pris = 0.0
        for pryl, count in self.pryl_lista:

            # Mult price by amount of pryl
            if pryl.pris is None:
                pryl.fetch()
            assert pryl.pris is not None
            mod_pryl = pryl.pris * count

            # If svanis, mult by svanis multi
            if self.svanis:
                mod_pryl = int(float(mod_pryl) * config["svanisMulti"])
            pris = self.dagar(config, mod_pryl)
            if pris is not None:
                self.output_record.Pryl_pris += pris
        if self.output_record.Pris is None:
            self.output_record.Pris = 0.0
        self.output_record.Pris += self.output_record.Pryl_pris
        self.pryl_kostnad = self.output_record.Pryl_pris * 0.4

    def dagar(self, config, pris):
        assert self.output_record.sluta_datum is not None and self.output_record.börja_datum is not None
        dagar = (
            self.output_record.sluta_datum - self.output_record.börja_datum
        )

        dag_tva_multi = config["dagTvåMulti"]
        dag_tre_multi = config["dagTreMulti"]
        temp_pris = copy.deepcopy(pris)
        #if type(dagar) is dict:
        #    dagar = 1

        if dagar.days + 1 < 1:
            temp_pris = 0
        elif dagar.days + 1 >= 2:
            temp_pris *= 1 + dag_tva_multi
        if dagar.days + 1 >= 3:
            temp_pris += pris * dag_tre_multi * (dagar.days + 1 - 2)
        return temp_pris * 1.0

    def adress_check(self):
        if self.adress.name is not None and self.adress.used_time is None and not self.svanis:
            print("using maps api")

            self.adress_update = True
            self.car = False

            gmaps_bike = self.gmaps.distance_matrix(
                origins="Levande video",
                destinations=self.adress.name,
                mode="bicycling",
                units="metric",
            )

            try:
                self.adress.time_bike = gmaps_bike['rows'][0]['elements'][0][
                    'duration']['value']
                print(self.adress.time_bike)
            except KeyError:
                raise InvalidMapsAdress("Invalid adress")
            if self.adress.time_bike / 60 > 60:
                self.car = True
                gmaps_car = self.gmaps.distance_matrix(
                    origins="Levande video",
                    destinations=self.adress.name,
                    mode="driving",
                    units="metric",
                )
                try:
                    self.adress.time_car = gmaps_car["rows"][0]["elements"][0][
                        "duration"]["value"]
                except KeyError:
                    raise InvalidMapsAdress("Invalid adress")
            self.adress.distance = str((
                self.adress.time_car
                if self.adress.time_car is not None else self.adress.time_bike
            ) / 60 / 60) + "h"
            self.adress.kund = [self.kund]
            for record in self.adress.all():
                if record["fields"]["Adress"] == self.adress.name:
                    self.adress.id = record["id"]
                    break
            self.adress.save()

    def rakna_timmar(self, config):
        #Custom riggtimmar
        if self.data.special_rigg is not None and self.data.special_rigg == 1:
            assert self.data.rigg_timmar_spec is not None
            self.rigg_timmar = self.data.rigg_timmar_spec / self.output_record.Personal if self.output_record.Personal is not None and self.output_record.Personal > 0.0 else 0.0

        else:
            self.rigg_timmar = math.floor(
                self.output_record.Pryl_pris * config["andelRiggTimmar"] /
                self.output_record.Personal
            ) if self.output_record.Personal is not None and self.output_record.Personal > 0 else 0
        if self.adress.exists() and self.adress.name is None:
            self.adress.fetch()
        if self.adress.used_time is not None:
            self.restid = self.adress.used_time / 60 / 60
        else:
            self.restid = self.dagar_amount * config["restid"]

        if self.svanis:
            self.restid = 0.0

        if self.restid is None:
            self.restid = 0.0
        self.restid = round(self.restid * 12) / 12

        self.per_pers_restid = self.restid * 2.0 * float(
            self.dagar_amount
        ) if self.restid < 2.0 else self.restid * 2.0

    def tid(self, config):
        self.dagar_changes = []
        self.restid_list = []
        ins = [
            datetime.time.
            fromisoformat(time_thing if ":" in time_thing else "00:00")
            for combined in (
                self.data.getin_getout if self.data.
                getin_getout is not None else "00:00,00:00-00:00,00:00"
            ).split(",") for time_thing in
            (combined.split("-") if "-" in combined else [combined, "00:00"])
        ]

        self.mgetins, self.mgetouts = ins[0::2], ins[1::2]

        self.mgets_outs_true = (
            self.mgetins[0].hour != 0 or self.mgetins[0].minute != 0
        )

        self.bad_day_dict = dict(zip(calendar.day_name, range(7)))
        i = 1
        for day in self.bad_day_dict:
            self.day_dict[i] = day
            i += 1

        self.end_date = self.data.sluta_datum
        hours_total = 0

        if self.data.tid_för_gig is not None:
            try:
                self.extra_gig_tid = self.data.tid_för_gig.split(",")

            except AttributeError:
                self.extra_gig_tid = []
                for _ in range(int(self.dagar_amount)):
                    self.extra_gig_tid.append(self.data.tid_för_gig)

            while len(self.extra_gig_tid) < self.dagar_amount:
                self.extra_gig_tid.append(self.extra_gig_tid[0])

            self.program_tider: tuple[
                list[datetime.time], list[datetime.time]] = ([
                    datetime.time.fromisoformat(
                        split_tid.split("-")[0] if ":" in
                        split_tid.split("-")[0] else "00:00"
                    ) for split_tid in self.extra_gig_tid
                ], [
                    datetime.time.fromisoformat(
                        split_tid.split("-")[1] if ":" in
                        split_tid.split("-")[1] else "00:00"
                    ) for split_tid in self.extra_gig_tid
                ])  # new thing, redoing stuff

            for starts, ends in zip(
                self.program_tider[0], self.program_tider[1]
            ):
                self.gig_timmar += (ends.hour + ends.minute /
                                    60) - (starts.hour + starts.minute / 60)

            self.gig_timmar /= len(self.program_tider[0])

            if self.mgets_outs_true:
                self.riggtimmar = 0
                for starts, ends in zip(self.mgetins, self.mgetouts):
                    self.riggtimmar += (ends.hour + ends.minute / 60) - (
                        starts.hour + starts.minute / 60
                    ) - self.gig_timmar
                self.riggtimmar /= len(self.mgetins)

            for idx, tid in enumerate(self.extra_gig_tid):
                tup: tuple[str, str] = tuple(tid.split("-"))
                start: tuple[int, int]
                end: tuple[int, int]

                start, end = map(
                    lambda x: tuple(map(int, x.split(":")))
                    if ":" in x else tuple(map(int, [x, "0"])), tup
                )

                cest = pytz.timezone("Europe/Stockholm")

                if self.mgets_outs_true:
                    rigg_after = 0
                    rigg_before = 0
                else:
                    if self.rigg_timmar > 1:  # Om mer än 1 timme gå till följande logik
                        if self.rigg_timmar > 2:  # Rigg efter gig max på 1, resten går till innan
                            rigg_after = 1
                            rigg_before = self.rigg_timmar - 1
                        else:  # Om tiden är mer är mer än 1 timme men mindre än 2, splitta jämt mellan
                            rigg_after = self.rigg_timmar / 2
                            rigg_before = self.rigg_timmar / 2
                    else:  # Minimum extra tid innan & efter är en halvtimme
                        rigg_after = 0.5
                        rigg_before = 0.5
                check = False
                default_restid = 0
                if self.restid < 2 * 60 * 60:
                    check = True
                if check:
                    if idx == 0:
                        beginn = self.restid
                        endn = default_restid
                    elif idx == len(self.extra_gig_tid) - 1:
                        beginn = default_restid
                        endn = self.restid
                    else:
                        beginn, endn = default_restid, default_restid
                else:
                    beginn, endn = self.restid, self.restid
                self.restid_list.append((beginn, endn))

                rigg_res_start = (
                    datetime.timedelta(
                        hours=rigg_before + beginn + self.begin_earlier
                    )
                )
                rigg_res_end = (datetime.timedelta(hours=rigg_after + endn))

                self.dagar_changes.append((rigg_res_start, rigg_res_end))

                if len(self.mgetins) > idx and self.mgets_outs_true:
                    self.dagar_list.append((
                        datetime.datetime.combine(
                            self.start_date + datetime.timedelta(days=idx),
                            self.mgetins[idx]
                        ) - datetime.timedelta(hours=beginn),
                        datetime.datetime.combine(
                            self.start_date + datetime.timedelta(days=idx),
                            self.mgetouts[idx]
                        ) + datetime.timedelta(hours=endn)
                    ))

                else:
                    self.dagar_list.append((
                        self.start_date + datetime.
                        timedelta(days=idx, hours=start[0], minutes=start[1]) -
                        rigg_res_start, self.start_date + datetime.
                        timedelta(days=idx, hours=end[0], minutes=end[1]) +
                        rigg_res_end
                    ))

                hours_total += (
                    self.dagar_list[-1][1].timestamp() -
                    self.dagar_list[-1][0].timestamp()
                ) / 60 / 60

        while len(self.mgetins) < len(self.dagar_list):
            self.mgetouts.append(None)
            self.mgetins.append(None)
        self.ob_dict = {"0": [], "1": [], "2": [], "3": [], "4": []}

        skärtorsdagen = None
        for date, holiday in holidays.SWE(False,
                                          years=self.end_date.year).items():
            if holiday == "Långfredagen":
                skärtorsdagen = date - datetime.timedelta(days=1)
                break
        for begin, stop in self.dagar_list:
            # Loopa igenom varje timme avrundat till närmaste halvtimme
            for idx, hour in enumerate(
                range(round((stop.timestamp() - begin.timestamp()) / 60 / 30))
            ):
                hour /= 2
                # Räkna ut ob och lägg i en dict

                if idx + 1 == round(
                    (stop.timestamp() - begin.timestamp()) / 60 / 30
                ):  # Check if last
                    temp_date = stop
                else:
                    temp_date = begin + datetime.timedelta(hours=hour)

                if temp_date in holidays.SWE(False, years=temp_date.year):
                    if (
                        holidays.SWE(False, years=temp_date.year)[temp_date]
                        in [
                            "Trettondedag jul", "Kristi himmelsfärdsdag",
                            "Alla helgons dag", "Första maj"
                        ] and temp_date.hour >= 7
                    ):
                        self.ob_dict["3"].append(temp_date)
                    elif (
                        holidays.SWE(False, years=temp_date.year)[temp_date]
                        in ["Nyårsafton"] and temp_date.hour >= 18
                        or holidays.SWE(False,
                                        years=temp_date.year)[temp_date] in [
                                            "Pingstdagen",
                                            "Sveriges nationaldag",
                                            "Midsommarafton",
                                            "Julafton",
                                        ] and temp_date.hour >= 7
                    ):
                        self.ob_dict["4"].append(temp_date)
                    else:
                        self.ob_dict["0"].append(temp_date)
                elif (
                    str(temp_date).split(" ")[0] == str(skärtorsdagen)
                    and temp_date.hour >= 18
                ):
                    self.ob_dict["4"].append(temp_date)
                elif temp_date.isoweekday() < 6:
                    if temp_date.hour >= 18:
                        self.ob_dict["1"].append(temp_date)
                    elif temp_date.hour < 7:
                        self.ob_dict["2"].append(temp_date)
                    else:
                        self.ob_dict["0"].append(temp_date)
                elif temp_date.isoweekday() == 6 or temp_date.isoweekday(
                ) == 7:
                    self.ob_dict["3"].append(temp_date)
                else:
                    self.ob_dict["0"].append(temp_date)

            self.start_date += datetime.timedelta(days=1)

        self.ob_text = "OB för en personal:\n"

        for key, value in self.ob_dict.items():
            value: list[datetime.datetime]
            if len(value) > 0:  # and key != "0":
                if key == "0":
                    self.ob_text += f"Timmar utan OB: {len(value) / 2}\n"
                else:
                    self.ob_text += f"OB {key}: {len(value) / 2}\n"

        avg = hours_total / len(self.dagar_list)

        self.dag_längd = avg

        self.ob_mult = 0
        self.ob_mult += len(self.ob_dict["0"]) / 2 * config["levandeVideoLön"]
        self.ob_mult += len(self.ob_dict["1"]) / 2 * (
            config["levandeVideoLön"] +
            (config["levandeVideoLön"] * 168 / 600)
        )
        self.ob_mult += len(self.ob_dict["2"]) / 2 * (
            config["levandeVideoLön"] +
            (config["levandeVideoLön"] * 168 / 400)
        )
        self.ob_mult += len(self.ob_dict["3"]) / 2 * (
            config["levandeVideoLön"] +
            (config["levandeVideoLön"] * 168 / 300)
        )
        self.ob_mult += len(self.ob_dict["4"]) / 2 * (
            config["levandeVideoLön"] +
            (config["levandeVideoLön"] * 168 / 150)
        )
        self.ob_mult /= self.dag_längd * len(self.dagar_list)

    def personal_rakna(self, config):
        total_personal = self.output_record.Personal

        if len(self.person_list) > total_personal:
            total_personal = len(self.person_list)
        # Add additional personal from specifik personal to the total personal

        self.bas_lön = self.ob_mult
        self.sociala_avgifter = config["socialaAvgifter"] + 1

        self.lön_kostnad = self.bas_lön * self.sociala_avgifter

        self.timpris = math.floor(
            self.lön_kostnad * config["lönJustering"] / 10
        ) * 10

        if self.projekt_timmar is None:
            # Slask timmar för tid spenderat på planering
            self.projekt_timmar = math.ceil(
                (self.gig_timmar + self.rigg_timmar) * config["projektTid"] /
                total_personal if total_personal != 0 else 0
            ) + (
                self.projekt_timmar_add / total_personal
                if total_personal != 0 and total_personal is not None else 0
            )

        self.tim_dict = {
            'gig': int(self.gig_timmar),
            'rigg': int(self.rigg_timmar),
            'proj': int(self.projekt_timmar),
            'res': int(self.restid),
        }
        total_tid = (
            self.gig_timmar * self.dagar_amount + self.rigg_timmar +
            self.projekt_timmar + self.per_pers_restid
        ) * total_personal if total_personal is not None and total_personal > 0 else 0
        self.frilans_kostnad, self.total_tim_frilans, self.antal_frilans = 0, 0, 0
        if self.output_record.frilans_uträkningar is not None:
            for uträkning in self.output_record.frilans_uträkningar:
                uträkning.delete()
            self.output_record.frilans_uträkningar = []
        for person in self.person_list:
            if person.name is None:
                person.fetch()
                person.fix()
                if not person.levande_video:
                    person.make_frilans_costs()
            if not person.levande_video and person.input_string is not None:
                cost = person.get_cost(self.tim_dict)
                self.frilans_kostnad += cost[0]
                self.total_tim_frilans += cost[1]
                self.antal_frilans += 1
                if self.output_record.frilans_uträkningar is None:
                    self.output_record.frilans_uträkningar = []
                self.output_record.frilans_uträkningar.append(
                    person.set_frilans_cost()
                )

        # self.folk = Folk(self.lön_kostnad, self.timpris, config['hyrMulti'])
        # self.frilans_kostnad, self.total_tim_frilans, self.antal_frilans, self.frilans_personal_dict = self.folk.total_cost(
        #     self.person_list, self.tim_dict, False, self.person_dict_grouped#[key for person in self.person_list for key, value in self.person_dict_grouped.items() if person == value]
        # )

        self.levande_video_kostnad = self.lön_kostnad * (
            total_tid/total_personal
        ) * (
            total_personal - self.antal_frilans
        ) if total_personal > self.antal_frilans else 0

        self.output_record.personal_kostnad = self.frilans_kostnad + self.levande_video_kostnad
        self.output_record.Personal_pris = self.timpris * total_tid  # Frilans is not used for pris

        #TODO FIX THIS
        self.total_tim_budget = total_tid

        #Theoretical cost if only done by lv
        self.teoretisk_lön_kostnad = self.total_tim_budget * self.lön_kostnad
        self.teoretisk_lön_pris = self.total_tim_budget * self.timpris
        self.output_record.Personal = total_personal * 1.0
        self.output_record.restid = int(
            self.per_pers_restid *
            check_with_default(self.output_record.Personal, 0.0)
        )

    def post_text_func(self):
        try:
            if self.data.post_text:
                self.post_text_pris = (
                    self.data.Textning_minuter *
                    self.config["textningPostPris"]
                )
                self.post_text_kostnad = (
                    self.data.Textning_minuter *
                    self.config["textningPostKostnad"]
                )
        except KeyError:
            pass

    def marginal_rakna(self, config):
        try:
            if self.data.hyrKostnad is None:
                self.data.hyrKostnad = 0.0
        except KeyError:
            self.data.hyrKostnad = 0.0

        self.hyr_pris = self.data.hyrKostnad * (1 + config["hyrMulti"])

        self.kostnad = (
            self.pryl_kostnad + self.data.hyrKostnad + self.post_text_kostnad +
            self.output_record.personal_kostnad
        )

        self.output_record.Pris += self.hyr_pris + self.post_text_pris + self.output_record.Personal_pris

        #Teoretiska ifall enbart gjort av LV
        self.teoretisk_kostnad = self.kostnad - self.frilans_kostnad - self.levande_video_kostnad + self.teoretisk_lön_kostnad

        if self.output_record.Pryl_pris is not None and self.output_record.Pryl_pris != 0:
            if self.pryl_kostnad is not None:
                self.pryl_marginal = (
                    self.output_record.Pryl_pris - int(self.pryl_kostnad)
                ) / self.output_record.Pryl_pris
            else:
                raise ValueError("Pryl kostnad is None")
        else:
            self.pryl_marginal = 0

        self.slit_kostnad = self.output_record.Pryl_pris * config["prylSlit"]
        self.pryl_fonden = self.slit_kostnad * (
            1 + config["Prylinv (rel slit)"]
        )
        print(self.output_record.Pris)
        self.avkastning = round(self.output_record.Pris - self.kostnad)

        self.teoretisk_avkastning = round(
            self.output_record.Pris - self.teoretisk_kostnad
        )

        self.hyr_things = self.data.hyrKostnad * (
            1 - config["hyrMulti"] * config["hyrMarginal"]
        )
        try:
            self.marginal = (
                round(
                    self.avkastning /
                    (self.output_record.Pris - self.hyr_things) * 10000
                ) / 100
            )
        except ZeroDivisionError:
            self.marginal = 0
        try:
            self.teoretisk_marginal = (
                round(
                    self.teoretisk_avkastning /
                    (self.output_record.Pris - self.hyr_things) * 10000
                ) / 100
            )
        except ZeroDivisionError:
            self.teoretisk_marginal = 0
        print(self.marginal, self.teoretisk_marginal)

    def output(self):
        print(f"Post Text: {self.post_text_pris}")
        print(f"Pryl: {self.output_record.Pryl_pris}")
        print(f"Personal: {self.output_record.Personal_pris}")
        print(f"Total: {self.output_record.Pris}")
        print(f"Avkastning: {self.avkastning}")

        if self.marginal > 65:
            print(
                f"Marginal: {Bcolors.OKGREEN + str(self.marginal)}%{Bcolors.ENDC}"
            )
        else:
            print(
                f"Marginal: {Bcolors.FAIL + str(self.marginal)}%{Bcolors.ENDC}"
            )

        packlista = "## Prylar:\n\n"
        self.pryl_lista = sorted(
            self.pryl_lista, key=lambda item: -1 * item[1]
        )

        for pryl, amount in self.pryl_lista:
            packlista += f"### {amount}st {pryl.name}\n\n"
            print(f"\t{amount}st {pryl.name}")

        paket_id_list = []
        pryl_id_list = []

        if self.prylpaket is None:
            self.prylpaket = []

        if self.extra_prylar is None:
            self.extra_prylar = []

        antal_string = ""

        if self.data.antalPrylar is not None:
            for antal in self.data.antalPrylar:
                if antal_string == "":
                    antal_string += antal
                else:
                    antal_string += "," + antal

        antal_paket_string = ""
        if self.data.antalPaket is not None and self.antal_paket is not None:
            for antal in self.antal_paket:
                if antal_paket_string == "":
                    antal_paket_string += antal
                else:
                    antal_paket_string += "," + antal

        try:
            with open("output.json", "r", encoding="utf-8") as f:
                old_output = json.load(f)
            with open("log.json", "r", encoding="utf-8") as f:
                log = json.load(f)
        except OSError:
            old_output = {}
            log = []
        self.log = log

        leverans_nummer = 1

        self.old_output = old_output
        # Move this to top
        self.post_text: bool | None = self.data.post_text

        if self.bestallare:
            print(self.kund.name, self.bestallare.name)
        self.projekt_typ = self.data.Projekt_typ if self.data.Projekt_typ is not None else "live"
        riggdag = self.projekt_typ == 'Rigg'

        self.output_record.Projekt_kanban = self.output_record.name
        self.output_record.Projekt_timmar = int(
            float(self.gig_timmar) * self.output_record.Personal *
            float(len(self.dagar_list))
        )
        self.output_record.Rigg_timmar = int(
            self.rigg_timmar * (
                self.output_record.Personal
                if self.output_record.Personal is not None else 0
            )
        )

        self.output_record.prylPaket = self.prylpaket
        self.output_record.extraPrylar = self.extra_prylar
        print(self.prylpaket, self.extra_prylar)
        self.output_record.antalPrylar = antal_string
        self.output_record.antalPaket = antal_paket_string
        self.output_record.projektledare = self.data.projektledare
        self.output_record.latest_added = True
        self.output_record.producent = self.data.producent
        self.output_record.Projekt = [self.projekt]
        self.output_record.dagar = len(self.dagar_list)
        self.output_record.packlista = packlista
        self.output_record.projektTid = int(
            self.projekt_timmar * self.output_record.Personal
        )
        self.output_record.dagLängd = self.dag_längd
        self.output_record.slitKostnad = self.slit_kostnad
        self.output_record.prylFonden = self.pryl_fonden
        self.output_record.hyrthings = self.hyr_things
        self.output_record.avkastWithoutPris = float(self.avkastning)
        self.output_record.avkast2 = float(self.teoretisk_avkastning)
        self.output_record.frilanstimmar = check_with_default(
            self.tim_budget_frilans, 0.0
        )
        #self.output_record.ny
        self.output_record.leverans_nummer = leverans_nummer
        self.output_record.typ = self.projekt_typ
        self.output_record.input_id = self.data.id
        self.output_record.post_deadline = check_with_default(
            self.data.post_deadline, datetime.datetime.min
        )
        self.output_record.All_personal = self.person_list
        self.output_record.slutkund_temp = [self.slutkund]
        self.output_record.role_format = self.make_format_for_roles()
        self.output_record.extra_namn = self.extra_name
        self.output_record.ob = self.ob_text
        self.output_record.Kommentar_från_formulär = self.comment

        if riggdag:
            self.output_record.eget_pris = 0
            self.output_record.rabatt = 1.0

        self.output_record.Bildproducent = self.data.Bildproducent if self.data.Bildproducent is not None else []
        self.output_record.Ljudtekniker = self.data.Ljudtekniker if self.data.Ljudtekniker is not None else []
        self.output_record.Fotograf = self.data.Fotograf if self.data.Fotograf is not None else []
        self.output_record.Ljustekniker = self.data.Ljustekniker if self.data.Ljustekniker is not None else []
        self.output_record.Animatör = self.data.Animatör if self.data.Animatör is not None else []
        self.output_record.Körproducent = self.data.Körproducent if self.data.Körproducent is not None else []
        self.output_record.Scenmästare = self.data.Scenmästare if self.data.Scenmästare is not None else []
        self.output_record.Klippare = self.data.Klippare if self.data.Klippare is not None else []
        self.output_record.Tekniskt_ansvarig = self.data.Tekniskt_ansvarig if self.data.Tekniskt_ansvarig is not None else []
        self.output_record.Innehållsproducent = self.data.Innehållsproducent if self.data.Innehållsproducent is not None else []
        self.output_record.Grafikproducent = self.data.Grafikproducent if self.data.Grafikproducent is not None else []
        self.output_record.Resten = []
        if self.output_record.projekt_kalender is None:
            self.output_record.projekt_kalender = []
        for key in self.person_dict_grouped.keys():
            if key not in ["Bildproducent", "Ljudtekniker"]:
                for person in self.person_dict_grouped[key]:
                    self.output_record.Resten.append(person)
        # TODO
        #if self.projekt_typ == "Rigg":
        #    (output.pop(x) for x in ["Pris", "prylPaket", "extraPrylar"])

        print(time.time() - self.start_time)

        if not self.output_record.exists():
            assert self.output_record.save()
        else:
            self.output_record.save()

        print(time.time() - self.start_time)
        self.airtable_record = self.output_record.id
        # print(output)
        projektkalender_records = []

        i = 0
        calendar_records: list[orm.Projektkalender] = []
        # Add the dates to the projektkalender table
        if self.update:
            for record in self.output_record.projekt_kalender:
                # Get all record ids of the already existing linked records in the projektkalender table
                if record.getin_hidden is None:
                    record.fetch()
                calendar_records.append(record)

        calendar_records = sorted(
            calendar_records, key=lambda x: x.getin_hidden, reverse=True
        )

        self.output_record.save()

        if self.dagar_list is not None:
            for idx, (getin, getout) in enumerate(self.dagar_list):
                if idx < len(calendar_records):
                    record = calendar_records[idx]
                else:
                    calendar_records.append(orm.Projektkalender())
                    record = calendar_records[-1]
                if record is not None:
                    record.getin_hidden = (
                        getin + self.dagar_changes[idx][0]
                    ).astimezone(pytz.timezone("Europe/Stockholm")
                                 ).replace(tzinfo=None)
                    record.getout_hidden = (
                        getout - self.dagar_changes[idx][1]
                    ).astimezone(pytz.timezone("Europe/Stockholm")
                                 ).replace(tzinfo=None)
                    record.program_stop_hidden = float(
                        self.program_tider[1][idx].hour * 60 * 60 +
                        self.program_tider[1][idx].minute *
                        60 if self.program_tider[1][idx] is not None else None
                    )
                    record.program_start_hidden = float(
                        self.program_tider[0][idx].hour * 60 * 60 +
                        self.program_tider[0][idx].minute *
                        60 if self.program_tider[0][idx] is not None else None
                    )
                    record.actual_getin = (
                        getin +
                        datetime.timedelta(hours=self.restid_list[idx][0])
                    ).hour * 60 * 60 + (
                        getin +
                        (datetime.timedelta(hours=(self.restid_list[idx][0])))
                    ).minute * 60
                    record.actual_getout = (
                        getout -
                        datetime.timedelta(hours=self.restid_list[idx][1])
                    ).hour * 60 * 60 + (
                        getout -
                        datetime.timedelta(hours=self.restid_list[idx][1])
                    ).minute * 60
                    record.åka_från_svanis = getin.hour * 60 * 60 + getin.minute * 60
                    record.komma_tillbaka_till_svanis = getout.hour * 60 * 60 + getout.minute * 60
                    record.projekt = [self.output_record.Projekt[0]]
                    self.output_record.projekt_kalender.append(record)

        else:
            raise ValueError("dagar_list empty")

        for record in calendar_records:
            if not record.exists():
                assert record.save()
            else:
                # Make sure not to update computed fields
                fields = [
                    "fldO8TzRQVNgt02qU", "fldITTqANmwPUjYuC",
                    "fldAnBswzCzNt7OFs", "fldDVxfuTkDruHHL8",
                    "flddD7XrPVHYHIPST", "fldVAczarHpOYDfWn",
                    "fldUPh7sIGcpNoDkL", "fldOgfAK8SlXhzKgH",
                    "fldPRDJlVSSOfccb8", "fldXXtWhMURLywgE3",
                    "fldnOyMoIQlfEJNXb", "fldj3L72EeGGRE0gV",
                    "fldjsKIIPTOhfg7gW", "fld81rwHaQu7eRx53",
                    "fldJunVGOofzOVrov", "fldjq2WoRhwPnO2xE"
                ]
                for field in fields:
                    record.__dict__["_fields"].pop(field, None)

                record.save()

        # if self.update:
        #     if len(projektkalender_records) != len(record_ids):
        #         self.kalender_table.batch_delete(record_ids)
        #         for record_id in record_ids:
        #             cal_del(record_id)
        #         self.kalender_table.batch_create(projektkalender_records)
        #     else:
        #         self.kalender_table.batch_update(projektkalender_records)
        # else:
        #     self.kalender_table.batch_create(projektkalender_records)
        print(time.time() - self.start_time)
        self.leverans_nummer = leverans_nummer
        try:
            self.tid_rapport = old_output["tidrapport"]
        except KeyError:
            pass

    def url_make(self):

        self.projektledare = self.data.projektledare
        self.producent = self.data.producent
        self.antal_paket = check_with_default(self.data.antalPaket, [])
        self.antal_prylar = check_with_default(self.data.antalPrylar, [])
        self.extra_personal = check_with_default(self.data.extraPersonal, 0)

        params = {
            "prefill_fldMpFwH617TIYHkk": self.projektledare[0].id,
            "prefill_fld2Q7WAm4q5MaLSO": self.producent[0].id,
            "prefill_flddagkZF2A0fGIUF": ",".join([
                x.id for x in self.output_record.prylPaket if x is not None
            ]),
            "prefill_fldSee4Tb6eABK6qY": ",".join([
                x.id for x in self.output_record.extraPrylar if x is not None
            ]),
            "prefill_fldMuiKyy5M4Ic36o": self.antal_paket if
            type(self.antal_paket) is not list else ",".join(self.antal_paket),
            "prefill_fldKPZXPgaAGvypFZ": self.antal_prylar if type(
                self.antal_prylar
            ) is not list else ",".join(self.antal_prylar),
            "prefill_fldgdbo04e5daul7r": self.extra_personal,
            "prefill_fldqpTwSSKNDL9fGT": self.data.hyrKostnad,
            "prefill_fldg8mwbEEcEtsuFy": self.data.tid_för_gig,
            "prefill_fldQJP25CrDQdZGRg": self.post_text,
            "prefill_fldPxGMqLTl0BYZms": self.data.Textning_minuter,
            "prefill_fldnH3dsbRixSXDVI": ",".join([
                x.id for x in self.data.Frilans if x is not None
            ]) if self.data.Frilans is not None else None,
            "prefill_fldKr9l8iJym15vnv": self.adress.id,
            "prefill_fldocj6Gxh5Ss1Ko2": self.bestallare.id
            if self.bestallare is not None else None,
            "prefill_fldS7HP5BJ5hh59VQ": self.slutkund.id
            if self.slutkund.exists() else None,
            "prefill_fldFpABlroJj4muC9": self.projekt_typ,
            "prefill_fld77P6NIqwO6sWTf": self.comment,
            "prefill_fldQibfzkvf2pPPsK": self.projekt_timmar_add,
            "prefill_fldM7myaiGPyiHqNc": self.extra_name,
            "prefill_fldgCwZHHkIj5cxFS": self.data.getin_getout
        }
        equip_url = {
            "prefill_flddagkZF2A0fGIUF": ",".join([
                x.id for x in self.output_record.prylPaket if x is not None
            ]),
            "prefill_fldSee4Tb6eABK6qY": ",".join([
                x.id for x in self.output_record.extraPrylar if x is not None
            ]),
            "prefill_fldMuiKyy5M4Ic36o": self.antal_paket if
            type(self.antal_paket) is not list else ",".join(self.antal_paket),
            "prefill_fldKPZXPgaAGvypFZ": self.antal_prylar if type(
                self.antal_prylar
            ) is not list else ",".join(self.antal_prylar)
        }
        self.output_record.equipment_url = urllib.parse.urlencode(
            equip_url
        ) + "&hide_flddagkZF2A0fGIUF=true&hide_fldSee4Tb6eABK6qY=true&hide_fldMuiKyy5M4Ic36o=true&hide_fldKPZXPgaAGvypFZ=true"
        if len(self.person_field_list) > 0:
            params.update({"prefill_fldsNgx88aUVIqazE": True})
        for work_area in self.person_field_list:
            if work_area in self.person_dict_grouped.keys():
                params.update({
                    f"prefill_{work_area}": ",".join([
                        x.id for x in self.person_dict_grouped[work_area]
                    ])
                })

        update_params = copy.deepcopy(params)
        update_params.update({
            "prefill_fldkZgi81M0SoCbIi": True,
            "prefill_fldG8glSnyO1voEt0": self.output_record.id,
            "prefill_fldgIVyUu8kci0haJ": self.output_record.börja_datum,
            "prefill_fldjr98jyFoWSOsHw": self.data.sluta_datum,
        })
        hidden_update = ["fldkZgi81M0SoCbIi", "fldG8glSnyO1voEt0"]
        for field in hidden_update:
            update_params.update({f"hidden_{field}": True})
        copy_params = copy.deepcopy(params)
        copy_params.update({
            "prefill_fldB06TMygWWfyiyM": False,
            "prefill_fld2IwCPbq7b8Yjik": self.output_record.name,
        })

        params_list = [update_params, copy_params]
        # Remove empty dicts
        for param in params_list:
            del_list = []
            for key, value in param.items():
                if value is None:
                    del_list.append(key)
            for key in del_list:
                del param[key]
        update_params = params_list[0]
        copy_params = params_list[1]

        self.update_url = (
            "https://airtable.com/shrQOV05GKoC6rjJz" + "?" +
            urllib.parse.urlencode(update_params)
        )
        self.copy_url = (
            "https://airtable.com/shrQOV05GKoC6rjJz" + "?" +
            urllib.parse.urlencode(copy_params)
        )

        self.output_record.link_to_update = self.update_url
        self.output_record.link_to_copy = self.copy_url
        self.output_record.save()

    def inventarie(self):
        inventarie = Table(api_key, base_id, "Pryl inventarie")
        inventarie_list: list[orm.Inventarie] = []
        for pryl_id, pryl in self.gig_prylar.items():

            inventarie_list.append(
                orm.Inventarie(
                    based_on=[pryl_id],
                    amount=pryl['amount'],
                    leverans=[self.output_record]
                )
            )
        existing_list = []
        update_list = []
        for record in inventarie.all():
            if record.get('fields',
                          {}).get('Leverans') == self.output_record.id:
                existing_list.append(record['id'])
                if record['fields']['Based on'] not in self.gig_prylar.keys():
                    del existing_list[-1]
                    inventarie.delete(record['id'])
                else:
                    update_list.append(record['id'])
        update = [
            dict_thing for dict_thing in inventarie_list
            if dict_thing['Based on'] in update_list
        ]
        if len(update) > 0:
            inventarie.batch_update(update)
        create = [
            x for x in inventarie_list if x['Based on'] not in existing_list
        ]
        if len(create) > 0:
            inventarie.batch_create(create)

    def make_tidrapport(self):
        tid_table = Table(api_key, base_id, "Tidrapport")
        all_people = []

        for person in self.person_list:

            if person.levande_video:
                all_people.append(person)
        for person in all_people:
            if person is None:
                del all_people[all_people.index(person)]
        records = []

        if self.update:
            if self.output_record.tidrapport is not None:
                for tidrapport in self.output_record.tidrapport:
                    tidrapport.delete()

        for dag in self.dagar_list:
            if self.output_record.tidrapport is None:
                self.output_record.tidrapport = []
                for person in all_people:
                    tidrapport = orm.Tidrapport(
                        start_tid=(dag[0].hour * 60 * 60 + dag[0].minute * 60)
                        * 1.0,
                        tid=((dag[1].hour - dag[0].hour) * 60 * 60 +
                             (dag[1].minute - dag[0].minute) * 60) * 1.0,
                        unused=True,
                        robot=True,
                        datum=dag[0],
                        person=person.name,
                        person_link=[person]
                    )
                    tidrapport.save()
                    self.output_record.tidrapport.append(tidrapport)
        self.output_record.save()

    def output_to_json(self):
        with open("output.json", "w", encoding="utf-8") as f:
            json.dump(self.old_output, f, ensure_ascii=False, indent=2)
        with open("log.json", "w", encoding="utf-8") as f:
            self.log.append({
                f"{self.output_record.name} #{self.leverans_nummer}": self.
                output_record.id
            })
            json.dump(self.log, f, ensure_ascii=False, indent=2)


@app.route("/airtable", methods=["POST"])
@token_required
def fuck_yeah():
    i_data = request.json
    # Load all the important data
    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)
    with open("paket.json", "r", encoding="utf-8") as f:
        paket = json.load(f)
    with open("prylar.json", "r", encoding="utf-8") as f:
        prylar = json.load(f)
    i_data_name = list(i_data.keys())[-1]

    Gig(i_data, config, prylar, paket, i_data_name)
    return "OK!", 200


@app.route("/delete", methods=["POST"])
@token_required
def delete():
    record_id = request.json["content"]
    # Load all the important data
    leverans = orm.Leverans.from_id(record_id)
    if leverans.projekt_kalender is not None:
        for datum in leverans.projekt_kalender:
            datum.delete()
    if leverans.frilans_uträkningar is not None:
        for uträkning in leverans.frilans_uträkningar:
            uträkning.delete()
    if leverans.tidrapport is not None:
        for tid in leverans.tidrapport:
            tid.delete()
    leverans.delete()

    return "OK!", 200


@app.route("/ifuckedup", methods=["GET"])
def take_back():
    with open("output_backup.json", "r", encoding="utf-8") as f:
        backup = json.load(f)
    try:
        with open("output.json", "r", encoding="utf-8") as f:
            output = json.load(f)
    except OSError:
        output = {}

    backup["update"] = False
    requests.post(
        url=  # skipcq  FLK-E251 
        "https://hooks.airtable.com/workflows/v1/genericWebhook/appG1QEArAVGABdjm/wflcP4lYCTDwmSs4g"
        "/wtrzRoN98kiDzdU05",
        json=backup,
    )

    with open("output.json", "w", encoding="utf-8") as f:
        output[backup["Gig namn"]] = backup
        #TODO fix here, can wipe entire db
        #json.dump(output, f, ensure_ascii=False, indent=2)
    return "OK!", 200


@app.route("/test-auth", methods=["POST"])
@token_required
def auth_test():
    return "OK!", 200


@app.route("/start", methods=["POST"])
@token_required
def start():
    input_record_id = request.data.decode("utf-8")
    print('hello')

    if os.environ.get("airtable_debug", "yes") != "no":
        Gig(input_record_id)
    else:
        try:
            Gig(input_record_id)
        except Exception as e:
            error_table.create(fields={"fld11NQUETyWAJ7ZR": str(e)})

    return "OK!", 200


data = ["test0", "test1"]


# Route for updating the configurables
@app.route("/update/config", methods=["POST"])
@token_required
def get_prylar():
    global folk

    # Make the key of configs go directly to the value
    for configurable in request.json["Config"]:
        request.json["Config"][configurable] = request.json["Config"][
            configurable]["Siffra i decimal"]

    # Format prylar better

    orm.Paket()._update_all(True)

    # pryl_dict = {pryl.id: pryl.__dict__ for pryl in orm.get_all_in_orm(orm.Prylar)}
    # paket_dict = {paket.id: paket.__dict__ for paket in orm.get_all_in_orm(orm.Paket)}

    # Save data to file
    # with open("prylar.json", "w", encoding="utf-8") as f:
    #     json.dump(pryl_dict, f, ensure_ascii=False, indent=2)
    # with open("paket.json", "w", encoding="utf-8") as f:
    #     json.dump(paket_dict, f, ensure_ascii=False, indent=2)

    with open("config.json", "w", encoding="utf-8") as f:
        json.dump(request.json["Config"], f, ensure_ascii=False, indent=2)

    return "OK!", 200


@app.route("/update", methods=["POST"])
@token_required
def update():
    with open("everything.json", "w", encoding="utf-8") as f:
        json.dump(request.json, f, ensure_ascii=False, indent=2)
    return "OK!", 200


def server():
    app.run(host="0.0.0.0", port=5000)  # skipcq BAN-B104


server()
