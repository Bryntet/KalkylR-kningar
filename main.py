import calendar
import copy
import datetime
import json
import math
import os
import re
import time
import urllib.parse

import googlemaps
import holidays


import pandas as pd
import pytz
import requests
from flask import Flask, request
from pyairtable import Table, Base
from auth_middleware import token_required
from operator import itemgetter
from folk import Folk
from calendar_update import delete_event as cal_del
import orm
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

class Prylob:
    def __init__(self, **kwargs):
        # Gets all attributes provided and adds them to self
        # Current args: name, in_pris, pris
        self.in_pris = None
        self.livs_längd = 3
        self.output_record.Pris = None

        for argName, value in kwargs.items():
            self.__dict__.update({argName: value})

        self.amount = 1
        self.mult = 100 + (self.ll_steg * 3)
        self.mult -= self.livs_längd * self.ll_steg
        self.mult /= 100

    def rounding(self, config):
        # Convert to lower price as a percentage of the buy price
        self.output_record.Pris = (
            math.floor((float(self.in_pris) * config["prylKostnadMulti"]) /
                       10 * self.mult) * 10
        )

    def dict_make(self):
        temp_dict = vars(self)

        # TODO make this call for all once to dict and then get dict instead of this bullshit.
        temp_dict.update({'name_packlista': pryl_table.get(self.id)["fields"]['Pryl Namn']})
        temp_dict.update({'name': self.id})

        out_dict = {temp_dict["id"]: temp_dict}
        #out_dict[temp_dict["id"]].pop("name", None)
        return out_dict

    def amount_calc(self, ind, antal_av_pryl):
        self.amount = antal_av_pryl[ind]


class Paketob:
    def __init__(self, prylar, saker, config):



        self.paket_prylar = self.get_value('paket_prylar', saker)
        self.antal_av_pryl = self.get_value('antal_av_pryl', saker)
        self.paket_dict = self.get_value('paket_dict', saker)
        self.paket_i_pryl_paket = self.get_value('paket_i_pryl_paket', saker)
        self.namn3 = saker.get("Paket Namn", "")
        self.svanis = saker.get("Svanis", False)
        self.hyra = saker.get("Hyreskostnad", 0)
        self.output_record.Pris = 0
        self.prylar = {}
        self.id = self.get_value('id', saker)

        self.output_record.Personal = saker.get('Personal', 0)


        if self.paket_i_pryl_paket is not None:
            for paket in self.paket_i_pryl_paket:  # skipcq PYL-E1133
                if paket['id'] in self.paket_dict.keys():
                    for pryl in self.paket_dict[paket["id"]]["prylar"]:
                        if pryl in self.prylar:
                            self.prylar[pryl]["amount"] += 1
                        else:
                            self.prylar[pryl] = copy.deepcopy(
                                self.paket_dict[paket["id"]]["prylar"][pryl]
                            )
                else:
                    paket_from_air = Table(api_key, base_id, "Prylpaket").get(paket['id'])
                    temp_prylar = {}
                    if paket_from_air['fields'].get('paket_prylar') is not None:

                        for pryl_id in paket_from_air['fields']['paket_prylar']:
                            obj = Prylob(
                                in_pris=prylar[pryl_id]["pris"],
                                id=pryl_id,
                                livs_längd=int(prylar[pryl_id]["livs_längd"]),
                                ll_steg=config['livsLängdSteg']
                            )
                            obj.rounding(config)
                            temp_prylar[pryl_id] = obj.dict_make()[pryl_id]

                    list_thingy = paket_from_air['fields'].get('antal_av_pryl', "").split(',')

                    for ind, pryl in enumerate(temp_prylar):


                        if 'antal_av_pryl' in paket_from_air['fields']:
                            if ind >= len(list_thingy):
                                amount = 1
                            else:
                                amount = list_thingy[ind]
                        else:
                            amount = 1
                        if pryl not in self.prylar:
                            self.prylar[pryl] = temp_prylar[pryl]
                            self.prylar[pryl]["amount"] = amount
                        else:
                            self.prylar[pryl] += amount

        if self.antal_av_pryl is not None:
            # Add pryl objects to self list of all prylar in paket

            self.antal_av_pryl = str(self.antal_av_pryl).split(",")
            for ind, pryl in enumerate(self.paket_prylar):
                self.prylar.update({pryl: copy.deepcopy(prylar[pryl])})
                if self.antal_av_pryl is not None and len(self.antal_av_pryl) > ind:
                    self.prylar[pryl]["amount"] = int(self.antal_av_pryl[ind])
                else:
                    self.prylar[pryl]["amount"] = 1
        else:
            if self.paket_prylar is not None:
                for pryl in self.paket_prylar:
                    self.prylar.update({pryl: copy.deepcopy(prylar[pryl])})
                    self.prylar[pryl]["amount"] = 1

        # Set total price of prylar in paket
        for pryl in self.prylar:
            self.output_record.Pris += self.prylar[pryl]["pris"] * int(self.prylar[pryl]["amount"])
        self.output_record.Pris += self.hyra
    def dict_make(self):
        temp_dict = vars(self)
        out_dict = {temp_dict["id"]: temp_dict}
        out_dict[temp_dict["id"]].pop("paket_prylar", None)
        bok = {}
        if out_dict[temp_dict["id"]]["paket_i_pryl_paket"] is not None:

            for dubbelPaket in out_dict[temp_dict["id"]
                                        ]["paket_i_pryl_paket"][0]:
                bok.update({
                    "name": out_dict[temp_dict["id"]]["paket_i_pryl_paket"]
                    [0][dubbelPaket]
                })
            out_dict[temp_dict["id"]]["paket_i_pryl_paket"] = bok

        out_dict[temp_dict["id"]].pop("paket_dict", None)
        out_dict[temp_dict["id"]].pop("Input data", None)
        out_dict[temp_dict["id"]].pop("Output table", None)


        return out_dict

    def get_value(self, key, dict_thing):
        if key in dict_thing:
            return dict_thing[key]
        else:
            return None


class Gig:
    def __init__(self, input_RID):
        self.tid_rapport = []

        with open("config.json", "r", encoding="utf-8") as f:
            config = json.load(f)

        with open("paket.json", "r", encoding="utf-8") as f:
            paketen = json.load(f)

        with open("prylar.json", "r", encoding="utf-8") as f:
            prylar = json.load(f)

        with open("output.json", "r", encoding="utf-8") as f:
            prev_out = json.load(f)

        self.i_data = input_data_table.get(input_RID)['fields']


        self.data = orm.input_data.from_id(input_data_table.get(input_RID)['id'])
        if self.data.uppdateraa:
            self.output_record.id = self.data.uppdateraProjekt[0]
            self.output_record.fetch()
        else:
            self.output_record = orm.Leverans()



        if self.data.ny_slutkund:
            self.slutkund = orm.Slutkund(
                    name = self.data.ny_slutkund
                )
            self.slutkund.save()
        elif self.data.slutkund is not None:
            self.slutkund = self.data.slutkund[0]
            self.slutkund.fetch()
        else:
            self.slutkund = orm.Slutkund()



        if self.data.ny_beställare_bool:
            if self.data.ny_kund:
                self.kund = orm.Kund(
                    name = self.data.ny_kund
                )
                self.kund.save()
            else:
                self.kund = self.data.koppla_till_kund[0]
                self.kund.fetch()
            self.bestallare = orm.Bestallare(name = self.data.ny_beställare, kund = self.kund)
            self.bestallare.save()
            get_prylar()
        else:
            self.bestallare = self.data.beställare[0]
            self.bestallare.fetch()
            self.bestallare.kund
            self.kund = self.bestallare.kund[0]
            self.kund.fetch()


        self.output_record.kund = [self.kund]


        self.extra_name = self.data.extra_name

        self.start_date = self.data.börja_datum


        if self.data.sluta_datum is not None:
            self.end_date = self.data.sluta_datum
        else:
            self.end_date = self.start_date

        self.output_record.sluta_datum = self.end_date
        self.output_record.börja_datum = self.start_date
        self.output_record.name = self.make_name()

        self.person_field_list = [
            'Bildproducent', 'Fotograf', 'Ljudtekniker', 'Ljustekniker',
            'Grafikproducent', 'Animatör', 'Körproducent',
            'Innehållsproducent', 'Scenmästare', 'Tekniskt_ansvarig', 'Klippare'
        ]


        # Make a dict of all the types of tasks with lists of people recIDs inside
        self.person_dict_grouped = {
            x: [rec for rec in self.data.__dict__[x]]
            for x in self.person_field_list if self.data.__dict__.get(x) is not None
        }
        self.person_list = []

        # Make a de-duped list of all the people involved in the gig
        [
            self.person_list.append(item) for sublist in
            [self.person_dict_grouped[key] for key in self.person_dict_grouped]
            for item in sublist if item not in self.person_list
        ]

        if self.data.existerande_adress is not None:
            self.adress = self.data.existerande_adress[0]
        elif self.data.Adress is not None:
            self.adress = orm.Adressbok(name = self.data.Adress)
        else:
            self.adress = orm.Adressbok()

        self.adress_update = False
        self.tid_to_adress_car = None
        #self.tid_to_adress = self.adress.used_time

        self.gmaps = googlemaps.Client(key=os.environ["maps_api"])
        self.url = None
        self.dagar_list: list[tuple[datetime.datetime, datetime.datetime]] = []
        self.extra_gig_tid = None
        self.ob_mult = None
        self.output_record.Personal_kostnad_gammal = None
        self.avkastning_gammal = None
        self.output_record.Personal_pris_gammal = None
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
        self.output_record.Personal_marginal = None
        self.kostnad = None
        self.pryl_kostnad = None
        self.hyr_pris = None
        self.output_record.Personal_kostnad = None
        self.output_record.Personal_pris = None
        self.tim_budget = None
        self.restid: float
        self.rigg_timmar: int
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

        self.output_record.Personal = check_with_default(self.data.extraPersonal, 0.0)
        self.output_record.extraPersonal = check_with_default(self.data.extraPersonal, 0)

        self.paketen = paketen
        self.prylar = prylar
        self.marginal = 0
        self.gig_prylar = {}
        self.pre_gig_prylar = []
        self.projekt_timmar_add = check_with_default(self.data.projekt_timmar, 0)

        self.projekt_timmar = None
        self.frilans_hyrkostnad = 0
        self.frilans_lista = []

        if self.data.Frilans is not None:
            self.frilans = len(self.data.Frilans)
            with open("frilans.json", "r", encoding="utf-8") as f:
                frilans_list = json.load(f)
            for frilans in self.i_data["Frilans"]:
                self.frilans_lista.append(frilans["id"])
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
            if paketen[paket]['svanis']:
                self.svanis = True
                break

        # Take all prylar and put them inside a list
        if self.extra_prylar != []:
            self.check_prylar()
        # Take all prylar from paket and put them inside a list
        if self.prylpaket != []:
            self.check_paket()

        # Add accurate count to all prylar and compile them from list to dict
        self.count_them()
        # Modify pryl_pris based on factors such as svanis
        self.pryl_mod(config)
        # Get the total modPris and in_pris from all the prylar
        self.get_pris()

        #TODO Here too
        self.adress_check()

        self.rakna_timmar(config)

        self.tid(config)

        self.post_text_func()

        self.personal_rakna(config)

        self.marginal_rakna(config)

        box_check()

        self.output()

        #if self.use_inventarie:
        #self.inventarie()

        self.frilans_to_airtable()

        self.url_make()

        box_check()

        if self.update:
            self.updating()
        if self.adress_update:
            adress_table = Table(api_key, base_id, "Adressbok")
            for record in adress_table.all():
                if record["fields"]["Adress"] == self.adress:
                    record_id = record["id"]
                    break
            adress_table.update(
                record_id,
                {
                    "tid_cykel": self.tid_to_adress,
                    "tid_bil": self.tid_to_adress_car,
                    "distans": self.distance_to_adress
                },
            )
        self.make_tidrapport()
        self.output_to_json()
        #google_drive_handler.do_one(self.projekt)

    def g_data(self, key, out=None):
        if key in self.i_data.keys():
            return self.i_data[key]
        else:
            return out

    def make_name(self):
        if self.start_date != self.end_date:
            name = self.start_date.strftime("%-y%m%d") + " ➜ " + self.end_date.strftime("%d%m")
        else:
            name = self.start_date.strftime("%-y%m%d")
        if self.kund.name is not None:
            name += " | " + self.kund.name
        if self.slutkund.name is not None:
            if self.kund is not None:
                name += " ➜ "
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
                out += f"### - {folk[person]['Name']}\n"
            out += "\n"
        return out


    def check_prylar(self):
        try:
            if self.data.antalPrylar is not None:
                try:
                    int(self.i_data["antalPrylar"])
                    self.i_data["antalPrylar"] = [self.i_data["antalPrylar"]]
                except ValueError:
                    if self.i_data["antalPrylar"][0] == "[": # Compat fix for old bug in update
                        self.i_data["antalPrylar"] = self.i_data["antalPrylar"].replace("[", "").replace("]", "").replace("'", "")
                    self.i_data["antalPrylar"] = self.i_data["antalPrylar"
                                                             ].split(",")
            antal = self.i_data["antalPrylar"] is not None
        except KeyError:
            antal = False
        i = 0
        if self.data.extraPrylar is not None:
            for pryl in self.data.extraPrylar:
                if antal:
                    try:
                        for _ in range(int(self.i_data["antalPrylar"][i])):
                            self.pre_gig_prylar.append({pryl: self.prylar[pryl]})
                    except IndexError:
                        self.pre_gig_prylar.append({pryl: self.prylar[pryl]})
                else:
                    # Add pryl from prylar to prylList
                    self.pre_gig_prylar.append({pryl: self.prylar[pryl]})
                i += 1

    def check_paket(self):
        try:
            if self.i_data["antalPaket"]:
                try:
                    int(self.i_data["antalPaket"])
                    self.i_data["antalPaket"] = [self.i_data["antalPaket"]]
                except ValueError:
                    if self.i_data["antalPaket"][0] == "[":
                        self.i_data["antalPaket"] = self.i_data["antalPaket"].replace("[", "").replace("]", "").replace("'", "")
                    self.i_data["antalPaket"] = self.i_data["antalPaket"
                                                            ].split(",")
            antal = self.i_data["antalPaket"] is not None
        except KeyError:
            antal = False
        if self.data.prylPaket is not None:
            for paket in self.data.prylPaket:
                # Check svanis
                try:
                    if self.paketen[paket]["Svanis"] == True:
                        self.svanis = True
                except KeyError:
                    pass
                # Get personal

                self.output_record.Personal += self.paketen[paket].get("personal", 0)
                i = 0

                for pryl in self.paketen[paket]["prylar"]:
                    if antal:
                        try:
                            for _ in range(int(self.i_data["antalPaket"][i])):
                                self.pre_gig_prylar.append({
                                    pryl: self.paketen[paket]["prylar"][pryl]
                                })
                        except IndexError:
                            self.pre_gig_prylar.append({
                                pryl: self.paketen[paket]["prylar"][pryl]
                            })
                    else:
                        # Add pryl from paket to prylList
                        self.pre_gig_prylar.append({
                            pryl: self.paketen[paket]["prylar"][pryl]
                        })
                i += 1

    def count_them(self):
        i = 0
        for pryl in self.pre_gig_prylar:
            for key in pryl:
                if key in list(self.gig_prylar):
                    self.gig_prylar[key]["amount"] += copy.deepcopy(
                        self.pre_gig_prylar[i][key]["amount"]
                    )
                else:
                    self.gig_prylar.update(
                        copy.deepcopy(self.pre_gig_prylar[i])
                    )
            i += 1

    def pryl_mod(self, config):

        for pryl in self.gig_prylar:
            self.in_pris += self.gig_prylar[pryl]["in_pris"]

            # Make new pryl attribute "mod" where price modifications happen
            self.gig_prylar[pryl]["mod"] = copy.deepcopy(
                self.gig_prylar[pryl]["pris"]
            )
            mod_pryl = self.gig_prylar[pryl]["mod"]

            # Mult price by amount of pryl
            mod_pryl *= self.gig_prylar[pryl]["amount"]

            # If svanis, mult by svanis multi
            if self.svanis:
                mod_pryl = int(float(mod_pryl) * config["svanisMulti"])


            self.gig_prylar[pryl]["dagarMod"] = self.dagar(config, mod_pryl)

            self.gig_prylar[pryl]["mod"] = mod_pryl

    def get_pris(self):
        for pryl in self.gig_prylar:
            self.in_pris += self.gig_prylar[pryl]["in_pris"]
            self.output_record.Pryl_pris += self.gig_prylar[pryl]["dagarMod"]
            self.output_record.Pris += self.gig_prylar[pryl]["dagarMod"]
        self.pryl_kostnad = self.output_record.Pryl_pris * 0.4

    def dagar(self, config, pris):

        dagar = self.i_data["dagar"]

        dag_tva_multi = config["dagTvåMulti"]
        dag_tre_multi = config["dagTreMulti"]
        temp_pris = copy.deepcopy(pris)
        if type(dagar) is dict:
            dagar = 1
            self.i_data["dagar"] = 1

        if dagar < 1:
            temp_pris = 0
        elif dagar >= 2:
            temp_pris *= 1 + dag_tva_multi
        if dagar >= 3:
            temp_pris += pris * dag_tre_multi * (dagar-2)
        return temp_pris

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
            self.adress.time_bike = gmaps_bike['rows'][0]['elements'][0]['duration']['value']
            if self.adress.time_bike / 60 > 60:
                self.car = True
                gmaps_car = self.gmaps.distance_matrix(
                    origins="Levande video",
                    destinations=self.adress.name,
                    mode="driving",
                    units="metric",
                )
                self.adress.time_car = gmaps_car["rows"][0]["elements"][0]["duration"]["value"]
            self.adress.distance = self.adress.time_car if self.adress.time_car is not None else self.adress.time_bike
            self.adress.save()

    def rakna_timmar(self, config):
        #Custom riggtimmar
        if self.i_data["specialRigg"]:
            self.rigg_timmar = self.i_data["riggTimmar"] / self.output_record.Personal if self.output_record.Personal > 0 else 0
        else:
            self.rigg_timmar = math.floor(self.output_record.Pryl_pris * config["andelRiggTimmar"] / self.output_record.Personal) if self.output_record.Personal > 0 else 0

        if self.adress.used_time is not None:
            if self.tid_to_adress_car is not None:
                self.restid = self.tid_to_adress_car / 60 / 60
            else:
                self.restid = self.tid_to_adress / 60 / 60
        else:
            self.restid = self.i_data["dagar"] * config["restid"]

        if self.svanis:
            self.restid = 0.0

        if self.restid is None:
            self.restid = 0.0
        self.restid = round(self.restid*12)/12



    def tid(self, config):

        ins = [
            datetime.time.fromisoformat(time_thing if ":" in time_thing else "00:00")
            for combined in (self.data.getin_getout if self.data.getin_getout is not None else "00:00,00:00-00:00,00:00").split(",")
            for time_thing in (combined.split("-") if "-" in combined else [combined, "00:00"])
        ]

        self.mgetins, self.mgetouts = ins[0::2], ins[1::2]

        self.mgets_outs_true = (self.mgetins[0].hour!=0 or self.mgetins[0].minute!=0)

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
                for _ in range(int(self.i_data["dagar"])):
                    self.extra_gig_tid.append(self.data.tid_för_gig)

            while len(self.extra_gig_tid) < self.i_data["dagar"]:
                self.extra_gig_tid.append(self.extra_gig_tid[0])

            self.program_tider: tuple[list[datetime.time], list[datetime.time]] = ([
                    datetime.time.fromisoformat(
                        split_tid.split("-")[0] if ":" in split_tid.split("-")[0] else "00:00"
                    ) for split_tid in self.extra_gig_tid
                ], [
                    datetime.time.fromisoformat(
                        split_tid.split("-")[1] if ":" in split_tid.split("-")[1] else "00:00"
                    ) for split_tid in self.extra_gig_tid
                ])  # new thing, redoing stuff

            for starts, ends in zip(self.program_tider[0], self.program_tider[1]):
                self.gig_timmar += (ends.hour + ends.minute/60) - (starts.hour + starts.minute/60)

            self.gig_timmar /= len(self.program_tider[0])

            if self.mgets_outs_true:
                self.riggtimmar = 0
                for starts, ends in zip(self.mgetins, self.mgetouts):
                    self.riggtimmar += (ends.hour + ends.minute/60) - (starts.hour + starts.minute/60) - self.gig_timmar
                self.riggtimmar /= len(self.mgetins)

            for idx, tid in enumerate(self.extra_gig_tid):
                tup: tuple[str, str] = tuple(tid.split("-"))
                start: tuple[int, int]
                end: tuple[int, int]

                start, end = map(lambda x: tuple(map(int, x.split(":"))) if ":" in x else tuple(map(int, [x, "0"])), tup)

                cest = pytz.timezone("Europe/Stockholm")


                if self.mgets_outs_true:
                    rigg_after = 0
                    rigg_before = 0
                else:
                    if self.rigg_timmar > 1: # Om mer än 1 timme gå till följande logik
                        if self.rigg_timmar > 2: # Rigg efter gig max på 1, resten går till innan
                            rigg_after = 1
                            rigg_before = self.rigg_timmar - 1
                        else: # Om tiden är mer är mer än 1 timme men mindre än 2, splitta jämt mellan
                            rigg_after = self.rigg_timmar/2
                            rigg_before = self.rigg_timmar/2
                    else: # Minimum extra tid innan & efter är en halvtimme
                        rigg_after = 0.5
                        rigg_before = 0.5

                rigg_res_start = (
                    datetime.timedelta(
                        hours=rigg_before + self.restid + self.begin_earlier
                    )
                )
                rigg_res_end = (datetime.timedelta(hours=rigg_after+self.restid))

                self.dagar_changes = (rigg_res_start, rigg_res_end)

                if len(self.mgetins) <= idx+1 and self.mgets_outs_true:
                    self.dagar_list.append((
                        cest.localize(
                            datetime.datetime.combine(
                                self.start_date +
                                datetime.timedelta(days=idx),
                                self.mgetins[idx]
                            )
                            - rigg_res_start
                        ),
                        cest.localize(
                            datetime.datetime.combine(
                                self.start_date +
                                datetime.timedelta(days=idx),
                                self.mgetouts[idx]
                            )
                            + rigg_res_end
                        )
                    ))

                else:
                    self.dagar_list.append((
                            cest.localize(
                                self.start_date
                                + datetime.timedelta(days=idx, hours=start[0], minutes=start[1])
                                - rigg_res_start
                            ),
                            cest.localize(
                                self.start_date
                                + datetime.timedelta(days=idx, hours=end[0], minutes=end[1])
                                + rigg_res_end
                            )
                    ))

                hours_total += (self.dagar_list[-1][1].timestamp() - self.dagar_list[-1][0].timestamp()) / 60 / 60

        while len(self.mgetins) < len(self.dagar_list):
            self.mgetouts.append(None)
            self.mgetins.append(None)
        self.ob_dict = {"0": [], "1": [], "2": [], "3": [], "4": []}

        skärtorsdagen = None
        for date, holiday in holidays.SWE(False, years=self.end_date.year).items():
            if holiday == "Långfredagen":
                skärtorsdagen = date - datetime.timedelta(days=1)
                break
        for begin, stop in self.dagar_list:
            # Loopa igenom varje timme avrundat till närmaste halvtimme
            for idx, hour in enumerate(range(round((stop.timestamp() - begin.timestamp())/60/30))):
                hour /= 2
                # Räkna ut ob och lägg i en dict

                if idx + 1 == round((stop.timestamp() - begin.timestamp())/60/30): # Check if last
                    temp_date = stop
                else:
                    temp_date = begin + datetime.timedelta(hours=hour)

                if temp_date in holidays.SWE(False, years=temp_date.year):
                    if (
                        holidays.SWE(False, years=temp_date.year)[temp_date]
                        in [
                            "Trettondedag jul",
                            "Kristi himmelsfärdsdag",
                            "Alla helgons dag",
                            "Första maj"
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
                elif temp_date.isoweekday() == 6 or temp_date.isoweekday() == 7:
                    self.ob_dict["3"].append(temp_date)
                else:
                    self.ob_dict["0"].append(temp_date)

            self.start_date += datetime.timedelta(days=1)

        self.ob_text = ""

        for key, value in self.ob_dict.items():
            if len(value) > 0:# and key != "0":
                self.ob_text += f"OB {key}: {value[0].isoformat()} - {value[-1].isoformat()} ({round((value[-1] - value[0]).seconds/60/60*2)/2}h)\n"
        avg = hours_total / len(self.dagar_list)

        self.dag_längd = avg

        self.ob_mult = 0
        self.ob_mult += len(self.ob_dict["0"])/2 * config["levandeVideoLön"]
        self.ob_mult += len(self.ob_dict["1"])/2 * (
            config["levandeVideoLön"] + (config["levandeVideoLön"] * 168 / 600)
        )
        self.ob_mult += len(self.ob_dict["2"])/2 * (
            config["levandeVideoLön"] + (config["levandeVideoLön"] * 168 / 400)
        )
        self.ob_mult += len(self.ob_dict["3"])/2 * (
            config["levandeVideoLön"] + (config["levandeVideoLön"] * 168 / 300)
        )
        self.ob_mult += len(self.ob_dict["4"])/2 * (
            config["levandeVideoLön"] + (config["levandeVideoLön"] * 168 / 150)
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
                (self.gig_timmar + self.rigg_timmar) * config["projektTid"] / total_personal if total_personal != 0 else 0
            ) + (self.projekt_timmar_add / total_personal if total_personal != 0 else 0)

        self.tim_dict = {
            'gig': int(self.gig_timmar),
            'rigg': int(self.rigg_timmar),
            'proj': int(self.projekt_timmar),
            'res': int(self.restid),
        }

        total_tid = (self.gig_timmar + self.rigg_timmar + self.projekt_timmar + self.restid*2) * total_personal if total_personal > 0 else 0

        self.folk = Folk(self.lön_kostnad, self.timpris, config['hyrMulti'])
        self.frilans_kostnad, self.total_tim_frilans, self.antal_frilans, self.frilans_personal_dict = self.folk.total_cost(
            self.person_list, self.tim_dict, False, self.person_dict_grouped#[key for person in self.person_list for key, value in self.person_dict_grouped.items() if person == value]
        )




        self.levande_video_kostnad = self.lön_kostnad * (total_tid/total_personal) * (total_personal - self.antal_frilans) if total_personal > self.antal_frilans else 0


        self.output_record.Personal_kostnad = self.frilans_kostnad + self.levande_video_kostnad
        self.output_record.Personal_pris =  self.timpris * total_tid # Frilans is not used for pris


        #TODO FIX THIS
        self.total_tim_budget = total_tid

        #Theoretical cost if only done by lv
        self.teoretisk_lön_kostnad = self.total_tim_budget * self.lön_kostnad
        self.teoretisk_lön_pris = self.total_tim_budget * self.timpris
        self.output_record.Personal = total_personal
        self.output_record.restid = int(self.restid * float(check_with_default(self.output_record.Personal, 0)) * 2.0 * float(len(self.dagar_list)))

    def post_text_func(self):
        try:
            if self.i_data["post_text"]:
                self.post_text_pris = (
                    self.i_data["Textning minuter"] *
                    self.config["textningPostPris"]
                )
                self.post_text_kostnad = (
                    self.i_data["Textning minuter"] *
                    self.config["textningPostKostnad"]
                )
        except KeyError:
            pass

    def marginal_rakna(self, config):
        try:
            if self.i_data["hyrKostnad"] is None:
                self.i_data["hyrKostnad"] = 0
        except KeyError:
            self.i_data["hyrKostnad"] = 0

        self.hyr_pris = self.i_data["hyrKostnad"] * (1 + config["hyrMulti"])

        self.kostnad = (
            self.pryl_kostnad + self.i_data["hyrKostnad"] +
            self.post_text_kostnad + self.output_record.Personal_kostnad
        )

        self.output_record.Pris += self.hyr_pris + self.post_text_pris + self.output_record.Personal_pris

        #Teoretiska ifall enbart gjort av LV
        self.teoretisk_kostnad = self.kostnad - self.frilans_kostnad - self.levande_video_kostnad + self.teoretisk_lön_kostnad

        # Prevent div by 0
        if self.output_record.Pryl_pris != 0:
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
        #self.avkastning_without_pris = (
        #    -1 * self.slit_kostnad - self.output_record.Personal_kostnad -
        #    self.i_data["hyrKostnad"]
        #)
        #self.avkastning_without_pris_gammal = (
        #    -1 * self.slit_kostnad - self.output_record.Personal_kostnad_gammal -
        #    self.i_data["hyrKostnad"]
        #)

        self.hyr_things = self.i_data["hyrKostnad"] * (
            1 - config["hyrMulti"] * config["hyrMarginal"]
        )
        try:
            self.marginal = (
                round(self.avkastning /
                      (self.output_record.Pris - self.hyr_things) * 10000) / 100
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

        self.gig_prylar = dict(
            sorted(
                self.gig_prylar.items(),
                key=lambda item: -1 * item[1]["amount"]
            )
        )
        packlista = "## Prylar:\n\n"
        for pryl in self.gig_prylar:
            packlista += f"### {self.gig_prylar[pryl]['amount']}st {self.gig_prylar[pryl]['name_packlista']}\n\n"
            print(
                f"\t{self.gig_prylar[pryl]['amount']}st {pryl} - {self.gig_prylar[pryl]['mod']} kr ",
                f"- {self.gig_prylar[pryl]['dagarMod']} kr pga {self.i_data['dagar']} dagar",
            )


        paket_id_list = []
        pryl_id_list = []

        if self.prylpaket is not None:
            for paket in self.prylpaket:
                paket_id_list.append(self.paketen[paket]["id"])

        if self.extra_prylar is not None:
            for pryl in self.extra_prylar:
                pryl_id_list.append(self.prylar[pryl]["id"])

        antal_string = ""

        try:
            for antal in self.i_data["antalPrylar"]:
                if antal_string == "":
                    antal_string += antal
                else:
                    antal_string += "," + antal
        except (KeyError, TypeError):
            pass
        antal_paket_string = ""
        try:
            for antal in self.i_data["antalPaket"]:
                if antal_paket_string == "":
                    antal_paket_string += antal
                else:
                    antal_paket_string += "," + antal
        except (KeyError, TypeError):
            pass


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
        self.post_text: bool = self.g_data('post_text', False)
        self.proj_typ = self.g_data('proj_typ', {'name': None})


        print(self.kund.name, self.bestallare.name)
        self.projekt_typ = self.i_data.get("Projekt typ", 'live')
        riggdag = self.projekt_typ == 'Rigg'

        self.output_record.Projekt_kanban = self.output_record.name
        self.output_record.Projekt_timmar = int(float(self.gig_timmar)*self.output_record.Personal*float(len(self.dagar_list)))
        self.output_record.Rigg_timmar = int(self.rigg_timmar*self.output_record.Personal)

        self.output_record.prylPaket = paket_id_list
        self.output_record.extraPrylar = pryl_id_list
        self.output_record.antalPrylar = antal_string
        self.output_record.antalPaket = antal_paket_string

        self.output_record.Projekt = [self.projekt]
        self.output_record.dagar = len(self.dagar_list)
        self.output_record.packlista = packlista
        self.output_record.projektTid = int(self.projekt_timmar*self.output_record.Personal)
        self.output_record.dagLängd = self.dag_längd
        self.output_record.slitKostnad = self.slit_kostnad
        self.output_record.prylFonden = self.pryl_fonden
        self.output_record.hyrthings = self.hyr_things
        self.output_record.avkastWithoutPris = float(self.avkastning)
        self.output_record.avkast2 = float(self.teoretisk_avkastning)
        self.output_record.frilanstimmar = check_with_default(self.tim_budget_frilans,0.0)
        #self.output_record.ny
        self.output_record.leverans_nummer = leverans_nummer
        self.output_record.Typ = self.projekt_typ
        self.output_record.input_id = self.data.id
        self.output_record.post_deadline = check_with_default(self.data.post_deadline, datetime.datetime.min)
        self.output_record.All_personal = self.person_list
        self.output_record.slutkund_temp = [self.slutkund]
        self.output_record.role_format = self.make_format_for_roles()
        self.output_record.extra_namn = self.extra_name
        self.output_record.ob = self.ob_text
        self.output_record.Kommentar_från_formulär = self.comment
        self.output_record.projekt_kalender = []
        output = {
            # "prylFonden": self.pryl_fonden,
            # "hyrthings": self.hyr_things,
            # "avkastWithoutPris": self.avkastning,
            # "avkast2": self.teoretisk_avkastning,
            # "frilanstimmar": self.tim_budget_frilans,
            # "total_tid_ex_frilans": self.tim_budget_personal,
            # "frilans": self.frilans_lista,
            "ny proj ledare från uppdatera": [
                x for x in self.i_data.get("projektledare")
            ],  # Så jag kan göra lite logik
            #"producent": [x for x in self.i_data.get("producent")],
            # "leverans_nummer": leverans_nummer,
            # "Kund": self.kund,
            # "Svanis": self.svanis,
            # "Typ": self.projekt_typ,
            # "Adress": self.adress,
            # "Beställare": self.bestallare,
            # "input_id": self.i_data.get("input_id"),
            # "made_by": [self.i_data.get("input_id")],
            # "post_deadline": self.i_data.get("post_deadline"),
            # "All personal": self.person_list,
            # 'slutkund_temp': self.slutkund,
            # 'role_format': self.make_format_for_roles(),
            # 'extra namn': self.extra_name,
            # "OB": self.ob_text,
            # "Kommentar från formulär": self.comment,
            # "Gig namn": self.name,
            # "Pris": self.output_record.Pris if not riggdag else 0,
            # "Personal": self.output_record.Personal,
            # "extraPersonal": self.i_data.get('extraPersonal', 0),
            # "Projekt timmar": self.gig_timmar*self.output_record.Personal*len(self.dagar_list),
            # "Rigg timmar": self.rigg_timmar*self.output_record.Personal,
            # "Totalt timmar": self.tim_budget,
            # "Pryl pris": self.output_record.Pryl_pris,
            # "prylPaket": paket_id_list,
            # "extraPrylar": pryl_id_list,
            # "antalPrylar": antal_string,
            # "antalPaket": antal_paket_string,
            # "Projekt kanban": self.name,
            #"Projekt": self.projekt,
            #"börjaDatum": self.output_record.börjaDatum,
            #"slutaDatum": self.output_record.slutaDatum,
            #"dagar": self.i_data["dagar"],
            #"packlista": packlista,
            #"restid": self.restid*self.output_record.Personal*2,
            #"projektTid": self.projekt_timmar*self.output_record.Personal,
            #"dagLängd": str(self.dag_längd),
            #"slitKostnad": self.slit_kostnad,
            #"typ person lista": [x for x in self.person_list]
            #"Mer folk": list(map(itemgetter("id"), self.specifik_personal))
        }
        if riggdag:
            self.output_record.eget_pris = 0

        self.output_record.__dict__.update({x: '' for x in self.person_field_list})
        self.output_record.__dict__.update(self.person_dict_grouped)

        for key in self.person_dict_grouped.keys():
            if key not in ["Bildproducent", "Ljudtekniker"]:
                for person in self.person_dict_grouped[key]:
                    self.output_record.Resten.append(person)
        # TODO
        #if self.projekt_typ == "Rigg":
        #    (output.pop(x) for x in ["Pris", "prylPaket", "extraPrylar"])


        for key in list(output.keys()):
            if output[key] is None:
                del output[key]

        print(time.time() - self.start_time)

        # if self.update:
        #     body = {
        #         "records": [{
        #             "id": self.i_data["uppdateraProjekt"][0],
        #             "fields": output
        #         }],
        #         "typecast": True,
        #     }
        #     output_from_airtable = requests.patch(
        #         url="https://api.airtable.com/v0/appG1QEArAVGABdjm/Leveranser",
        #         json=body,
        #         headers={
        #             "Authorization": "Bearer " + api_key,
        #             "Content-Type": "application/json",
        #         },
        #     )
        #     output_from_airtable = output_from_airtable.json()["records"][0]
        #     self.air_out = output_from_airtable

        # else:
        #     output_from_airtable = self.output_table.create(
        #         output, typecast=True
        #     )
        #     self.projekt = output_from_airtable["fields"]["Projekt"]

        if not self.output_record.exists():
            assert self.output_record.save()
        else:
            self.output_record.save()

        print(time.time() - self.start_time)
        self.airtable_record = self.output_record.id
        # print(output)
        projektkalender_records = []

        if self.i_data.get("Frilans") is not None:
            frilans_personer = []
            for record in self.i_data["Frilans"]:
                frilans_personer.append(record["id"])
        else:
            frilans_personer = None
        i = 0
        calendar_records: list[orm.Projektkalender] = []
        # Add the dates to the projektkalender table
        if self.update:
            for item in output_from_airtable["fields"]["Projekt kalender"]:
                # Get all record ids of the already existing linked records in the projektkalender table
                calendar_records.append(orm.Projektkalender(id=item))

        for record in calendar_records:
            record.fetch()
        calendar_records = sorted(calendar_records, key=lambda x: x.getin_hidden, reverse=True)


        self.output_record.save()

        if self.dagar_list is not None:
            for idx, (getin, getout) in enumerate(self.dagar_list):
                if idx < len(calendar_records):
                    record = calendar_records[idx]
                else:
                    calendar_records.append(orm.Projektkalender())
                    record = calendar_records[-1]
                if record is not None:
                    record.getin_hidden = (getin + self.dagar_changes[0]).astimezone(pytz.utc).replace(tzinfo=None)
                    record.getout_hidden = (getout - self.dagar_changes[1]).astimezone(pytz.utc).replace(tzinfo=None)
                    record.program_stop_hidden = float(self.program_tider[1][idx].hour*60*60 + self.program_tider[1][idx].minute*60 if self.program_tider[1][idx] is not None else None)
                    record.program_start_hidden = float(self.program_tider[0][idx].hour*60*60 + self.program_tider[0][idx].minute*60 if self.program_tider[0][idx] is not None else None)
                    record.actual_getin = (
                        getin + datetime.timedelta(hours=self.restid)
                    ).hour * 60 * 60 + (
                        getin + (datetime.timedelta(hours=(self.restid)))
                    ).minute * 60
                    record.actual_getout = (
                        getout - datetime.timedelta(hours=self.restid)
                    ).hour * 60 * 60 + (
                        getout - datetime.timedelta(hours=self.restid)
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
                record.save()
            
        if self.update:
            if len(projektkalender_records) != len(record_ids):
                self.kalender_table.batch_delete(record_ids)
                for record_id in record_ids:
                    cal_del(record_id)
                self.kalender_table.batch_create(projektkalender_records)
            else:
                self.kalender_table.batch_update(projektkalender_records)
        else:
            self.kalender_table.batch_create(projektkalender_records)
        print(time.time() - self.start_time)
        self.leverans_nummer = leverans_nummer
        self.output_variable = output
        try:
            self.tid_rapport = old_output["tidrapport"]
        except KeyError:
            pass
        self.old_output[self.output_record.id] = self.output_variable

    def url_make(self):

        self.projektledare = self.i_data.get("projektledare", [None])[0]
        self.producent = self.i_data.get("producent", [None])[0]
        self.antal_paket = self.i_data.get("antalPaket", [])
        self.antal_prylar = self.i_data.get("antalPrylar", [])
        self.extra_personal = self.i_data.get("extraPersonal")

        params = {
            "prefill_projektledare": self.projektledare,
            "prefill_producent": self.producent,
            "prefill_prylPaket": ",".join([x.id for x in self.output_record.prylPaket if x is not None]),
            "prefill_extraPrylar": ",".join([x.id for x in self.output_record.extraPrylar if x is not None]),
            "prefill_antalPaket": ",".join(self.antal_paket),
            "prefill_antalPrylar": ",".join(self.antal_prylar),
            "prefill_extraPersonal": self.extra_personal,
            "prefill_hyrKostnad": self.data.hyrKostnad,
            "prefill_tid för gig": self.data.tid_för_gig,
            "prefill_post_text": self.post_text,
            "prefill_Textning minuter": self.data.Textning_minuter,
            "prefill_Kund": self.output_record.kund[0].id,
            "prefill_Frilans": ",".join([x.id for x in self.data.Frilans if x is not None]) if self.data.Frilans is not None else None,
            "prefill_existerande_adress": ",".join(self.adress.id) if (type(self.adress) is not str and self.adress is not None) else self.adress,
            "prefill_gigNamn": self.output_record.name,
            "prefill_Beställare": ",".join(self.bestallare)
            if type(self.bestallare) is list else None,
            "prefill_Slutkund": self.slutkund.id if self.slutkund is not None else None,
            "prefill_Projekt typ": self.projekt_typ,
            "prefill_Anteckning": self.comment,
            "prefill_projekt_timmar": self.projekt_timmar_add,
            "prefill_extra_name": self.extra_name,
            "prefill_getin-getout": self.i_data.get("getin-getout")
        }
        if len(self.person_field_list) > 0:
            params.update({"prefill_boka personal": True})
        for work_area in self.person_field_list:
            if work_area in self.person_dict_grouped.keys():

                params.update({f"prefill_{work_area}": ",".join(self.person_dict_grouped[work_area])})

        update_params = copy.deepcopy(params)
        update_params.update({
            "prefill_uppdateraa": True,
            "prefill_uppdateraProjekt": self.output_record.id,
            "prefill_Börja datum": self.output_record.börja_datum,
            "prefill_preSluta datum": self.i_data.get("preSluta datum"),
        })
        hidden_update = ["uppdateraa", "uppdateraProjekt"]
        for field in hidden_update:
            update_params.update({f"hidden_{field}": True})
        copy_params = copy.deepcopy(params)
        copy_params.update({
            "prefill_nytt_projekt": False,
            "prefill_gigNamn": self.output_record.name,
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

            inventarie_list.append(orm.Inventarie(
                based_on=[pryl_id],
                amount=pryl['amount'],
                leverans=[self.output_record]
            ))
        existing_list = []
        update_list = []
        for record in inventarie.all():
            if record.get('fields',{}).get('Leverans') == self.output_record.id:
                existing_list.append(record['id'])
                if record['fields']['Based on'] not in self.gig_prylar.keys():
                    del existing_list[-1]
                    inventarie.delete(record['id'])
                else:
                    update_list.append(record['id'])
        update = [dict_thing for dict_thing in inventarie_list if dict_thing['Based on'] in update_list]
        if len(update) > 0:
            inventarie.batch_update(update)
        create = [x for x in inventarie_list if x['Based on'] not in existing_list]
        if len(create) > 0:
            inventarie.batch_create(create)



    def updating(self):
        input_data_table = Table(api_key, base_id, "Input data")

        del_list = []
        for key, value in self.i_data.items():
            if value is None and key not in ["extraPrylar", "prylPaket"]:
                del_list.append(key)
        for key in del_list:
            del self.i_data[key]

        del_list = [
            "dagar",
            "specialRigg",
            "riggTimmar",
            "Uppdatera",
            "Created",
            "Sluta datum",
            "old_input_id",
            "extra_prylar_id",
            "input_id",
            "pryl_paket_id",
            "projektledare",
            "producent",
        ]
        for key in del_list:
            try:
                del self.i_data[key]
            except KeyError:
                pass

    def make_tidrapport(self):
        tid_table = Table(api_key, base_id, "Tidrapport")
        all_people = []

        for person in self.person_list:
            person = self.folk.get_person(person)
            if person.levande_video:
                all_people.append(person.name)
        for person in all_people:
            if person is None:
                del all_people[all_people.index(person)]
        records = []
        for dag in self.dagar_list:
            for person in all_people:
                records.append({
                    "Gig": [self.airtable_record],
                    "Start tid": dag[0].hour * 60 * 60 + dag[0].minute * 60,
                    "Tid": (dag[1].hour - dag[0].hour) * 60 * 60 +
                    (dag[1].minute - dag[0].minute) * 60,
                    "unused": True,
                    "Robot": True,
                    "Datum": dag[0].isoformat(),
                    "Person": person
                })

        if self.update:
            update_records = []
            delete_list = []
            create_list = []

            for record in records:
                if record["Person"] in self.tid_rapport:
                    for entry in self.tid_rapport:
                        if record["Person"] == entry["name"]:
                            update_records.append({
                                "id": entry["id"],
                                "fields": record
                            })
                else:
                    create_list.append(record)

            for entry in self.tid_rapport:
                if entry["name"] not in all_people:
                    delete_list.append(entry["id"])

            out_list = []
            if update_records != []:
                outupdate = tid_table.batch_update(
                    update_records, typecast=True
                )
                for record in outupdate:
                    out_list.append(record)
            if delete_list != []:
                tid_table.batch_delete(delete_list, typecast=True)
            if create_list != []:
                outcreat = tid_table.batch_create(create_list, typecast=True)
                for record in outcreat:
                    out_list.append(record)

            tid_out = []
            for record in out_list:
                tid_out.append({
                    'id': record["id"],
                    "name": record["fields"]["Person"]
                })
            self.old_output[self.output_record.id][
                "tidrapport"] = tid_out

        else:
            tid_out = []
            out = tid_table.batch_create(records, typecast=True)
            for record in out:
                tid_out.append({
                    'id': record["id"],
                    "name": record["fields"]["Person"]
                })
            self.old_output[self.output_record.id][
                "tidrapport"] = tid_out

    def frilans_to_airtable(self):
        frilans_calcs = Table(api_key, base_id, "Frilansuträkningar")
        for record in frilans_calcs.all():
            if record["fields"].get("Leveransen") == [self.airtable_record]:
                if record['fields'].get('Riktig kostnad') is not None:
                    continue
                elif record['fields'].get('frilans')[0] in self.frilans_personal_dict.keys():
                    frilans_calcs.update(record['id'], fields={'Gissad kostnad': self.frilans_personal_dict[record['fields'].get('frilans')[0]]})
                    self.frilans_personal_dict.pop(record['fields'].get('frilans')[0], None)
                else:
                    frilans_calcs.delete(record['id'])
        for frilans_id, cost in self.frilans_personal_dict.items():
            frilans_calcs.create({'frilans': [frilans_id], 'Gissad kostnad': cost, 'Leveransen': [self.airtable_record]})



    def output_to_json(self):
        with open("output.json", "w", encoding="utf-8") as f:
            json.dump(self.old_output, f, ensure_ascii=False, indent=2)
        with open("log.json", "w", encoding="utf-8") as f:
            self.log.append({
                f"{self.output_record.name} #{self.leverans_nummer}": self.output_variable
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
    record_name = request.json["content"]
    # Load all the important data
    with open("output.json", "r", encoding="utf-8") as f:
        output = json.load(f)

    with open("output_backup.json", "w", encoding="utf-8") as f:
        json.dump(output[record_name], f, ensure_ascii=False, indent=2)

    output.pop(record_name, None)

    with open("output.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

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
    Gig(input_record_id)

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

    config = request.json["Config"]

    # Format prylar better
    prylarna = request.json["Prylar"]
    pryl_dict = {}
    for prylNamn in prylarna:
        pryl = Prylob(
            in_pris=prylarna[prylNamn].get("pris", 0),
            id=prylNamn,
            livs_längd=int(prylarna[prylNamn]["livsLängd"]["name"]),
            ll_steg=config['livsLängdSteg'],
        )
        pryl.rounding(config)
        pryl_dict.update(pryl.dict_make())
    for pryl_namn, pryl in pryl_dict.items():
        pryl_table.update(pryl_namn, {"Uträknat Pris": pryl["pris"]})
    paketen = request.json["Prylpaket"]
    paket_dict = {}
    last_list = []
    for paket in paketen:
        lista = []
        paketen[paket]["id"] = paket
        if 'paket_i_pryl_paket' in paketen[paket].keys():
            last_list.append(paket)
            continue
        try:
            for pryl in paketen[paket]["paket_prylar"]:
                lista.append(pryl["id"])

            paketen[paket]["paket_prylar"] = lista
        except KeyError:
            pass
        paketen[paket]["paket_dict"] = paket_dict
        paket = Paketob(pryl_dict, paketen[paket], config)
        paket_dict.update(paket.dict_make())

    for paket in last_list:
        paketen[paket]["id"] = paket
        lista = []
        try:
            for pryl in paketen[paket]["paket_prylar"]:
                lista.append(pryl["id"])

            paketen[paket]["paket_prylar"] = lista
        except KeyError:
            pass

        paketen[paket]["paket_dict"] = paket_dict
        paket = Paketob(pryl_dict, paketen[paket], config)
        paket_dict.update(paket.dict_make())

    prylar_table = Table(api_key, base_id, "Prylar")
    paket_table = Table(api_key, base_id, "Prylpaket")


    for record in prylar_table.all():
        pryl_dict[record["id"]].update({"id": record["id"]})
    for record in paket_table.all():
        if record['id'] in paket_dict.keys():
            paket_table.update(record['id'], {'Uträknat pris': paket_dict[record["id"]]['pris']})
            paket_dict[record["id"]].update({"id": record["id"]})

        else:
            paket_dict[record["id"]] = {"id": record["id"]}

    # Save data to file
    with open("prylar.json", "w", encoding="utf-8") as f:
        json.dump(pryl_dict, f, ensure_ascii=False, indent=2)

    with open("config.json", "w", encoding="utf-8") as f:
        json.dump(request.json["Config"], f, ensure_ascii=False, indent=2)
    with open("paket.json", "w", encoding="utf-8") as f:
        json.dump(paket_dict, f, ensure_ascii=False, indent=2)
    with open("frilans.json", "w", encoding="utf-8") as f:
        json.dump(request.json["Frilans"], f, ensure_ascii=False, indent=2)
    with open('folk.json', 'w', encoding='utf-8') as f:
        json.dump(request.json["Folk"], f, ensure_ascii=False, indent=2)
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
