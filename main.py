import copy
import json
import math
import os
import pandas as pd
import requests
from flask import Flask, request
from pyairtable import Table
import time


class Bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


# pd.set_option('display.max_colwidth', None)
pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)

# pd.set_option('display.width', 150)

api_key = os.environ['api_key']
base_id = os.environ['base_id']

output_table = Table(api_key, base_id, 'Output table')

# time.sleep(10)

beforeTime = time.time()
output_tables = []

print(time.time() - beforeTime)

app = Flask(__name__)


class Prylob:
    def __init__(self, **kwargs):
        # Gets all attributes provided and adds them to self
        # Current args: name, in_pris, pris
        self.in_pris = None
        self.livsLängd = 3
        self.pris = None
        for argName, value in kwargs.items():
            self.__dict__.update({argName: value})

        self.amount = 1
        self.mult = 145
        self.mult -= self.livsLängd * 15
        self.mult /= 100

        print(self.mult)

    def rounding(self, config):
        # Convert to lower price as a percentage of the buy price
        self.pris = math.floor((float(self.in_pris) * config["prylKostnadMulti"]) / 10 * self.mult) * 10

    def dict_make(self):
        temp_dict = vars(self)
        out_dict = {temp_dict["name"]: temp_dict}
        out_dict[temp_dict["name"]].pop('name', None)
        return out_dict

    def amount_calc(self, ind, antal_av_pryl):
        self.amount = antal_av_pryl[ind]


class Paketob:
    def __init__(self, prylar, args):
        # Gets all kwargs provided and adds them to self
        # Current kwargs:
        # print(args, "test")
        self.paket_prylar = []
        self.antal_av_pryl = None
        self.paket_dict = {}
        self.paket_i_pryl_paket = None
        for argName, value in args.items():
            # print(argName, value)
            self.__dict__.update({argName: value})

        self.pris = 0
        self.prylar = {}
        # print(prylar)

        if self.paket_i_pryl_paket is not None:
            for paket in self.paket_i_pryl_paket:
                # print(paket, self.paket_dict[paket["name"]])
                for pryl in self.paket_dict[paket["name"]]["prylar"]:
                    if pryl in self.prylar.keys():
                        self.prylar[pryl]["amount"] += 1
                    else:
                        self.prylar[pryl] = copy.deepcopy(self.paket_dict[paket["name"]]["prylar"][pryl])
        else:
            try:
                # Add pryl objects to self list of all prylar in paket
                self.antal_av_pryl = str(self.antal_av_pryl).split(",")
                for pryl in self.paket_prylar:
                    ind = self.paket_prylar.index(pryl)

                    self.prylar.update({pryl: copy.deepcopy(prylar[pryl])})
                    self.prylar[pryl]["amount"] = int(self.antal_av_pryl[ind])

                # print(self.prylar, "\n\n\n\n")
            except AttributeError:
                pass
        # Set total price of prylar in paket
        for pryl in self.prylar:
            self.pris += (self.prylar[pryl]["pris"] * self.prylar[pryl]["amount"])

    def dict_make(self):
        temp_dict = vars(self)
        out_dict = {temp_dict["name"]: temp_dict}
        out_dict[temp_dict["name"]].pop('paket_prylar', None)
        bok = {}
        try:
            for dubbelPaket in out_dict[temp_dict["name"]]["paket_i_pryl_paket"][0]:
                bok.update({"name": out_dict[temp_dict["name"]]["paket_i_pryl_paket"][0][dubbelPaket]})
            out_dict[temp_dict["name"]]["paket_i_pryl_paket"] = bok
        except KeyError:
            pass

        out_dict[temp_dict["name"]].pop('paket_dict', None)
        out_dict[temp_dict["name"]].pop('Input data', None)
        out_dict[temp_dict["name"]].pop('Output table', None)
        out_dict[temp_dict["name"]].pop('name', None)

        return out_dict


class Gig:
    def __init__(self, i_data, config, prylar, paketen, name):
        self.output_table = Table(api_key, base_id, 'Output table')
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
        self.projekt_timmar = None
        self.gig_timmar = None
        self.tim_peng = None
        self.personal = None
        self.paketen = paketen
        self.prylar = prylar
        self.marginal = 0
        self.gig_prylar = {}
        self.pre_gig_prylar = []
        self.name = name
        self.i_data = i_data[self.name]
        self.pryl_pris = 0
        self.pris = 0
        self.in_pris = 0
        self.update = False
        try:
            if self.i_data["uppdateraProjekt"]:
                self.update = True
        except KeyError:
            pass

        try:
            if self.i_data["extraPersonal"] is not None:
                self.personal = self.i_data["extraPersonal"]
            else:
                self.personal = 0
        except KeyError:
            self.personal = 0
        try:
            if i_data["svanis"]:
                self.svanis = True
        except KeyError:
            self.svanis = False

        # Take all prylar and put them inside a list
        try:
            self.check_prylar(prylar)
        except KeyError:
            pass
        # Take all prylar from paket and put them inside a list
        try:
            self.check_paket()
        except KeyError:
            pass
        # Add accurate count to all prylar and compile them from list to dict
        self.count_them()
        # Modify pryl_pris based on factors such as svanis
        self.pryl_mod(config)
        # Get the total modPris and in_pris from all the prylar
        self.get_pris()

        self.personal_rakna(config)
        self.marginal_rakna(config)
        self.output()

    def check_prylar(self, prylar):
        try:
            if self.i_data["antalPrylar"]:
                try:
                    int(self.i_data["antalPrylar"])
                    self.i_data["antalPrylar"] = [self.i_data["antalPrylar"]]
                except ValueError:
                    self.i_data["antalPrylar"] = self.i_data["antalPrylar"].split(",")
            if self.i_data["antalPrylar"] is not None:
                antal = True
            else:
                antal = False
        except KeyError:
            antal = False
        i = 0
        for pryl in self.i_data["extraPrylar"]:
            if antal:

                try:
                    for j in range(int(self.i_data["antalPrylar"][i])):
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
            if self.i_data["antalPaket"] is not None:
                antal = True
            else:
                antal = False
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
                        for j in range(int(self.i_data["antalPaket"][i])):
                            self.pre_gig_prylar.append({pryl: self.paketen[paket]["prylar"][pryl]})
                    except IndexError:
                        self.pre_gig_prylar.append({pryl: self.paketen[paket]["prylar"][pryl]})
                else:
                    # Add pryl from paket to prylList
                    self.pre_gig_prylar.append({pryl: self.paketen[paket]["prylar"][pryl]})
            i += 1

    def count_them(self):
        # print(self.pre_gig_prylar, "hi")
        i = 0
        for pryl in self.pre_gig_prylar:
            for key in pryl:
                # print(i, key, "\n", list(self.gig_prylar.keys()), "\n")
                if key in list(self.gig_prylar.keys()):
                    self.gig_prylar[key]["amount"] += copy.deepcopy(self.pre_gig_prylar[i][key]["amount"])
                    # print("hi", key, self.gig_prylar[key]["amount"])
                else:
                    self.gig_prylar.update(copy.deepcopy(self.pre_gig_prylar[i]))
            i += 1
        # print(self.gig_prylar)

    def pryl_mod(self, config):

        for pryl in self.gig_prylar:
            self.in_pris += self.gig_prylar[pryl]["inPris"]

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
            self.in_pris += self.gig_prylar[pryl]["inPris"]
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
            print(dagar)
        if dagar < 1:
            temp_pris = 0
        elif dagar >= 2:
            temp_pris *= (1 + dag_tva_multi)
        if dagar >= 3:
            temp_pris += pris * dag_tre_multi * (dagar - 2)
        return temp_pris

    def personal_rakna(self, config):
        self.tim_peng = math.floor(config["levandeVideoLön"] * (config["lönJustering"]) / 10) * 10

        self.gig_timmar = round(int(self.i_data["dagLängd"]["name"]) * self.personal * self.i_data["dagar"])

        if self.i_data["specialRigg"]:
            self.rigg_timmar = self.i_data["riggTimmar"]
        else:
            self.rigg_timmar = math.floor(self.pris * config["andelRiggTimmar"])

        self.projekt_timmar = math.ceil((self.gig_timmar + self.rigg_timmar) * config["projektTid"])

        if self.svanis:
            self.restid = 0
        else:
            self.restid = self.personal * self.i_data["dagar"] * config["restid"]

        self.tim_budget = self.gig_timmar + self.rigg_timmar + self.projekt_timmar + self.restid
        # Timmar gånger peng per timme
        self.personal_pris = self.tim_budget * self.tim_peng

        self.personal_kostnad = self.tim_budget * config["levandeVideoLön"]
        self.pris += self.personal_pris
        # print(self.tim_budget, self.restid, self.projekt_timmar, self.gig_timmar, self.rigg_timmar, self.svanis)

    def marginal_rakna(self, config):
        try:
            if self.i_data["hyrKostnad"] is None:
                self.i_data["hyrKostnad"] = 0
        except KeyError:
            self.i_data["hyrKostnad"] = 0

        self.hyr_pris = self.i_data["hyrKostnad"] * (1 + config["hyrMulti"])
        self.kostnad = self.pryl_kostnad + self.personal_kostnad + self.i_data["hyrKostnad"]
        self.pris += self.hyr_pris

        # Prevent div by 0
        if self.personal_pris != 0:
            self.personal_marginal = (self.personal_pris - self.personal_kostnad) / self.personal_pris
        else:
            self.personal_marginal = 0

        # Prevent div by 0
        if self.pryl_pris != 0:
            self.pryl_marginal = (self.pryl_pris - self.pryl_kostnad) / self.pryl_pris
        else:
            self.pryl_marginal = 0
        # TODO
        #  Add resekostnader
        #  F19, F20 i arket

        self.slit_kostnad = self.pryl_pris * config["prylSlit"]

        self.avkastning = round(
            self.pris - self.slit_kostnad - self.personal_kostnad - self.i_data["hyrKostnad"]
        )

        self.marginal = round(
            self.avkastning / (
                    self.pris - self.i_data["hyrKostnad"] * (1 - config["hyrMulti"] * config["hyrMarginal"])
            ) * 10000
        ) / 100

    def output(self):
        print(f"Pryl: {self.pryl_pris}")
        print(f"Personal: {self.personal_pris}")
        print(f"Total: {self.pris}")
        print(f"Avkastning: {self.avkastning}")

        if self.marginal > 65:
            print(f"Marginal: {Bcolors.OKGREEN + str(self.marginal)}%{Bcolors.ENDC}")
        else:
            print(f"Marginal: {Bcolors.FAIL + str(self.marginal)}%{Bcolors.ENDC}")

        self.gig_prylar = dict(sorted(self.gig_prylar.items(), key=lambda item: -1 * item[1]["amount"]))

        for pryl in self.gig_prylar:
            print(
                f"\t{self.gig_prylar[pryl]['amount']}st {pryl} - {self.gig_prylar[pryl]['mod']} kr ",
                f"- {self.gig_prylar[pryl]['dagarMod']} kr pga {self.i_data['dagar']} dagar")

        paket_id_list = []
        pryl_id_list = []

        # print(self.paketen)
        try:
            for paket in self.i_data["prylPaket"]:
                paket_id_list.append(self.paketen[paket]["id"])
        except KeyError:
            pass

        try:
            for pryl in self.i_data["extraPrylar"]:
                pryl_id_list.append(self.prylar[pryl]["id"])

        except KeyError:
            pass
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
            rec_id = self.i_data["uppdateraProjekt"][0]["id"]
        else:
            rec_id = None
        output = {
            "Gig namn": self.name,
            "Pris": self.pris,
            "Marginal": str(self.marginal) + "%",
            "marginalSecret": self.marginal,
            "Personal": self.personal,
            "Projekt timmar": self.gig_timmar,
            "Rigg timmar": self.rigg_timmar,
            "Totalt timmar": self.tim_budget,
            "Pryl pris": self.pryl_pris,
            "prylPaket": paket_id_list,
            "extraPrylar": pryl_id_list,
            "antalPrylar": antal_string,
            "antalPaket": antal_paket_string,
            "update": self.update,
            "recID": rec_id
        }

        # print(output)
        requests.post(
            url="https://hooks.airtable.com/workflows/v1/genericWebhook/appG1QEArAVGABdjm/wflcP4lYCTDwmSs4g"
                "/wtrzRoN98kiDzdU05",
            json=output)
        # self.output_table.create(output)


@app.route("/airtable", methods=["POST"])
def fuck_yeah():
    i_data = request.json
    # Load all the important data
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    with open('paket.json', 'r', encoding='utf-8') as f:
        paket = json.load(f)
    with open('prylar.json', 'r', encoding='utf-8') as f:
        prylar = json.load(f)
    i_data_name = list(i_data.keys())[-1]

    Gig(i_data, config, prylar, paket, i_data_name)
    return "<3"


@app.route("/", methods=["GET"])
def the_basics():
    return "Hello <3"


@app.route("/start", methods=["POST", "GET"])
def start():
    i_data = request.json["Input data"]
    # Clean junk from data
    try:
        if request.json["key"]:
            pass
        i_data_name = request.json["key"]
    except KeyError:
        i_data_name = list(i_data.keys())[-1]

    for key in i_data:
        pryl_list = []
        paket_list = []
        try:
            i = 0
            for pryl in i_data[key]["extraPrylar"]:
                pryl.pop("id", None)
                pryl_list.append(i_data[key]["extraPrylar"][i]["name"])
                i += 1
            i_data[key]["extraPrylar"] = pryl_list
        except (KeyError, AttributeError):
            pass
        try:
            i = 0
            for paket in i_data[key]["prylPaket"]:
                paket.pop("id", None)
                paket_list.append(i_data[key]["prylPaket"][i]["name"])
                i += 1
            i_data[key]["prylPaket"] = paket_list
        except (KeyError, AttributeError):
            pass

    # Save data just because
    with open('input.json', 'w', encoding='utf-8') as f:
        json.dump(i_data, f, ensure_ascii=False, indent=2)

    # Load all the important data
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    with open('paket.json', 'r', encoding='utf-8') as f:
        paket = json.load(f)
    with open('prylar.json', 'r', encoding='utf-8') as f:
        prylar = json.load(f)

    Gig(i_data, config, prylar, paket, i_data_name)

    return "<3"


data = ["test0", "test1"]


# Route for updating the configurables
@app.route("/update/config", methods=["POST"])
def get_prylar():
    global api_key, base_id
    # Make the key of configs go directly to the value
    for configurable in request.json["Config"]:
        request.json["Config"][configurable] = request.json["Config"][configurable]["Siffra i decimal"]

    config = request.json["Config"]

    # Format prylar better
    prylarna = request.json["Prylar"]
    pryl_dict = {}
    for prylNamn in prylarna:
        pryl = Prylob(inPris=prylarna[prylNamn]["pris"], name=prylNamn,
                      livsLängd=int(prylarna[prylNamn]["livsLängd"]["name"]))
        pryl.rounding(config)
        pryl_dict.update(pryl.dict_make())

    paketen = request.json["Pryl Paket"]
    paket_dict = {}
    for paket in paketen:
        lista = []
        paketen[paket]["name"] = paket
        try:
            for pryl in paketen[paket]["paketPrylar"]:
                lista.append(pryl["name"])

            paketen[paket]["paketPrylar"] = lista
        except KeyError:
            pass
        paketen[paket]["paket_dict"] = paket_dict
        paket = Paketob(pryl_dict, paketen[paket])
        paket_dict.update(paket.dict_make())

    prylar_table = Table(api_key, base_id, "Prylar")
    paket_table = Table(api_key, base_id, "Pryl Paket")
    for record in prylar_table.all():
        pryl_dict[str(record["fields"]["Pryl Namn"])].update({"id": record["id"]})
    for record in paket_table.all():
        paket_dict[str(record["fields"]["Paket Namn"])].update({"id": record["id"]})

    # Save data to file
    with open('prylar.json', 'w', encoding='utf-8') as f:
        json.dump(pryl_dict, f, ensure_ascii=False, indent=2)

    with open('config.json', 'w', encoding='utf-8') as f:
        json.dump(request.json["Config"], f, ensure_ascii=False, indent=2)
    with open('paket.json', 'w', encoding='utf-8') as f:
        json.dump(paket_dict, f, ensure_ascii=False, indent=2)
    return "Tack"


@app.route("/update", methods=["POST"])
def update():
    with open('everything.json', 'w', encoding='utf-8') as f:
        json.dump(request.json, f, ensure_ascii=False, indent=2)
    return "<3"


def server():
    app.run(host='0.0.0.0')


personal = 0

svanis = False

# prylLista = prylarOchPersonalAvPaket({"prylPaket": ["id0"]})

# print(fixaPrylarna({"extraPrylar": '1 "id0"', "prylLista": prylLista}))


"""
def raknaTillganglighetsTjanster(inputData):
  tillganglighetsPris = 0
  tillganglighetsKostnad = 0
  if inputData["textningOchÖversättning"] == "Ja":
    tillganglighetsPris += inputData["postMinuter"]*300
    tillganglighetsKostnad += inputData["postMinuter"]*160

  elif inputData["textning"] == "Post":
    tillganglighetsPris += inputData["postMinuter"]*120
    tillganglighetsKostnad += inputData["postMinuter"]*50

  elif inputData["textning"] == "Live":
    tillganglighetsPris += inputData["liveMinuter"]
    tillganglighetsKostnad += inputData["liveMinuter"]
  if inputData["syntolkning"] == "Live":
    tillganglighetsPris += inputData[liveMinuter]
    tillganglighetsKostnad += inputData["liveMinuter"]
  elif inputData["syntolking"] == "Post":



    
  tillganglighetsInfo = {}
  return tillganglighetsInfo
"""

inputFields = ["gigNamn", "prylPaket", "dagLängd", "extraPrylar", "dagLängd", "dagar", "extraPersonal", "hyrKostnad",
               "antalPaket", "antalPrylar", "extraPrylar", "projekt"]
paketFields = ["Paket Namn", "Paket i prylPaket", "Prylar", "Antal Prylar", "Personal", "Svanis", "Hyreskostnad"]
prylFields = ["Pryl Namn", "pris"]

# config = {}


server()
