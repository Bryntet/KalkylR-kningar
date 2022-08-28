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

beforeTime = time.time()
output_tables = []
SECRET_KEY = os.environ.get("my_secret")
app = Flask(__name__)

app.config["SECRET_KEY"] = SECRET_KEY


def extractor(data, key="id"):
    return [x[key] for x in data]


class Prylob:
    def __init__(self, **kwargs):
        # Gets all attributes provided and adds them to self
        # Current args: name, in_pris, pris
        self.in_pris = None
        self.livs_längd = 3
        self.pris = None
        for argName, value in kwargs.items():
            self.__dict__.update({argName: value})

        self.amount = 1
        self.mult = 145
        self.mult -= self.livs_längd * 15
        self.mult /= 100

    def rounding(self, config):
        # Convert to lower price as a percentage of the buy price
        self.pris = (
            math.floor(
                (float(self.in_pris) * config["prylKostnadMulti"]) / 10 * self.mult
            )
            * 10
        )

    def dict_make(self):
        temp_dict = vars(self)
        out_dict = {temp_dict["name"]: temp_dict}
        out_dict[temp_dict["name"]].pop("name", None)
        return out_dict

    def amount_calc(self, ind, antal_av_pryl):
        self.amount = antal_av_pryl[ind]


class Paketob:
    def __init__(self, prylar, args):
        # Gets all kwargs provided and adds them to self
        # Current kwargs:
        self.paket_prylar = []
        self.antal_av_pryl = None
        self.paket_dict = {}
        self.paket_i_pryl_paket = None
        for argName, value in args.items():
            self.__dict__.update({argName: value})

        self.pris = 0
        self.prylar = {}

        if self.paket_i_pryl_paket is not None:
            for paket in self.paket_i_pryl_paket:  # skipcq PYL-E1133
                for pryl in self.paket_dict[paket["name"]]["prylar"]:
                    if pryl in self.prylar:
                        self.prylar[pryl]["amount"] += 1
                    else:
                        self.prylar[pryl] = copy.deepcopy(
                            self.paket_dict[paket["name"]]["prylar"][pryl]
                        )
        else:
            if self.antal_av_pryl is not None:
                # Add pryl objects to self list of all prylar in paket

                self.antal_av_pryl = str(self.antal_av_pryl).split(",")
                for pryl in self.paket_prylar:
                    ind = self.paket_prylar.index(pryl)

                    self.prylar.update({pryl: copy.deepcopy(prylar[pryl])})
                    self.prylar[pryl]["amount"] = int(self.antal_av_pryl[ind])

            else:
                for pryl in self.paket_prylar:
                    ind = self.paket_prylar.index(pryl)

                    self.prylar.update({pryl: copy.deepcopy(prylar[pryl])})
                    self.prylar[pryl]["amount"] = 1

        # Set total price of prylar in paket
        for pryl in self.prylar:
            self.pris += self.prylar[pryl]["pris"] * self.prylar[pryl]["amount"]

    def dict_make(self):
        temp_dict = vars(self)
        out_dict = {temp_dict["name"]: temp_dict}
        out_dict[temp_dict["name"]].pop("paket_prylar", None)
        bok = {}
        if out_dict[temp_dict["name"]]["paket_i_pryl_paket"] is not None:
            for dubbelPaket in out_dict[temp_dict["name"]]["paket_i_pryl_paket"][0]:
                bok.update(
                    {
                        "name": out_dict[temp_dict["name"]]["paket_i_pryl_paket"][0][
                            dubbelPaket
                        ]
                    }
                )
            out_dict[temp_dict["name"]]["paket_i_pryl_paket"] = bok

        out_dict[temp_dict["name"]].pop("paket_dict", None)
        out_dict[temp_dict["name"]].pop("Input data", None)
        out_dict[temp_dict["name"]].pop("Output table", None)
        out_dict[temp_dict["name"]].pop("name", None)

        return out_dict


class Gig:
    def __init__(self, i_data, config, prylar, paketen, name):
        self.tid_rapport = []
        self.name = name
        self.i_data = i_data[self.name]
        self.adress_update = False
        self.tid_to_adress_car = None
        self.tid_to_adress = None
        self.gmaps = googlemaps.Client(key=os.environ["maps_api"])
        self.url = None
        self.dagar_list = None
        self.extra_gig_tid = None
        self.ob_mult = None
        self.personal_kostnad_gammal = None
        self.avkastning_gammal = None
        self.personal_pris_gammal = None
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
        self.personal_marginal = None
        self.kostnad = None
        self.pryl_kostnad = None
        self.hyr_pris = None
        self.personal_kostnad = None
        self.personal_pris = None
        self.tim_budget = None
        self.restid = None
        self.rigg_timmar = None
        self.gig_timmar = None
        self.tim_peng = None

        if self.i_data["Mer_personal"]:
            self.specifik_personal = self.i_data["Mer_personal"]
            self.specifik_personal = {"Empty": False, "actual": self.specifik_personal}
        else:
            self.specifik_personal = {
                "Empty": True,
                "actual": [{"id": None, "name": None}],
            }

        try:
            if self.i_data["extraPersonal"] is not None:
                self.personal = self.i_data["extraPersonal"]
            else:
                self.personal = 0
        except KeyError:
            self.personal = 0

        self.paketen = paketen
        self.prylar = prylar
        self.marginal = 0
        self.gig_prylar = {}
        self.pre_gig_prylar = []

        if self.i_data["projekt_timmar"] is not None:
            self.projekt_timmar = self.i_data["projekt_timmar"]
        else:
            self.projekt_timmar = None
        self.frilans_hyrkostnad = 0
        self.frilans_lista = []
        if self.i_data["Frilans"] is not None:
            self.frilans = len(self.i_data["Frilans"])
            with open("frilans.json", "r", encoding="utf-8") as f:
                frilans_list = json.load(f)
            for frilans in self.i_data["Frilans"]:
                self.frilans_lista.append(frilans["id"])
                self.frilans_hyrkostnad += (
                    self.i_data["dagar"] * frilans_list[frilans["name"]]["hyrkostnad"]
                )
        else:
            self.frilans = 0
        self.post_text_kostnad = 0
        self.post_text_pris = 0
        self.pryl_pris = 0
        self.pris = 0
        self.in_pris = 0

        self.config = config
        self.start_time = time.time()

        if self.i_data["uppdateraProjekt"]:
            self.update = True
        else:
            self.update = False

        if self.update:
            self.projektledare = self.i_data["Projektledare (from Projekt)"]
            self.producent = self.i_data["Producent (from Projekt)"]
        else:
            self.producent = self.i_data["producent"]
            self.projektledare = self.i_data["projektledare"]
        try:
            if i_data["svanis"]:
                self.svanis = True
        except KeyError:
            self.svanis = False

        # Take all prylar and put them inside a list
        if self.i_data["extraPrylar"] is not None:
            self.check_prylar(prylar)
        # Take all prylar from paket and put them inside a list
        if self.i_data["prylPaket"] is not None:
            self.check_paket()

        # Add accurate count to all prylar and compile them from list to dict
        self.count_them()
        # Modify pryl_pris based on factors such as svanis
        self.pryl_mod(config)
        # Get the total modPris and in_pris from all the prylar
        self.get_pris()

        self.adress_check()

        self.tid(config)

        self.post_text()

        self.personal_rakna(config)

        self.marginal_rakna(config)

        self.output()

        self.url_make()

        if self.update:
            self.updating()
        if self.adress_update:
            adress_table = Table(api_key, base_id, "Adressbok")
            for record in adress_table.all():
                if record["fields"]["Adress"] == self.i_data["existerande_adress"]:
                    record_id = record["id"]
                    break
            adress_table.update(
                record_id,
                {"tid_cykel": self.tid_to_adress, "tid_bil": self.tid_to_adress_car},
            )
        self.make_tidrapport()
        self.output_to_json()

    def check_prylar(self, prylar):
        try:
            if self.i_data["antalPrylar"]:
                try:
                    int(self.i_data["antalPrylar"])
                    self.i_data["antalPrylar"] = [self.i_data["antalPrylar"]]
                except ValueError:
                    self.i_data["antalPrylar"] = self.i_data["antalPrylar"].split(",")
            antal = self.i_data["antalPrylar"] is not None
        except KeyError:
            antal = False
        i = 0
        for pryl in self.i_data["extraPrylar"]:
            if antal:

                try:
                    for _ in range(int(self.i_data["antalPrylar"][i])):
                        self.pre_gig_prylar.append({pryl: prylar[pryl]})
                except IndexError:
                    self.pre_gig_prylar.append({pryl: prylar[pryl]})
            else:
                # Add pryl from prylar to prylList
                self.pre_gig_prylar.append({pryl: prylar[pryl]})
            i += 1

    def check_paket(self):
        try:
            if self.i_data["antalPaket"]:
                try:
                    int(self.i_data["antalPaket"])
                    self.i_data["antalPaket"] = [self.i_data["antalPaket"]]
                except ValueError:
                    self.i_data["antalPaket"] = self.i_data["antalPaket"].split(",")
            antal = self.i_data["antalPaket"] is not None
        except KeyError:
            antal = False

        for paket in self.i_data["prylPaket"]:
            # Check svanis
            try:
                if self.paketen[paket]["svanis"]:
                    self.svanis = True
            except KeyError:
                pass
            # Get personal
            try:
                if self.paketen[paket]["Personal"]:
                    self.personal += self.paketen[paket]["Personal"]
            except (KeyError, TypeError):
                pass
            i = 0

            for pryl in self.paketen[paket]["prylar"]:
                if antal:
                    try:
                        for _ in range(int(self.i_data["antalPaket"][i])):
                            self.pre_gig_prylar.append(
                                {pryl: self.paketen[paket]["prylar"][pryl]}
                            )
                    except IndexError:
                        self.pre_gig_prylar.append(
                            {pryl: self.paketen[paket]["prylar"][pryl]}
                        )
                else:
                    # Add pryl from paket to prylList
                    self.pre_gig_prylar.append(
                        {pryl: self.paketen[paket]["prylar"][pryl]}
                    )
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
                    self.gig_prylar.update(copy.deepcopy(self.pre_gig_prylar[i]))
            i += 1

    def pryl_mod(self, config):

        for pryl in self.gig_prylar:
            self.in_pris += self.gig_prylar[pryl]["in_pris"]

            # Make new pryl attribute "mod" where price modifications happen
            self.gig_prylar[pryl]["mod"] = copy.deepcopy(self.gig_prylar[pryl]["pris"])
            mod_pryl = self.gig_prylar[pryl]["mod"]

            # Mult price by amount of pryl
            mod_pryl *= self.gig_prylar[pryl]["amount"]

            # If svanis, mult by svanis multi
            if self.svanis:
                mod_pryl *= config["svanisMulti"]

            self.gig_prylar[pryl]["dagarMod"] = self.dagar(config, mod_pryl)

            self.gig_prylar[pryl]["mod"] = mod_pryl

    def get_pris(self):
        for pryl in self.gig_prylar:
            self.in_pris += self.gig_prylar[pryl]["in_pris"]
            self.pryl_pris += self.gig_prylar[pryl]["dagarMod"]
            self.pris += self.gig_prylar[pryl]["dagarMod"]
        self.pryl_kostnad = self.pryl_pris * 0.4

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
            temp_pris += pris * dag_tre_multi * (dagar - 2)
        return temp_pris

    def adress_check(self):
        if (self.i_data["existerande_adress"] is not None) or (
            self.i_data["Adress"] is not None
        ):
            if self.i_data["tid_to_adress"] is not None:
                self.tid_to_adress = self.i_data["tid_to_adress"][0]
            else:
                print("using maps api")
                if self.i_data["existerande_adress"] is not None:
                    adress = self.i_data["existerande_adress"][0]["name"]
                else:
                    adress = self.i_data["Adress"]
                self.adress_update = True
                self.car = False
                self.tid_to_adress = self.gmaps.distance_matrix(
                    origins="Levande video",
                    destinations=adress,
                    mode="bicycling",
                    units="metric",
                )
                if self.tid_to_adress / 60 > 60:
                    self.car = True
                    self.tid_to_adress_car = self.gmaps.distance_matrix(
                        origins="Levande video",
                        destinations=adress,
                        mode="driving",
                        units="metric",
                    )["rows"][0]["elements"][0]["duration"]["value"]
                print(self.tid_to_adress, "here")

    def tid(self, config):

        self.bad_day_dict = dict(zip(calendar.day_name, range(7)))
        i = 1
        for day in self.bad_day_dict:
            self.day_dict[i] = day
            i += 1

        start_date = datetime.datetime.fromisoformat(
            self.i_data["Börja datum"].split(".")[0]
        )
        end_date = datetime.datetime.fromisoformat(
            self.i_data["Sluta datum"].split(".")[0]
        )

        hours_list = []
        self.dagar_list = []

        if self.i_data["tid för gig"] is not None:
            try:
                self.extra_gig_tid = self.i_data["tid för gig"].split(",")
            except AttributeError:
                self.extra_gig_tid = []
                for _ in range(int(self.i_data["dagar"])):
                    self.extra_gig_tid.append(self.i_data["tid för gig"])
            while len(self.extra_gig_tid) < self.i_data["dagar"]:
                self.extra_gig_tid.append(self.extra_gig_tid[0])
            i = 1
            for tid in self.extra_gig_tid:
                self.dagar_list.append([])
                j = 0
                next_change = False
                for temp in tid.split("-"):
                    if ":" in temp:
                        temp = temp.split(":")
                    else:
                        temp = [temp, 0]
                    date = start_date.replace(
                        day=int(start_date.day) + i,
                        hour=int(temp[0]),
                        minute=int(temp[1]),
                    )

                    if j % 2 == 0 and j != 0 or next_change:
                        if (
                            date + datetime.timedelta(hours=1)
                            <= self.dagar_list[-1][-1]
                            or next_change
                        ):
                            if next_change:
                                self.dagar_list[-1].append(date)
                            else:
                                del self.dagar_list[-1][-1]
                                next_change = True
                        else:
                            if not next_change:
                                self.dagar_list.append([])
                    if not next_change:
                        self.dagar_list[-1].append(date)
                        if (j + 1) % 2 == 0:
                            hours_list.append(
                                math.ceil(
                                    (
                                        self.dagar_list[-1][1] - self.dagar_list[-1][0]
                                    ).seconds
                                    / 60
                                    / 60
                                )
                            )
                    else:
                        next_change = False
                    j += 1
                i += 1
            print(hours_list)
        else:
            if self.i_data["dagar"] != 1:
                for i in range(self.i_data["dagar"] - 1):
                    hours_list.append(hours_list[0])

        new_timezone = pytz.timezone("UTC")
        old_timezone = pytz.timezone("Europe/Stockholm")
        temp_dagar_list = []
        print(self.dagar_list)

        for getin, getout in self.dagar_list:
            localized_timestamp = old_timezone.localize(getin)
            getin = localized_timestamp.astimezone(new_timezone)
            localized_timestamp = old_timezone.localize(getout)
            getout = localized_timestamp.astimezone(new_timezone)
            temp_dagar_list.append([getin, getout])

        self.dagar_list = temp_dagar_list
        self.ob_dict = {"0": [], "1": [], "2": [], "3": [], "4": []}
        skärtorsdagen = None
        for date, holiday in holidays.SWE(False, years=end_date.year).items():
            if holiday == "Långfredagen":
                skärtorsdagen = date - datetime.timedelta(days=1)
                break
        for hour in hours_list:
            # Räkna ut ob och lägg i en dict
            for i in range(hour):
                pre_tz_temp_date = start_date + datetime.timedelta(hours=i)
                old_timezone = pytz.timezone("UTC")
                new_timezone = pytz.timezone("Europe/Stockholm")
                localized_timestamp = old_timezone.localize(pre_tz_temp_date)
                temp_date = localized_timestamp.astimezone(new_timezone)
                if temp_date in holidays.SWE(False, years=temp_date.year):
                    if (
                        holidays.SWE(False, years=temp_date.year)[temp_date]
                        in [
                            "Trettondedag jul",
                            "Kristi himmelsfärdsdag",
                            "Alla helgons dag",
                        ]
                        and temp_date.hour >= 7
                    ):
                        self.ob_dict["3"].append(temp_date.timestamp())
                    elif (
                        holidays.SWE(False, years=temp_date.year)[temp_date]
                        in ["Nyårsafton"]
                        and temp_date.hour >= 18
                        or holidays.SWE(False, years=temp_date.year)[temp_date]
                        in [
                            "Pingstdagen",
                            "Sveriges nationaldag",
                            "Midsommarafton",
                            "Julafton",
                        ]
                        and temp_date.hour >= 7
                    ):
                        self.ob_dict["4"].append(temp_date.timestamp())
                    else:
                        self.ob_dict["0"].append(temp_date.timestamp())
                elif (
                    str(temp_date).split(" ")[0] == str(skärtorsdagen)
                    and temp_date.hour >= 18
                ):
                    self.ob_dict["4"].append(temp_date.timestamp())
                elif 1 > temp_date.isoweekday() > 5:
                    if temp_date.hour >= 18:
                        self.ob_dict["1"].append(temp_date.timestamp())
                    elif temp_date.hour <= 7:
                        self.ob_dict["2"].append(temp_date.timestamp())
                    else:
                        self.ob_dict["0"].append(temp_date.timestamp())
                elif temp_date.isoweekday() == 6 or temp_date.isoweekday() == 7:
                    self.ob_dict["3"].append(temp_date.timestamp())
                else:
                    self.ob_dict["0"].append(temp_date.timestamp())
            start_date += datetime.timedelta(days=1)

        avg = sum(hours_list) / len(hours_list)

        print(sum(hours_list), avg)
        self.dag_längd = avg

        self.ob_mult = 0
        self.ob_mult += len(self.ob_dict["0"]) * config["levandeVideoLön"]
        self.ob_mult += len(self.ob_dict["1"]) * (
            config["levandeVideoLön"] + config["levandeVideoLön"] * 168 / 600
        )
        self.ob_mult += len(self.ob_dict["2"]) * (
            config["levandeVideoLön"] + config["levandeVideoLön"] * 168 / 400
        )
        self.ob_mult += len(self.ob_dict["3"]) * (
            config["levandeVideoLön"] + config["levandeVideoLön"] * 168 / 300
        )
        self.ob_mult += len(self.ob_dict["4"]) * (
            config["levandeVideoLön"] + config["levandeVideoLön"] * 168 / 150
        )
        self.ob_mult /= self.dag_längd * len(hours_list)
        self.ob_mult *= 1.5

    def personal_rakna(self, config):
        # Add additional personal from specifik personal to the total personal
        if not self.specifik_personal["Empty"] and (
            self.i_data["extraPersonal"] is None or self.i_data["extraPersonal"] == 0
        ):
            if self.i_data["producent"] == self.i_data["projektledare"]:
                minus = 1
            else:
                minus = 2
            if len(self.specifik_personal["actual"]) + minus > self.personal:
                self.personal = len(self.specifik_personal["actual"]) + minus
            elif self.personal < minus:
                self.personal = minus
        self.specifik_personal = self.specifik_personal["actual"]

        self.tim_peng = math.floor(self.ob_mult * (config["lönJustering"]) / 10) * 10

        self.gig_timmar = round(self.dag_längd * self.personal * self.i_data["dagar"])

        if self.i_data["specialRigg"]:
            self.rigg_timmar = self.i_data["riggTimmar"]
        else:
            self.rigg_timmar = math.floor(self.pryl_pris * config["andelRiggTimmar"])
        if self.projekt_timmar is None:
            self.projekt_timmar = math.ceil(
                (self.gig_timmar + self.rigg_timmar) * config["projektTid"]
            )

        if self.svanis:
            self.restid = 0
        else:
            if self.tid_to_adress:
                if self.tid_to_adress_car:
                    self.restid = (
                        self.personal
                        * self.i_data["dagar"]
                        * self.tid_to_adress_car
                        / 60
                        / 60
                    )
                else:
                    self.restid = (
                        self.personal
                        * self.i_data["dagar"]
                        * self.tid_to_adress
                        / 60
                        / 60
                    )
            else:
                self.restid = self.personal * self.i_data["dagar"] * config["restid"]
        self.restid = math.ceil(self.restid)
        self.tim_budget = (
            self.gig_timmar + self.rigg_timmar + self.projekt_timmar + self.restid
        )
        if self.frilans != 0:
            self.tim_budget_frilans = (
                (self.tim_budget - (self.projekt_timmar * self.frilans))
                / self.personal
                * self.frilans
            )
        else:
            self.tim_budget_frilans = 0
        if self.personal - self.frilans != 0:
            self.tim_budget_personal = (
                (self.tim_budget + (self.projekt_timmar * self.frilans))
                / self.personal
                * (self.personal - self.frilans)
            )
        else:
            self.tim_budget_personal = 0
        # Timmar gånger peng per timme
        self.personal_pris = self.tim_budget_personal * self.tim_peng
        self.personal_pris_gammal = self.tim_budget * self.tim_peng
        self.personal_kostnad = (
            self.tim_budget_personal * config["levandeVideoLön"] * 1.5
        )
        self.personal_kostnad_gammal = self.tim_budget * config["levandeVideoLön"] * 1.5

    def post_text(self):
        try:
            if self.i_data["post_text"]:
                self.post_text_pris = (
                    self.i_data["Textning minuter"] * self.config["textningPostPris"]
                )
                self.post_text_kostnad = (
                    self.i_data["Textning minuter"] * self.config["textningPostKostnad"]
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

        self.gammal_kostnad = (
            self.pryl_kostnad
            + self.personal_kostnad_gammal
            + self.i_data["hyrKostnad"]
            + self.post_text_kostnad
            + self.frilans_hyrkostnad
        )

        if self.personal_pris_gammal != 0:
            self.personal_marginal_gammal = (
                self.personal_pris_gammal - self.personal_kostnad_gammal
            ) / self.personal_pris_gammal
        else:
            self.personal_marginal_gammal = 0

        self.kostnad = (
            self.pryl_kostnad
            + self.personal_kostnad
            + self.i_data["hyrKostnad"]
            + self.post_text_kostnad
            + self.frilans_hyrkostnad
        )

        self.pris += self.hyr_pris + self.post_text_pris + self.personal_pris_gammal

        # Prevent div by 0
        if self.personal_pris != 0:
            self.personal_marginal = (
                self.personal_pris - self.personal_kostnad
            ) / self.personal_pris
        else:
            self.personal_marginal = 0

        # Prevent div by 0
        if self.pryl_pris != 0:
            self.pryl_marginal = (self.pryl_pris - self.pryl_kostnad) / self.pryl_pris
        else:
            self.pryl_marginal = 0

        self.slit_kostnad = self.pryl_pris * config["prylSlit"]
        self.pryl_fonden = self.slit_kostnad * (1 + config["Prylinv (rel slit)"])
        print(self.pris)
        self.avkastning = round(
            self.pris
            - self.slit_kostnad
            - self.personal_kostnad
            - self.i_data["hyrKostnad"]
        )

        self.avkastning_gammal = round(
            self.pris
            - self.slit_kostnad
            - self.personal_kostnad_gammal
            - self.i_data["hyrKostnad"]
        )
        self.avkastning_without_pris = (
            -1 * self.slit_kostnad - self.personal_kostnad - self.i_data["hyrKostnad"]
        )
        self.avkastning_without_pris_gammal = (
            -1 * self.slit_kostnad
            - self.personal_kostnad_gammal
            - self.i_data["hyrKostnad"]
        )
        self.hyr_things = self.i_data["hyrKostnad"] * (
            1 - config["hyrMulti"] * config["hyrMarginal"]
        )
        try:
            self.marginal = (
                round(self.avkastning / (self.pris - self.hyr_things) * 10000) / 100
            )
        except ZeroDivisionError:
            self.marginal = 0
        try:
            self.marginal_gammal = (
                round(self.avkastning_gammal / (self.pris - self.hyr_things) * 10000)
                / 100
            )
        except ZeroDivisionError:
            self.marginal_gammal = 0
        print(self.marginal, self.marginal_gammal)

    def output(self):
        print(f"Post Text: {self.post_text_pris}")
        print(f"Pryl: {self.pryl_pris}")
        print(f"Personal: {self.personal_pris}")
        print(f"Total: {self.pris}")
        print(f"Avkastning: {self.avkastning}")

        if self.marginal > 65:
            print(f"Marginal: {Bcolors.OKGREEN + str(self.marginal)}%{Bcolors.ENDC}")
        else:
            print(f"Marginal: {Bcolors.FAIL + str(self.marginal)}%{Bcolors.ENDC}")

        self.gig_prylar = dict(
            sorted(self.gig_prylar.items(), key=lambda item: -1 * item[1]["amount"])
        )
        packlista = "# Packlista:\n\n"
        for pryl in self.gig_prylar:
            packlista += f"### {self.gig_prylar[pryl]['amount']}st {pryl}\n\n"
            print(
                f"\t{self.gig_prylar[pryl]['amount']}st {pryl} - {self.gig_prylar[pryl]['mod']} kr ",
                f"- {self.gig_prylar[pryl]['dagarMod']} kr pga {self.i_data['dagar']} dagar",
            )

        paket_id_list = []
        pryl_id_list = []

        if self.i_data["prylPaket"] is not None:
            for paket in self.i_data["prylPaket"]:
                paket_id_list.append(self.paketen[paket]["id"])

        if self.i_data["extraPrylar"] is not None:
            for pryl in self.i_data["extraPrylar"]:
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
        if self.update:
            _unusedrec_id = self.i_data["uppdateraProjekt"][0]["id"]
        else:
            _unusedrec_id = None

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
        if not self.update:
            for key in old_output:
                # Strip key of number delimiter
                if re.findall(r"(.*) #\d", key)[0] == self.name:
                    leverans_nummer += 1
        self.old_output = old_output
        if self.i_data["post_text"] is None:
            self.i_data["post_text"] = False

        if self.i_data["Projekt typ"] is None:
            self.i_data["Projekt typ"] = {}
            self.i_data["Projekt typ"]["name"] = None
        if self.i_data["Beställare"] is None:
            self.i_data["Beställare"] = [{"id": None}]
        if self.i_data["projektledare"] is None:
            self.i_data["projektledare"] = [{"id": None}]
        if self.i_data["producent"] is None:
            self.i_data["producent"] = [{"id": None}]
        if self.i_data["Kund"] is None:
            self.i_data["Kund"] = [{"id": None}]
        if self.i_data["Beställare"] is None:
            self.i_data["Beställare"] = [{"id": None}]
        if self.i_data["existerande_adress"] is None:
            if self.i_data["Adress"] is not None:
                self.i_data["existerande_adress"] = self.i_data["Adress"]
            else:
                self.i_data["existerande_adress"] = None
        else:
            self.i_data["existerande_adress"] = self.i_data["existerande_adress"][0][
                "name"
            ]
        print(self.i_data["Kund"], self.i_data["Beställare"])

        output = {
            "Gig namn": f"{self.name} #{leverans_nummer}",
            "Pris": self.pris,
            "Personal": self.personal,
            "Projekt timmar": self.gig_timmar,
            "Rigg timmar": self.rigg_timmar,
            "Totalt timmar": self.tim_budget,
            "Pryl pris": self.pryl_pris,
            "prylPaket": paket_id_list,
            "extraPrylar": pryl_id_list,
            "antalPrylar": antal_string,
            "antalPaket": antal_paket_string,
            "Projekt kanban": self.name,
            "Projekt": self.name,
            "börjaDatum": self.i_data["Börja datum"],
            "slutaDatum": self.i_data["Sluta datum"],
            "dagar": self.i_data["dagar"],
            "packlista": packlista,
            "restid": self.restid,
            "projektTid": self.projekt_timmar,
            "dagLängd": str(self.dag_längd),
            "slitKostnad": self.slit_kostnad,
            "prylFonden": self.pryl_fonden,
            "hyrthings": self.hyr_things,
            "avkastWithoutPris": self.avkastning_without_pris,
            "frilanstimmar": self.tim_budget_frilans,
            "total_tid_ex_frilans": self.tim_budget_personal,
            "frilans": self.frilans_lista,
            "projektledare": self.i_data["projektledare"][0]["id"],
            "producent": [x["id"] for x in self.i_data["producent"]],
            "leverans_nummer": leverans_nummer,
            "Kund": self.i_data["Kund"][0]["id"],
            "Svanis": self.svanis,
            "Typ": self.i_data["Projekt typ"]["name"],
            "Adress": self.i_data["existerande_adress"],
            "Beställare": [self.i_data["Beställare"][0]["id"]],
            "input_id": self.i_data["input_id"],
            "made_by": [self.i_data["input_id"]],
            "post_deadline": self.i_data["post_deadline"],
            "avkast2": self.avkastning_without_pris_gammal,
            "Mer folk": list(map(itemgetter("id"), self.specifik_personal)),
        }

        for key in list(output.keys()):
            if output[key] is None:
                del output[key]

        print(time.time() - self.start_time)
        if self.update:
            output.pop("Gig namn", None)
            output.pop("producent", None)
            output.pop("projektledare", None)
            body = {
                "records": [
                    {"id": self.i_data["uppdateraProjekt"][0]["id"], "fields": output}
                ],
                "typecast": True,
            }
            output_from_airtable = requests.patch(
                url="https://api.airtable.com/v0/appG1QEArAVGABdjm/Leveranser",
                json=body,
                headers={
                    "Authorization": "Bearer " + api_key,
                    "Content-Type": "application/json",
                },
            )
            output_from_airtable = output_from_airtable.json()["records"][0]

        else:
            output_from_airtable = self.output_table.create(output, typecast=True)
        print(time.time() - self.start_time)
        self.airtable_record = output_from_airtable["id"]
        # print(output)
        projektkalender_records = []

        if self.i_data["Frilans"] is not None:
            frilans_personer = []
            for record in self.i_data["Frilans"]:
                frilans_personer.append(record["id"])
        else:
            frilans_personer = None
        i = 0
        record_ids = []
        # Add the dates to the projektkalender table
        if self.update:
            for item in output_from_airtable["fields"]["Projekt kalender"]:
                # Get all record ids of the already existing linked records in the projektkalender table
                record_ids.append(item)

        for getin, getout in self.dagar_list:

            kalender_dict = {
                "Name": self.name,
                "Getin-hidden": getin.isoformat(),
                "Getout-hidden": getout.isoformat(),
                "Projekt": output_from_airtable["fields"]["Projekt"],
                "Leverans": [output_from_airtable["id"]],
                "Frilans": frilans_personer,
            }
            if self.update and len(self.dagar_list) == len(record_ids):
                projektkalender_records.append(
                    {"id": record_ids[i], "fields": kalender_dict}
                )
            else:
                projektkalender_records.append(kalender_dict)
            i += 1
        if self.update:
            if len(projektkalender_records) != len(record_ids):
                self.kalender_table.batch_delete(record_ids)
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
        self.old_output[f"{self.name} #{self.leverans_nummer}"] = self.output_variable

    def url_make(self):
        paket = ""
        prylar = ""
        if "pryl_paket_id" in self.i_data:
            for ID in self.i_data["pryl_paket_id"]:
                paket += ID["id"] + ","
        if "extra_prylar_id" in self.i_data:
            for ID in self.i_data["extra_prylar_id"]:
                prylar += ID["id"] + ","
        paket = paket[0:-1]
        prylar = prylar[0:-1]

        params = {
            "prefill_projektledare": self.i_data["projektledare"][0]["id"],
            "prefill_producent": self.i_data["producent"][0]["id"],
            "prefill_prylPaket": paket,
            "prefill_extraPrylar": prylar,
            "prefill_antalPaket": self.i_data["antalPaket"],
            "prefill_antalPrylar": self.i_data["antalPrylar"],
            "prefill_extraPersonal": self.i_data["extraPersonal"],
            "prefill_hyrKostnad": self.i_data["hyrKostnad"],
            "prefill_tid för gig": self.i_data["tid för gig"],
            "prefill_post_text": self.i_data["post_text"],
            "prefill_Textning minuter": self.i_data["Textning minuter"],
            "prefill_Kund": self.i_data["Kund"][0]["id"],
            "prefill_Frilans": self.i_data["Frilans"],
            "prefill_Adress": self.i_data["Adress"],
            "prefill_gigNamn": self.name,
            "prefill_Beställare": self.i_data["Beställare"][0]["id"],
            "prefill_Projekt typ": self.i_data["Projekt typ"]["name"],
            "prefill_Mer_personal": ",".join(
                [x["id"] for x in self.specifik_personal if x["id"] is not None]
            ),
        }

        update_params = copy.deepcopy(params)
        update_params.update(
            {
                "prefill_uppdateraa": True,
                "prefill_uppdateraProjekt": self.airtable_record,
                "prefill_Börja datum": self.i_data["Börja datum"],
                "prefill_preSluta datum": self.i_data["preSluta datum"],
            }
        )
        copy_params = copy.deepcopy(params)
        copy_params.update({"prefill_nytt_projekt": False, "prefill_gigNamn": None})

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
            "https://airtable.com/shrQOV05GKoC6rjJz"
            + "?"
            + urllib.parse.urlencode(update_params)
        )
        self.copy_url = (
            "https://airtable.com/shrQOV05GKoC6rjJz"
            + "?"
            + urllib.parse.urlencode(copy_params)
        )
        self.output_table.update(
            self.airtable_record,
            {"link_to_update": self.update_url, "link_to_copy": self.copy_url},
        )

    def updating(self):
        input_data_table = Table(api_key, base_id, "Input data")

        del_list = []
        for key, value in self.i_data.items():
            if value is None and key not in ["extraPrylar", "prylPaket"]:
                del_list.append(key)
        for key in del_list:
            del self.i_data[key]
        _unused_old_input_id = copy.deepcopy(self.i_data["old_input_id"])
        input_id = copy.deepcopy(self.i_data["input_id"])
        self.i_data["Projekt typ"] = self.i_data["Projekt typ"]["name"]
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

        if self.producent != self.projektledare:
            if not self.update:
                all_people.append(self.producent[0]["name"])
                all_people.append(self.projektledare[0]["name"])
            else:
                time_ = time.time()
                test_list = {x["id"]: x["fields"] for x in self.output_table.all()}
                print(time.time() - time_)

        else:
            if self.update:
                self.output_table.get()
            else:
                all_people.append(self.producent[0]["name"])

        for person in self.specifik_personal:

            all_people.append(person["name"])
        for person in all_people:
            if person is None:
                del all_people[all_people.index(person)]
        records = []
        for dag in self.dagar_list:
            for person in all_people:
                records.append(
                    {
                        "Gig": [self.airtable_record],
                        "Start tid": dag[0].hour * 60 * 60 + dag[0].minute * 60,
                        "Tid": (dag[1].hour - dag[0].hour) * 60 * 60
                        + (dag[1].minute - dag[0].minute) * 60,
                        "unused": True,
                        "Datum": dag[0].isoformat(),
                        "Person": person,
                    }
                )

        if self.update:
            update_records = []
            delete_list = []
            create_list = []

            for record in records:
                if record["Person"] in self.tid_rapport:
                    for entry in self.tid_rapport:
                        if record["Person"] == entry["name"]:
                            update_records.append({"id": entry["id"], "fields": record})
                else:
                    create_list.append(record)

            for entry in self.tid_rapport:
                if entry["name"] not in all_people:
                    delete_list.append(entry["id"])

            out_list = []
            if update_records != []:
                outupdate = tid_table.batch_update(update_records, typecast=True)
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
                tid_out.append({"id": record["id"], "name": record["fields"]["Person"]})
            self.old_output[f"{self.name} #{self.leverans_nummer}"][
                "tidrapport"
            ] = tid_out

        else:
            tid_out = []
            out = tid_table.batch_create(records, typecast=True)
            for record in out:
                tid_out.append({"id": record["id"], "name": record["fields"]["Person"]})
            self.old_output[f"{self.name} #{self.leverans_nummer}"][
                "tidrapport"
            ] = tid_out

    def output_to_json(self):

        with open("output.json", "w", encoding="utf-8") as f:
            json.dump(self.old_output, f, ensure_ascii=False, indent=2)
        with open("log.json", "w", encoding="utf-8") as f:
            self.log.append(
                {f"{self.name} #{self.leverans_nummer}": self.output_variable}
            )
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
        url="https://hooks.airtable.com/workflows/v1/genericWebhook/appG1QEArAVGABdjm/wflcP4lYCTDwmSs4g"  # skipcq  FLK-E251
        "/wtrzRoN98kiDzdU05",
        json=backup,
    )

    with open("output.json", "w", encoding="utf-8") as f:
        output[backup["Gig namn"]] = backup
        json.dump(output, f, ensure_ascii=False, indent=2)
    return "OK!", 200


@app.route("/test-auth", methods=["POST"])
@token_required
def auth_test():
    return "OK!", 200


@app.route("/start", methods=["POST"])
@token_required
def start():
    i_data = request.json
    # Clean junk from data
    try:
        i_data_name = request.json["key"]
        i_data = i_data["Input data"]
    except KeyError:
        i_data_name = list(i_data.keys())[-1]

    for key in i_data:

        pryl_list = []
        paket_list = []
        if i_data[key]["extraPrylar"] is not None:
            i = 0
            i_data[key]["extra_prylar_id"] = copy.deepcopy(i_data[key]["extraPrylar"])
            for pryl in i_data[key]["extraPrylar"]:
                pryl.pop("id", None)
                pryl_list.append(i_data[key]["extraPrylar"][i]["name"])
                i += 1
            i_data[key]["extraPrylar"] = pryl_list

        if i_data[key]["prylPaket"] is not None:
            i = 0
            i_data[key]["pryl_paket_id"] = copy.deepcopy(i_data[key]["prylPaket"])
            for paket in i_data[key]["prylPaket"]:
                paket.pop("id", None)
                paket_list.append(i_data[key]["prylPaket"][i]["name"])
                i += 1
            i_data[key]["prylPaket"] = paket_list

    # Save data just because
    with open("input.json", "w", encoding="utf-8") as f:
        json.dump(i_data, f, ensure_ascii=False, indent=2)

    # Load all the important data
    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)
    with open("paket.json", "r", encoding="utf-8") as f:
        paket = json.load(f)
    with open("prylar.json", "r", encoding="utf-8") as f:
        prylar = json.load(f)
    if i_data_name == "Unnamed record":
        if i_data["Unnamed record"]["uppdateraa"] is not None:
            # If the record is to be updated, get it from the i_data and remove the numbering from the name
            i_data_name = re.split(
                r" #\d+", i_data["Unnamed record"]["uppdateraProjekt"][0]["name"]
            )[0]
        else:
            # If input is not update treat as new leverans to projekt
            i_data_name = i_data["Unnamed record"]["Projekt"][0]["name"]

        i_data[i_data_name] = i_data["Unnamed record"]
    Gig(i_data, config, prylar, paket, i_data_name)

    return "OK!", 200


data = ["test0", "test1"]


# Route for updating the configurables
@app.route("/update/config", methods=["POST"])
@token_required
def get_prylar():

    # Make the key of configs go directly to the value
    for configurable in request.json["Config"]:
        request.json["Config"][configurable] = request.json["Config"][configurable][
            "Siffra i decimal"
        ]

    config = request.json["Config"]

    # Format prylar better
    prylarna = request.json["Prylar"]
    pryl_dict = {}
    for prylNamn in prylarna:
        pryl = Prylob(
            in_pris=prylarna[prylNamn]["pris"],
            name=prylNamn,
            livs_längd=int(prylarna[prylNamn]["livsLängd"]["name"]),
        )
        pryl.rounding(config)
        pryl_dict.update(pryl.dict_make())

    paketen = request.json["Prylpaket"]
    paket_dict = {}
    for paket in paketen:
        lista = []
        paketen[paket]["name"] = paket
        try:
            for pryl in paketen[paket]["paket_prylar"]:
                lista.append(pryl["name"])

            paketen[paket]["paket_prylar"] = lista
        except KeyError:
            pass
        paketen[paket]["paket_dict"] = paket_dict
        paket = Paketob(pryl_dict, paketen[paket])
        paket_dict.update(paket.dict_make())

    prylar_table = Table(api_key, base_id, "Prylar")
    paket_table = Table(api_key, base_id, "Prylpaket")
    for record in prylar_table.all():
        pryl_dict[str(record["fields"]["Pryl Namn"])].update({"id": record["id"]})
    for record in paket_table.all():
        paket_dict[str(record["fields"]["Paket Namn"])].update({"id": record["id"]})

    # Save data to file
    with open("prylar.json", "w", encoding="utf-8") as f:
        json.dump(pryl_dict, f, ensure_ascii=False, indent=2)

    with open("config.json", "w", encoding="utf-8") as f:
        json.dump(request.json["Config"], f, ensure_ascii=False, indent=2)
    with open("paket.json", "w", encoding="utf-8") as f:
        json.dump(paket_dict, f, ensure_ascii=False, indent=2)
    with open("frilans.json", "w", encoding="utf-8") as f:
        json.dump(request.json["Frilans"], f, ensure_ascii=False, indent=2)
    with open("folk.json", "w", encoding="utf-8") as f:
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
