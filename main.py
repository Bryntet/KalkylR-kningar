import os
import time
from pyairtable import Table
import re
# import random
from threading import Thread
import copy
import pandas as pd
import math
from flask import Flask, request
import json

# pd.set_option('display.max_colwidth', None)
pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)

# pd.set_option('display.width', 150)

api_key = os.environ['api_key']

app = Flask(  # Create a flask app
    __name__,
    template_folder='templates',  # Name of html file folder
    static_folder='static'  # Name of directory for static files
)

try:
    with open('config.json', 'r') as f:
        config = json.load(f)
except OSError as e:
    print(e)


class prylOb:
    def __init__(self, config, **kwargs):
        # Gets all attributes provided and adds them to self
        # Current args: name, inPris, pris
        for argName, value in kwargs.items():
            self.__dict__.update({argName: value})
        self.amount = 1

    def rounding(self, config):
        # Convert to lower price as a percentage of the buy price
        self.pris = math.floor((float(self.inPris) * config["prylKostnadMulti"]) / 10) * 10

    def dict_make(self):
        temp_dict = vars(self)
        out_dict = {temp_dict["name"]: temp_dict}
        out_dict[temp_dict["name"]].pop('name', None)
        return out_dict

    def amount_calc(self, ind, antal_av_pryl):
        self.amount = antal_av_pryl[ind]


class paketOb:
    def __init__(self, config, prylar, args):
        # Gets all kwargs provided and adds them to self
        # Current kwargs:
        # print(args, "test")
        for argName, value in args.items():
            # print(argName, value)
            self.__dict__.update({argName: value})

        self.pris = 0
        self.prylar = {}
        # print(prylar)
        try:
            if self.paketIPrylPaket:
                for paket in self.paketIPrylPaket:
                    # print(paket, self.paketDict[paket["name"]])
                    for pryl in self.paketDict[paket["name"]]["prylar"]:
                        if pryl in self.prylar.keys():
                            self.prylar[pryl]["amount"] += 1
                        else:
                            self.prylar[pryl] = copy.deepcopy(self.paketDict[paket["name"]]["prylar"][pryl])


        except AttributeError:

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
    def __init__(self, iData, config, prylar, paketen, name):
        self.slitKostnad = None
        self.marginal = None
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
        self.gigPrylar = {}
        self.preGigPrylar = []
        self.name = name
        self.iData = iData[self.name]
        self.prylPris = 0
        self.pris = 0
        self.inPris = 0
        try:
            self.personal = self.iData["extraPersonal"]
        except KeyError:
            self.personal = 0
        try:
            if iData["svanis"]:
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
            self.check_paket(paketen)
        except KeyError:
            pass
        # Add accurate count to all prylar and compile them from list to dict
        self.count_them()
        # Modify prylPris based on factors such as svanis
        self.pryl_mod(config)
        # Get the total modPris and inPris from all the prylar
        self.get_pris()
        self.personalRakna(config)
        print(f"Total: {self.pris}")
        print(f"Total inköp: {self.inPris}")
        print(f"Personal kostnad: {self.personalPris}")
        print(f"Total: {self.pris}")
        self.gigPrylar = dict(sorted(self.gigPrylar.items(), key=lambda item: -1 * item[1]["amount"]))
        for pryl in self.gigPrylar:
            print(
                f"\t{self.gigPrylar[pryl]['amount']}st {pryl} - {self.gigPrylar[pryl]['mod']} kr - {self.gigPrylar[pryl]['dagarMod']} kr pga {self.iData['dagar']} dagar")

    def checkPrylar(self, prylar):
        try:
            if self.iData["antalPrylar"]:
                try:
                    int(self.iData["antalPrylar"])
                    self.iData["antalPrylar"] = [self.iData["antalPrylar"]]
                except ValueError:
                    self.iData["antalPrylar"] = self.iData["antalPrylar"].split(",")

            antal = True

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

    def check_paket(self, paketen):
        try:
            if self.iData["antalPaket"]:

                try:
                    int(self.iData["antalPaket"])
                    self.iData["antalPaket"] = [self.iData["antalPaket"]]
                except ValueError:
                    self.iData["antalPaket"] = self.iData["antalPaket"].split(",")
            antal = True

        except KeyError:
            antal = False
        for paket in self.iData["prylPaket"]:
            # Check svanis
            try:
                if paketen[paket]["svanis"]:
                    self.svanis = True
            except KeyError:
                pass
            # Get personal
            try:
                if paketen[paket]["Personal"]:
                    self.personal += paketen[paket]["Personal"]
            except KeyError:
                pass
            i = 0

            for pryl in paketen[paket]["prylar"]:
                if antal:
                    try:
                        for j in range(int(self.iData["antalPaket"][i])):
                            self.preGigPrylar.append({pryl: paketen[paket]["prylar"][pryl]})
                    except IndexError:
                        self.preGigPrylar.append({pryl: paketen[paket]["prylar"][pryl]})
                else:
                    # Add pryl from paket to prylList
                    self.preGigPrylar.append({pryl: paketen[paket]["prylar"][pryl]})
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
            print(modPryl)

    def get_pris(self):
        for pryl in self.gigPrylar:
            self.inPris += self.gigPrylar[pryl]["inPris"]
            self.pris += self.gigPrylar[pryl]["dagarMod"]

    def dagar(self, config, pris):
        dagar = self.iData["dagar"]
        dagTvaMulti = config["dagTvåMulti"]
        dagTreMulti = config["dagTreMulti"]
        tempPris = copy.deepcopy(pris)

        if dagar < 1:
            tempPris = 0
        elif dagar >= 2:
            tempPris *= (1 + dagTvaMulti)
        if dagar >= 3:
            tempPris += pris * config["dagTreMulti"] * (dagar - 2)
        return tempPris

    def personalRakna(self, config):
        self.timPeng = math.floor(config["levandeVideoLön"] * (config["lönJustering"]) / 10) * 10

        self.gigTimmar = round(self.iData["dagLängd"] * self.personal * self.iData["dagar"])

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

    def marginal(self, config):
        self.hyrPris = self.iData["hyrKostnad"] * (1 + config["hyrMulti"])


@app.route("/", methods=["GET"])
def the_basics():
    return "Hello <3"


@app.route("/start", methods=["POST"])
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
        except KeyError:
            pass
        try:
            i = 0
            for paket in iData[key]["prylPaket"]:
                paket.pop("id", None)
                paketList.append(iData[key]["prylPaket"][i]["name"])
                i += 1
            iData[key]["prylPaket"] = paketList
        except KeyError:
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

    test = gig(iData, config, prylar, paket, iDataName)

    return "<3"


data = ["test0", "test1"]


# Route for updating the configurables
@app.route("/update/config", methods=["POST"])
def get_prylar():
    # Make the key of configs go directly to the value
    for configurable in request.json["Config"]:
        request.json["Config"][configurable] = request.json["Config"][configurable]["Siffra i decimal"]

    config = request.json["Config"]

    # Format prylar better
    prylarna = request.json["Prylar"]
    prylDict = {}
    for prylNamn in prylarna:
        pryl = prylOb(config, inPris=prylarna[prylNamn]["pris"], name=prylNamn)
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
        paket = paketOb(config, prylDict, paketen[paket])
        paketDict.update(paket.dictMake())
    # print(paketDict)

    # Save data to file
    with open('prylar.json', 'w', encoding='utf-8') as f:
        json.dump(prylDict, f, ensure_ascii=False, indent=2)

    with open('config.json', 'w', encoding='utf-8') as f:
        json.dump(request.json["Config"], f, ensure_ascii=False, indent=2)
    with open('paket.json', 'w', encoding='utf-8') as f:
        json.dump(paketDict, f, ensure_ascii=False, indent=2)

    for ind in range(len(paketen)):
        pris = 0
        # print(paketen[ind]["prylar"][])
        """
    for pryl in paket.Prylar:
      print(pryl)
      pris += prylarDF[pryl["name"]].pris
    print(pris)
    paket.pris = pris
    """
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


def raknaMarginal(config, prylInfo, personalInfo, inputData):
    hyrMulti = config["hyrMulti"]
    hyrKostnad = inputData["hyrKostnad"]
    prylPris = prylInfo["prylPris"]
    prylKostnad = prylInfo["prylKostnad"]
    personalPris = personalInfo["personalPris"]
    personalKostnad = personalInfo["personalKostnad"]
    hyrPris = hyrKostnad * (1 + hyrMulti)
    hyrMarginal = config["hyrMarginal"]
    helPris = prylPris + personalPris + hyrPris

    helKostnad = prylKostnad + personalKostnad + hyrKostnad

    try:
        personalMarginal = (personalPris - personalKostnad) / personalPris
    except ZeroDivisionError:
        personalMarginal = 0
    try:
        prylMarginal = (prylPris - prylKostnad) / prylPris
    except ZeroDivisionError:
        prylMarginal = 0

    print(prylInfo, personalInfo)

    avkastning = helPris - prylKostnad - personalKostnad - hyrKostnad
    marginal = avkastning / (helPris - hyrKostnad * (1 - hyrMulti * hyrMarginal))

    marginalInfo = {
        "Helpris": helPris,
        "Helkostnad": helKostnad,
        "Personal Marginal": personalMarginal,
        "Pryl Marginal": prylMarginal,
        "Marginal": marginal,
        "Avkastning": avkastning,
        "HyrPris": hyrPris
    }
    return marginalInfo


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
baseName = "appG1QEArAVGABdjm"
inputTable = Table(api_key, baseName, 'Input data')
paketTable = Table(api_key, baseName, 'Pryl Paket')
prylTable = Table(api_key, baseName, 'Prylar')
outputTable = Table(api_key, baseName, 'Output table')
configTable = Table(api_key, baseName, 'Config')
isItRunning = False


def everything():
    global isItRunning, prylarUrPaket, outputId
    print("hello")
    global inputData
    global areWeRunning
    global svanis
    global prylFields
    global inputFields
    personal = 0
    allPrylar = prylTable.all(fields=prylFields)
    allPaket = paketTable.all(fields=paketFields)
    inputTableList = inputTable.all(fields=inputFields)

    # print(allPrylar)
    outputTableList = outputTable.all()

    start = time.time()

    configTableList = configTable.all()
    try:

        inputData = inputTableList[1]["fields"]
        print(inputData)
        # uppdatera översta "Input Data" table, och sedan ta bort det nya som var underst

        # inputTable.update(inputTableList[0]["id"], inputData)
        # inputTable.delete(inputTableList[1]["id"])
        inputTableSaveOriginal = copy.deepcopy(inputData)
        # print("hello!", inputTableSaveOriginal)

        try:
            if inputTableSaveOriginal["prylPaket"] != list:
                inputTableSaveOriginal["prylPaket"] = [inputTableSaveOriginal["prylPaket"]]
        except KeyError:
            pass

        dontRunAnyMore = False
    except IndexError as e:
        print(e)
        dontRunAnyMore = True
        isItRunning = False
        return
    if dontRunAnyMore != True:
        print("Actually running")
        prylLista = []
        # Fixa prylar från paket ids + antal paket som används
        try:
            try:
                # print(inputData)
                inputData["antalPaket"] += ","
                inputData["antalPaket"] = inputData["antalPaket"].split(",")
                if inputData["antalPaket"][-1] == '':
                    del inputData["antalPaket"][-1]
                for i in range(0, len(inputData["antalPaket"])):
                    startILoop = time.time()
                    for j in range(0, int(inputData["antalPaket"][i])):
                        startILoopLoop = time.time()
                        # print(inputData["prylPaket"])
                        paketId = inputData["prylPaket"][i]
                        prylarUrPaket = skaffaPrylarUrPaket(paketId, allPrylar, allPaket, paket=True)
                        personal += prylarUrPaket["personal"]
                        # print(time.time() - startILoopLoop)

                        for pryl in prylarUrPaket["prylLista"]:
                            prylLista.append(pryl)
                    # print(time.time() - startILoop)
                # print(prylLista)
            except KeyError:
                for paketId in inputData["prylPaket"]:
                    prylarUrPaket = skaffaPrylarUrPaket(paketId, allPrylar, allPaket, paket=True)
                    personal += prylarUrPaket["personal"]
                    # print(prylarUrPaket)
                    for pryl in prylarUrPaket["prylLista"]:
                        prylLista.append(pryl)
                    # print(prylLista)
        except KeyError:
            pass
        # print("hello")
        # Fixa prylar från IDs
        try:
            prylarUrPrylId = skaffaPrylarUrPaket(0, allPrylar, allPaket, False, prylar=inputData["extraPrylar"])
            for pryl in prylarUrPrylId["prylLista"]:
                prylLista.append(pryl)

        except KeyError:
            pass
        # print(prylLista)
        middle = time.time()
        inputData["prylar"] = prylLista
        try:
            inputData["svanis"] = prylarUrPaket["svanis"]
            inputData["personal"] = personal + inputData["extraPersonal"]
        except NameError:
            inputData["svanis"] = False
            inputData["personal"] = inputData["extraPersonal"]

        # fyfan

        # inputData.update(prylarOchPersonalAvPaket(inputData))

        # inputData["prylar"] = fixaPrylarna(inputData)
        # print(inputData["prylar"])
        for record in configTableList:
            config[record["fields"]["Name"]] = record["fields"]["Siffra i decimal"]
        print("Running the kalkylark\n")
        # print(inputData["prylar"], "\n")

        prylInfo = raknaPryl(config, inputData)
        personalInfo = raknaPersonal(config, prylInfo, inputData)
        marginalInfo = raknaMarginal(config, prylInfo, personalInfo, inputData)
        kalkylOutput = {}
        kalkylOutput["Gig Namn"] = inputData["gigNamn"]
        kalkylOutput["Helpris"] = marginalInfo["Helpris"]
        kalkylOutput["Marginal"] = marginalInfo["Marginal"]
        kalkylOutput["Personal"] = inputData["personal"]
        kalkylOutput["Projekttimmar"] = personalInfo["projektTimmar"]
        kalkylOutput["Riggtimmar"] = personalInfo["riggTimmar"]
        kalkylOutput["Totalt timmar"] = personalInfo["timBudget"]
        kalkylOutput["Prylpris"] = prylInfo["prylPris"]
        # print(kalkylOutput)

        kalkylOutput["debug"] = "`" + str([config, inputData, prylInfo, personalInfo, marginalInfo]) + "`"
        # print(kalkylOutput["debug"])
        # print(config, inputData, prylInfo, personalInfo, marginalInfo)
        print("hello!", inputTableSaveOriginal)
        try:
            kalkylOutput["prylPaket"] = inputTableSaveOriginal["prylPaket"][0]
        except KeyError:
            pass
        try:
            kalkylOutput["extraPrylar"] = inputTableSaveOriginal["extraPrylar"][0]
        except KeyError:
            pass
        try:
            kalkylOutput["antalPaket"] = inputTableSaveOriginal["antalPaket"]
        except KeyError:
            pass
        try:
            kalkylOutput["antalPrylar"] = inputTableSaveOriginal["antalPrylar"]
        except KeyError:
            pass
        try:
            kalkylOutput["dagLängd"] = inputTableSaveOriginal["dagLängd"]
        except KeyError:
            pass
        try:
            kalkylOutput["dagar"] = inputTableSaveOriginal["dagar"]
        except KeyError:
            pass
        try:
            kalkylOutput["extraPersonal"] = inputTableSaveOriginal["extraPersonal"]
        except KeyError:
            pass
        try:
            kalkylOutput["hyrKostnad"] = inputTableSaveOriginal["hyrKostnad"]
        except KeyError:
            pass
        duplicateOrNot = False

        for record in outputTableList:
            # print(record)
            if record["fields"]["Gig Namn"] == inputData["gigNamn"]:
                outputId = record["id"]
                outputTable.update(outputId, kalkylOutput, replace=True)
                # print(outputId, "hi!!")
                duplicateOrNot = True
        if duplicateOrNot == False:
            print(kalkylOutput)
            outputId = outputTable.create(kalkylOutput)
            outputId = re.findall(r".*{'id': '(\w+)', 'fields': {'Gig Namn': '.*', 'Helpris'", str(outputId))[0]
            print(outputId)
        svanis = False
        stop = time.time()
        print("The time of the run:", stop - start, "\n Time to middle was: ", middle - start)

        projectTable = Table(api_key, baseName, 'Projekt')
        projectTableList = projectTable.all()
        projectExists = False
        print(projectTableList)
        try:
            for record in projectTableList:
                if record["fields"]["Name"] == inputData["projekt"] and projectExists != True:
                    existingLinks = record["fields"]["Leveranser"]
                    projectTable.update(record["id"]["fields"]["Leveranser"], existingLinks.append(outputId))
                    projectExists = True
        except KeyError:
            projectExists = False
        if not projectExists:
            outputId = [outputId]
            projectTable.create({"Name": inputData["projekt"], "Leveranser": outputId})
        isItRunning = False
        Thread(target=everything).stop()


server()
