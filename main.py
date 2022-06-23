import copy
import json
import math
import os
import pandas as pd
import requests
from flask import Flask, request
from pyairtable import Table
import time


class bcolors:
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


class prylOb:
    def __init__(self, **kwargs):
        # Gets all attributes provided and adds them to self
        # Current args: name, inPris, pris
        self.inPris = None
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
        self.pris = math.floor((float(self.inPris) * config["prylKostnadMulti"]) / 10 * self.mult) * 10

    def dict_make(self):
        temp_dict = vars(self)
        out_dict = {temp_dict["name"]: temp_dict}
        out_dict[temp_dict["name"]].pop('name', None)
        return out_dict

    def amount_calc(self, ind, antal_av_pryl):
        self.amount = antal_av_pryl[ind]


class paketOb:
    def __init__(self, prylar, args):
        # Gets all kwargs provided and adds them to self
        # Current kwargs:
        # print(args, "test")
        self.paketPrylar = []
        self.antalAvPryl = None
        self.paketDict = {}
        self.paketIPrylPaket = None
        for argName, value in args.items():
            # print(argName, value)
            self.__dict__.update({argName: value})

        self.pris = 0
        self.prylar = {}
        # print(prylar)

        if self.paketIPrylPaket is not None:
            for paket in self.paketIPrylPaket:
                # print(paket, self.paketDict[paket["name"]])
                for pryl in self.paketDict[paket["name"]]["prylar"]:
                    if pryl in self.prylar.keys():
                        self.prylar[pryl]["amount"] += 1
                    else:
                        self.prylar[pryl] = copy.deepcopy(self.paketDict[paket["name"]]["prylar"][pryl])
        else:
            try:
                # Add pryl objects to self list of all prylar in paket
                self.antalAvPryl = str(self.antalAvPryl).split(",")
                for pryl in self.paketPrylar:
                    ind = self.paketPrylar.index(pryl)

                    self.prylar.update({pryl: copy.deepcopy(prylar[pryl])})
                    self.prylar[pryl]["amount"] = int(self.antalAvPryl[ind])

                # print(self.prylar, "\n\n\n\n")
            except AttributeError:
                pass
        # Set total price of prylar in paket
        for pryl in self.prylar:
            self.pris += (self.prylar[pryl]["pris"] * self.prylar[pryl]["amount"])

    def dictMake(self):
        tempDict = vars(self)
        outDict = {tempDict["name"]: tempDict}
        outDict[tempDict["name"]].pop('paketPrylar', None)
        bok = {}
        try:
            for dubbelPaket in outDict[tempDict["name"]]["paketIPrylPaket"][0]:
                bok.update({"name": outDict[tempDict["name"]]["paketIPrylPaket"][0][dubbelPaket]})
            outDict[tempDict["name"]]["paketIPrylPaket"] = bok
        except KeyError:
            pass

        outDict[tempDict["name"]].pop('paketDict', None)
        outDict[tempDict["name"]].pop('Input data', None)
        outDict[tempDict["name"]].pop('Output table', None)
        outDict[tempDict["name"]].pop('name', None)

        return outDict


class gig:
    def __init__(self, i_data, config, prylar, paketen, name):
        self.outputTable = Table(api_key, base_id, 'Output table')
        self.slitKostnad = None
        self.avkastning = None
        self.prylMarginal = None
        self.personalMarginal = None
        self.kostnad = None
        self.prylKostnad = None
        self.hyrPris = None
        self.personalKostnad = None
        self.personalPris = None
        self.timBudget = None
        self.restid = None
        self.riggTimmar = None
        self.projektTimmar = None
        self.gigTimmar = None
        self.timPeng = None
        self.personal = None
        self.paketen = paketen
        self.prylar = prylar
        self.marginal = 0
        self.gigPrylar = {}
        self.preGigPrylar = []
        self.name = name
        self.iData = i_data[self.name]
        self.prylPris = 0
        self.pris = 0
        self.inPris = 0
        self.update = False
        try:
            if self.iData["uppdateraProjekt"]:
                self.update = True
        except KeyError:
            pass

        try:
            if self.iData["extraPersonal"] is not None:
                self.personal = self.iData["extraPersonal"]
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
            self.checkPrylar(prylar)
        except KeyError:
            pass
        # Take all prylar from paket and put them inside a list
        try:
            self.check_paket()
        except KeyError:
            pass
        # Add accurate count to all prylar and compile them from list to dict
        self.count_them()
        # Modify prylPris based on factors such as svanis
        self.pryl_mod(config)
        # Get the total modPris and inPris from all the prylar
        self.get_pris()

        self.personalRakna(config)
        self.marginalRakna(config)
        self.output()

    def checkPrylar(self, prylar):
        try:
            if self.iData["antalPrylar"]:
                try:
                    int(self.iData["antalPrylar"])
                    self.iData["antalPrylar"] = [self.iData["antalPrylar"]]
                except ValueError:
                    self.iData["antalPrylar"] = self.iData["antalPrylar"].split(",")
            if self.iData["antalPrylar"] is not None:
                antal = True
            else:
                antal = False
        except KeyError:
            antal = False
        i = 0
        for pryl in self.iData["extraPrylar"]:
            if antal:

                try:
                    for j in range(int(self.iData["antalPrylar"][i])):
                        self.preGigPrylar.append({pryl: prylar[pryl]})
                except IndexError:
                    self.preGigPrylar.append({pryl: prylar[pryl]})
            else:
                # Add pryl from prylar to prylList
                self.preGigPrylar.append({pryl: prylar[pryl]})
            i += 1

    def check_paket(self):
        try:
            if self.iData["antalPaket"]:

                try:
                    int(self.iData["antalPaket"])
                    self.iData["antalPaket"] = [self.iData["antalPaket"]]
                except ValueError:
                    self.iData["antalPaket"] = self.iData["antalPaket"].split(",")
            if self.iData["antalPaket"] is not None:
                antal = True
            else:
                antal = False
        except KeyError:
            antal = False

        for paket in self.iData["prylPaket"]:
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
                        for j in range(int(self.iData["antalPaket"][i])):
                            self.preGigPrylar.append({pryl: self.paketen[paket]["prylar"][pryl]})
                    except IndexError:
                        self.preGigPrylar.append({pryl: self.paketen[paket]["prylar"][pryl]})
                else:
                    # Add pryl from paket to prylList
                    self.preGigPrylar.append({pryl: self.paketen[paket]["prylar"][pryl]})
            i += 1

    def count_them(self):
        # print(self.preGigPrylar, "hi")
        i = 0
        for pryl in self.preGigPrylar:
            for key in pryl:
                # print(i, key, "\n", list(self.gigPrylar.keys()), "\n")
                if key in list(self.gigPrylar.keys()):
                    self.gigPrylar[key]["amount"] += copy.deepcopy(self.preGigPrylar[i][key]["amount"])
                    # print("hi", key, self.gigPrylar[key]["amount"])
                else:
                    self.gigPrylar.update(copy.deepcopy(self.preGigPrylar[i]))
            i += 1
        # print(self.gigPrylar)

    def pryl_mod(self, config):

        for pryl in self.gigPrylar:
            self.inPris += self.gigPrylar[pryl]["inPris"]

            # Make new pryl attribute "mod" where price modifications happen
            self.gigPrylar[pryl]["mod"] = copy.deepcopy(self.gigPrylar[pryl]["pris"])
            modPryl = self.gigPrylar[pryl]["mod"]

            # Mult price by amount of pryl
            modPryl *= self.gigPrylar[pryl]["amount"]

            # If svanis, mult by svanis multi
            if self.svanis:
                modPryl *= config["svanisMulti"]

            self.gigPrylar[pryl]["dagarMod"] = self.dagar(config, modPryl)

            self.gigPrylar[pryl]["mod"] = modPryl

    def get_pris(self):
        for pryl in self.gigPrylar:
            self.inPris += self.gigPrylar[pryl]["inPris"]
            self.prylPris += self.gigPrylar[pryl]["dagarMod"]
            self.pris += self.gigPrylar[pryl]["dagarMod"]
        self.prylKostnad = self.prylPris * 0.4

    def dagar(self, config, pris):
        dagar = self.iData["dagar"]
        dagTvaMulti = config["dagTvåMulti"]
        dagTreMulti = config["dagTreMulti"]
        tempPris = copy.deepcopy(pris)
        if type(dagar) is dict:
            dagar = 1
            self.iData["dagar"] = 1
            print(dagar)
        if dagar < 1:
            tempPris = 0
        elif dagar >= 2:
            tempPris *= (1 + dagTvaMulti)
        if dagar >= 3:
            tempPris += pris * dagTreMulti * (dagar - 2)
        return tempPris

    def personalRakna(self, config):
        self.timPeng = math.floor(config["levandeVideoLön"] * (config["lönJustering"]) / 10) * 10

        self.gigTimmar = round(int(self.iData["dagLängd"]["name"]) * self.personal * self.iData["dagar"])

        if self.iData["specialRigg"]:
            self.riggTimmar = self.iData["riggTimmar"]
        else:
            self.riggTimmar = math.floor(self.pris * config["andelRiggTimmar"])

        self.projektTimmar = math.ceil((self.gigTimmar + self.riggTimmar) * config["projektTid"])

        if self.svanis:
            self.restid = 0
        else:
            self.restid = self.personal * self.iData["dagar"] * config["restid"]

        self.timBudget = self.gigTimmar + self.riggTimmar + self.projektTimmar + self.restid
        # Timmar gånger peng per timme
        self.personalPris = self.timBudget * self.timPeng

        self.personalKostnad = self.timBudget * config["levandeVideoLön"]
        self.pris += self.personalPris
        # print(self.timBudget, self.restid, self.projektTimmar, self.gigTimmar, self.riggTimmar, self.svanis)

    def marginalRakna(self, config):
        try:
            if self.iData["hyrKostnad"] is None:
                self.iData["hyrKostnad"] = 0
        except KeyError:
            self.iData["hyrKostnad"] = 0

        self.hyrPris = self.iData["hyrKostnad"] * (1 + config["hyrMulti"])
        self.kostnad = self.prylKostnad + self.personalKostnad + self.iData["hyrKostnad"]
        self.pris += self.hyrPris

        # Prevent div by 0
        if self.personalPris != 0:
            self.personalMarginal = (self.personalPris - self.personalKostnad) / self.personalPris
        else:
            self.personalMarginal = 0

        # Prevent div by 0
        if self.prylPris != 0:
            self.prylMarginal = (self.prylPris - self.prylKostnad) / self.prylPris
        else:
            self.prylMarginal = 0
        # TODO
        #  Add resekostnader
        #  F19, F20 i arket

        self.slitKostnad = self.prylPris * config["prylSlit"]

        self.avkastning = round(
            self.pris - self.slitKostnad - self.personalKostnad - self.iData["hyrKostnad"]
        )

        self.marginal = round(
            self.avkastning / (
                    self.pris - self.iData["hyrKostnad"] * (1 - config["hyrMulti"] * config["hyrMarginal"])
            ) * 10000
        ) / 100

    def output(self):
        print(f"Pryl: {self.prylPris}")
        print(f"Personal: {self.personalPris}")
        print(f"Total: {self.pris}")
        print(f"Avkastning: {self.avkastning}")

        if self.marginal > 65:
            print(f"Marginal: {bcolors.OKGREEN + str(self.marginal)}%{bcolors.ENDC}")
        else:
            print(f"Marginal: {bcolors.FAIL + str(self.marginal)}%{bcolors.ENDC}")

        self.gigPrylar = dict(sorted(self.gigPrylar.items(), key=lambda item: -1 * item[1]["amount"]))

        for pryl in self.gigPrylar:
            print(
                f"\t{self.gigPrylar[pryl]['amount']}st {pryl} - {self.gigPrylar[pryl]['mod']} kr ",
                f"- {self.gigPrylar[pryl]['dagarMod']} kr pga {self.iData['dagar']} dagar")

        paketIdList = []
        prylIdList = []

        # print(self.paketen)
        try:
            for paket in self.iData["prylPaket"]:
                paketIdList.append(self.paketen[paket]["id"])
        except KeyError:
            pass

        try:
            for pryl in self.iData["extraPrylar"]:
                prylIdList.append(self.prylar[pryl]["id"])

        except KeyError:
            pass
        antalString = ""

        try:
            for antal in self.iData["antalPrylar"]:
                if antalString == "":
                    antalString += antal
                else:
                    antalString += "," + antal
        except (KeyError, TypeError):
            pass
        antalPaketString = ""
        try:
            for antal in self.iData["antalPaket"]:
                if antalPaketString == "":
                    antalPaketString += antal
                else:
                    antalPaketString += "," + antal
        except (KeyError, TypeError):
            pass
        if self.update:
            recID = self.iData["uppdateraProjekt"][0]["id"]
        else:
            recID = None
        output = {
            "Gig namn": self.name,
            "Pris": self.pris,
            "Marginal": str(self.marginal) + "%",
            "marginalSecret": self.marginal,
            "Personal": self.personal,
            "Projekt timmar": self.gigTimmar,
            "Rigg timmar": self.riggTimmar,
            "Totalt timmar": self.timBudget,
            "Pryl pris": self.prylPris,
            "prylPaket": paketIdList,
            "extraPrylar": prylIdList,
            "antalPrylar": antalString,
            "antalPaket": antalPaketString,
            "update": self.update,
            "recID": recID
        }

        # print(output)
        requests.post(
            url="https://hooks.airtable.com/workflows/v1/genericWebhook/appG1QEArAVGABdjm/wflcP4lYCTDwmSs4g"
                "/wtrzRoN98kiDzdU05",
            json=output)
        # self.outputTable.create(output)


@app.route("/airtable", methods=["POST"])
def fuck_yeah():
    iData = request.json
    # Load all the important data
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    with open('paket.json', 'r', encoding='utf-8') as f:
        paket = json.load(f)
    with open('prylar.json', 'r', encoding='utf-8') as f:
        prylar = json.load(f)
    iDataName = list(iData.keys())[-1]

    gig(iData, config, prylar, paket, iDataName)
    return "<3"


@app.route("/", methods=["GET"])
def the_basics():
    return "Hello <3"


@app.route("/start", methods=["POST", "GET"])
def start():
    iData = request.json["Input data"]
    # Clean junk from data
    try:
        if request.json["key"]:
            pass
        iDataName = request.json["key"]
    except KeyError:
        iDataName = list(iData.keys())[-1]

    for key in iData:
        prylList = []
        paketList = []
        try:
            i = 0
            for pryl in iData[key]["extraPrylar"]:
                pryl.pop("id", None)
                prylList.append(iData[key]["extraPrylar"][i]["name"])
                i += 1
            iData[key]["extraPrylar"] = prylList
        except (KeyError, AttributeError):
            pass
        try:
            i = 0
            for paket in iData[key]["prylPaket"]:
                paket.pop("id", None)
                paketList.append(iData[key]["prylPaket"][i]["name"])
                i += 1
            iData[key]["prylPaket"] = paketList
        except (KeyError, AttributeError):
            pass

    # Save data just because
    with open('input.json', 'w', encoding='utf-8') as f:
        json.dump(iData, f, ensure_ascii=False, indent=2)

    # Load all the important data
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    with open('paket.json', 'r', encoding='utf-8') as f:
        paket = json.load(f)
    with open('prylar.json', 'r', encoding='utf-8') as f:
        prylar = json.load(f)

    gig(iData, config, prylar, paket, iDataName)

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
    prylDict = {}
    for prylNamn in prylarna:
        pryl = prylOb(inPris=prylarna[prylNamn]["pris"], name=prylNamn,
                      livsLängd=int(prylarna[prylNamn]["livsLängd"]["name"]))
        pryl.rounding(config)
        prylDict.update(pryl.dict_make())

    paketen = request.json["Pryl Paket"]
    paketDict = {}
    for paket in paketen:
        lista = []
        paketen[paket]["name"] = paket
        try:
            for pryl in paketen[paket]["paketPrylar"]:
                lista.append(pryl["name"])

            paketen[paket]["paketPrylar"] = lista
        except KeyError:
            pass
        paketen[paket]["paketDict"] = paketDict
        paket = paketOb(prylDict, paketen[paket])
        paketDict.update(paket.dictMake())

    prylarTable = Table(api_key, base_id, "Prylar")
    paketTable = Table(api_key, base_id, "Pryl Paket")
    for record in prylarTable.all():
        prylDict[str(record["fields"]["Pryl Namn"])].update({"id": record["id"]})
    for record in paketTable.all():
        paketDict[str(record["fields"]["Paket Namn"])].update({"id": record["id"]})

    # Save data to file
    with open('prylar.json', 'w', encoding='utf-8') as f:
        json.dump(prylDict, f, ensure_ascii=False, indent=2)

    with open('config.json', 'w', encoding='utf-8') as f:
        json.dump(request.json["Config"], f, ensure_ascii=False, indent=2)
    with open('paket.json', 'w', encoding='utf-8') as f:
        json.dump(paketDict, f, ensure_ascii=False, indent=2)
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
