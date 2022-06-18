import os
import time
from pyairtable import Table
import re
import random
from threading import Thread
import copy
import pandas as pd
import math
from flask import Flask, request
import json
#pd.set_option('display.max_colwidth', None)
pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)

#pd.set_option('display.width', 150)

api_key = os.environ['api_key']

app = Flask(  # Create a flask app
	__name__,
	template_folder='templates',  # Name of html file folder
	static_folder='static'  # Name of directory for static files
)
try:
  with open('config.json', 'r') as f:
    config = json.load(f)
except Exception:
  print(Exception)


class prylOb:
  def __init__(self, config, **kwargs):
    #Gets all attributes provided and adds them to self
    #Current args: name, inPris, pris
    for argName, value in kwargs.items():
      self.__dict__.update({argName:value})
    self.amount = 1
  def rounding(self, config):
    #Convert to lower price as a percentage of the buy price
    self.pris = math.floor((float(self.inPris)*config["prylKostnadMulti"])/10)*10
    
  def dictMake(self):
    tempDict = vars(self)
    outDict = {tempDict["name"]:tempDict}
    outDict[tempDict["name"]].pop('name', None)
    return outDict
  def amountCalc(self, ind, antalAvPryl):
    self.amount = antalAvPryl[ind]
  
class paketOb:
  def __init__(self, config, prylar, args):
    #Gets all kwargs provided and adds them to self
    #Current kwargs:
    #print(args, "test")
    for argName, value in args.items():
      #print(argName, value)
      self.__dict__.update({argName:value})
      
    
    
    self.pris = 0
    self.prylar = {}
    #print(prylar)
    try:
      if self.paketIPrylPaket:
        for paket in self.paketIPrylPaket:
          print(paket, self.paketDict[paket["name"]])
          for pryl in self.paketDict[paket["name"]]["prylar"]:
            if pryl in self.prylar.keys():
              self.prylar[pryl]["amount"] += 1
            else:
              self.prylar[pryl] = copy.deepcopy(self.paketDict[paket["name"]]["prylar"][pryl])
          
        
    except AttributeError:
      
      try:
        #Add pryl objects to self list of all prylar in paket
        self.antalAvPryl = str(self.antalAvPryl).split(",")
        for pryl in self.paketPrylar:
          
          ind = self.paketPrylar.index(pryl)
          
          self.prylar.update({pryl:copy.deepcopy(prylar[pryl])})
          self.prylar[pryl]["amount"] = int(self.antalAvPryl[ind])
          
        #print(self.prylar, "\n\n\n\n")
      except AttributeError:
        pass
    #Set total price of prylar in paket
    for pryl in self.prylar:
      self.pris += (self.prylar[pryl]["pris"]*self.prylar[pryl]["amount"])
      
      

    
  def dictMake(self):
    tempDict = vars(self)
    outDict = {tempDict["name"]:tempDict}
    outDict[tempDict["name"]].pop('paketPrylar', None)
    bok = {}
    try:
      for dubbelPaket in outDict[tempDict["name"]]["paketIPrylPaket"][0]:
        bok.update({"name":outDict[tempDict["name"]]["paketIPrylPaket"][0][dubbelPaket]})
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
    self.gigPrylar = {}
    self.preGigPrylar = []
    self.name = name
    self.iData = iData[self.name]
    try:
      self.checkPrylar(prylar)
    except KeyError:
      pass
    try:
      self.checkPaket(paketen)
    except KeyError:
      pass
    #print(self.preGigPrylar, "hi")
    self.countThem()
    self.prisFunc()
    self.rounding(config)
    print(f"Total: {self.pris}")
    print(f"Total inköp: {self.inPris}")
    for pryl in self.gigPrylar:
      print(f"\t{self.gigPrylar[pryl]['amount']}st {pryl} - {self.gigPrylar[pryl]['amount']*self.gigPrylar[pryl]['pris']} kr")

  def checkPrylar(self, prylar):
    for pryl in self.iData["extraPrylar"]:
      #print(pryl)
      self.preGigPrylar.append({pryl:prylar[pryl]})
  
  def checkPaket(self, paketen):
    for paket in self.iData["prylPaket"]:
      for pryl in paketen[paket]["prylar"]:
        
        #print(pryl)
        self.preGigPrylar.append({pryl:paketen[paket]["prylar"][pryl]})

  def countThem(self):
    #print(self.preGigPrylar, "hi")
    i = 0
    for pryl in self.preGigPrylar:
      for key in pryl:
        #print(i, key, "\n", list(self.gigPrylar.keys()), "\n")
        if key in list(self.gigPrylar.keys()):
          self.gigPrylar[key]["amount"] += copy.deepcopy(self.preGigPrylar[i][key]["amount"])
          #print("hi", key, self.gigPrylar[key]["amount"])
        else:
          self.gigPrylar.update(copy.deepcopy(self.preGigPrylar[i]))
      i += 1
    #print(self.gigPrylar)
    
  def prisFunc(self):
    self.pris = 0
    self.inPris = 0
    for pryl in self.gigPrylar:
      #print(pryl)
      self.inPris += self.gigPrylar[pryl]["inPris"]*self.gigPrylar[pryl]["amount"]
    
  def rounding(self, config):
    self.pris = math.floor((float(self.inPris)*config["prylKostnadMulti"])/10)*10
@app.route("/", methods=["GET"])
def theBasics():
  return "Hello <3"

@app.route("/start", methods=["POST"])
def start():
  iData = request.json["Input data"]
  #Clean junk from data
  try:
    if request.json["key"]:
      key = request.json["key"]
  except KeyError:
    key = list(iData.keys())[-1]
  iDataName = key
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
  
  #Save data just because
  with open('input.json', 'w', encoding='utf-8') as f:
    json.dump(iData, f, ensure_ascii=False, indent=2)

  #Load all the important data
  with open('config.json', 'r') as f:
    config = json.load(f)
  with open('paket.json', 'r') as f:
    paket = json.load(f)
  with open('prylar.json', 'r') as f:
    prylar = json.load(f)

  test = gig(iData, config, prylar, paket, iDataName)

  
  return "<3"
  
data = ["test0", "test1"]

#Route for updating the configurables
@app.route("/update/config", methods=["POST"]) 
def getPrylar():

  #Make the key of configs go directly to the value
  for configurable in request.json["Config"]:
    request.json["Config"][configurable] = request.json["Config"][configurable]["Siffra i decimal"]


  config = request.json["Config"]
  
  #Format prylar better
  prylarna = request.json["Prylar"]
  prylDict = {}
  for prylNamn in prylarna:
    pryl = prylOb(config, inPris=prylarna[prylNamn]["pris"], name=prylNamn)
    pryl.rounding(config)
    prylDict.update(pryl.dictMake())

  
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
  print(paketDict)
  
  #Save data to file
  with open('prylar.json', 'w', encoding='utf-8') as f:
    json.dump(prylDict, f, ensure_ascii=False, indent=2)
  

  with open('config.json', 'w', encoding='utf-8') as f:
    json.dump(request.json["Config"], f, ensure_ascii=False, indent=2)
  with open('paket.json', 'w', encoding='utf-8') as f:
    json.dump(paketDict, f, ensure_ascii=False, indent=2)

  
  
  for ind in range(len(paketen)):
    pris = 0
    #print(paketen[ind]["prylar"][])
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

def raknaPersonal(config, prylInfo, inputData):
  levandeVideoLön = config["levandeVideoLön"]
  dagLängd = inputData["dagLängd"]
  dagar = inputData["dagar"]
  andelRiggTimmar = config["andelRiggTimmar"]
  prylPris = prylInfo["prylPris"]
  lönMarginal = config["lönMarginal"] + 1
  personal = inputData["personal"]

  if personal > 0:
    
    timPeng = math.floor(levandeVideoLön * (lönMarginal)/10)*10
    
    gigTimmar = round(dagLängd*personal*dagar)
    
    if inputData["specialRigg"] == True:
      riggTimmar = inputData["riggTimmar"]
    else:
      riggTimmar = round(prylPris*andelRiggTimmar)
    
    print(riggTimmar)
    projektTimmar = round((gigTimmar+riggTimmar) * .3)
    if inputData["svanis"] == True:
      restid = personal * 2
    else:
      restid = 0
    
    timBudget = gigTimmar + riggTimmar + projektTimmar + restid
    
    personalPris = timBudget * timPeng

    personalKostnad = timBudget * levandeVideoLön
    personalInfo = {
      "timBudget": timBudget,
      "personalKostnad": personalKostnad,
      "projektTimmar": projektTimmar,
      "riggTimmar": riggTimmar,
      "gigTimmar": gigTimmar,
      "timPeng": timPeng,
      "personalPris": personalPris,
      "restid": restid,
      "personal": personal
    }
  else:
    personalInfo = {
      "timBudget": 0,
      "personalKostnad": 0,
      "projektTimmar": 0,
      "riggTimmar": 0,
      "gigTimmar": 0,
      "timPeng": 0,
      "personalPris": 0,
      "restid": 0,
      "personal": 0
    }
  return personalInfo

def raknaPryl(config, inputData):
  print("in raknaPryl", inputData["prylar"])
  #Pris = Pris för kund
  #Kostnad = Kostnad för levande video kooperativet!
  prylPris = 0
  dagar = inputData["dagar"]
  prylKostnadMulti = config["prylKostnadMulti"]
  dagTvåMulti = config["dagTvåMulti"]



  if inputData["svanis"] == True:
    prylPris *= config["svanisMulti"]

  if dagar < 1:
    prylPris = 0
  elif dagar == 2:
    prylPris *= 1 + dagTvåMulti
  elif dagar >= 3:
    prylPris = prylPris*(1 + dagTvåMulti) + prylPris*config["dagTreMulti"]*(dagar-2)

  
  prylKostnad = prylPris * .4
  prylInfo = {
    "prylPris": prylPris,
    "prylKostnad": prylKostnad
  }
  return prylInfo


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
    "Helpris":helPris, 
    "Helkostnad": helKostnad, 
    "Personal Marginal": personalMarginal,
    "Pryl Marginal": prylMarginal, 
    "Marginal": marginal, 
    "Avkastning": avkastning,
    "HyrPris": hyrPris
  }
  return marginalInfo



#prylLista = prylarOchPersonalAvPaket({"prylPaket": ["id0"]})

#print(fixaPrylarna({"extraPrylar": '1 "id0"', "prylLista": prylLista}))



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






def skaffaPrylarUrPaket(paketId, prylTableList, paketTableList, personal = 0, paket = True, svanis = False, **prylar):
  #print("in skaffaPrylarUrPaket")
  global inputData
  #print(prylar)
  #print(prylTableList)
  if paket == True:
    for record in paketTableList:
      #print(record["id"], paketId)
      if paketId == record["id"]:
        paketIdPlace = record
        break

    #print(paketIdPlace)
    personal += int(paketIdPlace["fields"]["Personal"])
    #print(personal)
    try:
      if paketIdPlace["fields"]["Svanis"]:
        svanis = True
    except KeyError:# as e:
      #print(e)
      pass
  
  #print(prylTableList)

  prylLista = []

 
  #prelPrylLista = []
  
  #Recursion med möjliga paket i prylpaket, output till lista
  prelPrylLista = []
  if paket == True:
    #print("hello")
    try:
      for paketPaketId in paketIdPlace["fields"]["Paket i prylPaket"]:
        #print(prylTableList[0], paketTableList[0])
        output = skaffaPrylarUrPaket(paketPaketId, prylTableList, paketTableList, personal, paket = True)
        #print(output["prylLista"])
        prelPrylLista.append(output["prylLista"])
        #prylLista.append(output["prylLista"])

      for pryl in prelPrylLista[0]:
        prylLista.append(pryl)
          
    except KeyError:# as e:
      #print(e)
      pass
    #Kolla efter alla prylar 
    try:
      try:
        
        antalPrylar = str(paketIdPlace["fields"]["Antal Prylar"])+","
        antalPrylar = antalPrylar.split(",")
        if antalPrylar[-1] == "":
          del antalPrylar[-1]
        
        for prylId in paketIdPlace["fields"]["prylar"]:
          for record in prylTableList:
            #print(item["id"], prylId)
            if record["id"] == prylId:
              pryl = prylTableList[int(prylTableList.index(record))+1]
              platsILista = paketIdPlace["fields"]["prylar"].index(prylId)
              #print(prylId, platsILista)
              
              for i in range(0, platsILista):
                prylLista.append(record["fields"])
              break
              
      except KeyError:# as e:
        #print(e)
        for prylId in paketIdPlace["fields"]["prylar"]:
          for record in prylTableList:
            if record == prylId:
              pryl = prylTableList[int(prylTableList.index(record))+1]
              prylLista.append(pryl["fields"])
              
        #pryl = prylTable.get(prylId)

          
    except KeyError:# as e:
      #print(e)
      pass
  if prylar:
    try:
      antalPrylar = str(inputData["antalPrylar"])+","
      antalPrylar = antalPrylar.split(",")
      if antalPrylar[-1] == "":
       del antalPrylar[-1]
        
      #print(antalPrylar)
      for prylId in prylar["prylar"]:
        for record in prylTableList:
          if record["id"] == prylId:
            
            pryl = prylTableList[int(prylTableList.index(record))+1]
            platsILista = prylar["prylar"].index(prylId)
            #print(antalPrylar[int(platsILista)])
            for i in range(0, int(antalPrylar[platsILista])):
              prylLista.append(record["fields"])
            

    except KeyError:# as e:
      #print(e)
      for prylId in prylar["prylar"]:
        #print(prylId)
        for record in prylTableList:
          #print(item)
          if record["id"] == prylId:
            prylLista.append(record["fields"])
            
  #print(prylLista)
  #print(stop - start, svanisTime - start, paketRecursionTime - svanisTime, prylTime - paketRecursionTime)

  return {"prylLista": prylLista, "personal": personal, "svanis": svanis}



inputFields=["gigNamn", "prylPaket", "dagLängd", "extraPrylar", "dagLängd", "dagar", "extraPersonal", "hyrKostnad", "antalPaket", "antalPrylar", "extraPrylar", "projekt"]
paketFields=["Paket Namn", "Paket i prylPaket", "Prylar", "Antal Prylar", "Personal", "Svanis", "Hyreskostnad"]
prylFields=["Pryl Namn", "pris"]

config = {}
baseName = "appG1QEArAVGABdjm"
inputTable = Table(api_key, baseName, 'Input data')
paketTable = Table(api_key, baseName, 'Pryl Paket')
prylTable = Table(api_key, baseName, 'Prylar')
outputTable = Table(api_key, baseName, 'Output table')
configTable = Table(api_key, baseName, 'Config')
isItRunning = False
def everything():
  global isItRunning
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
  
  #print(allPrylar)
  outputTableList = outputTable.all()

  start = time.time()

  configTableList = configTable.all()
  try:
      
    inputData = inputTableList[1]["fields"]
    print(inputData)
    #uppdatera översta "Input Data" table, och sedan ta bort det nya som var underst
    
    #inputTable.update(inputTableList[0]["id"], inputData)
    #inputTable.delete(inputTableList[1]["id"])
    inputTableSaveOriginal = copy.deepcopy(inputData)
    #print("hello!", inputTableSaveOriginal)

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
    #Fixa prylar från paket ids + antal paket som används
    try: 
      try:
        #print(inputData)
        inputData["antalPaket"] += ","
        inputData["antalPaket"] = inputData["antalPaket"].split(",")
        if inputData["antalPaket"][-1] == '':
          del inputData["antalPaket"][-1]
        for i in range(0, len(inputData["antalPaket"])):
          startILoop = time.time()
          for j in range(0, int(inputData["antalPaket"][i])):
            startILoopLoop = time.time()
            #print(inputData["prylPaket"])
            paketId = inputData["prylPaket"][i]
            prylarUrPaket = skaffaPrylarUrPaket(paketId, allPrylar, allPaket, paket=True)
            personal += prylarUrPaket["personal"]
            #print(time.time() - startILoopLoop)

            for pryl in prylarUrPaket["prylLista"]:
              prylLista.append(pryl)
          #print(time.time() - startILoop)
        #print(prylLista)
      except KeyError:
        for paketId in inputData["prylPaket"]:
          prylarUrPaket = skaffaPrylarUrPaket(paketId, allPrylar, allPaket, paket=True)
          personal += prylarUrPaket["personal"]
          #print(prylarUrPaket)
          for pryl in prylarUrPaket["prylLista"]:
            prylLista.append(pryl)
          #print(prylLista)
    except KeyError:
      pass
    #print("hello")
    #Fixa prylar från IDs  
    try:
      prylarUrPrylId = skaffaPrylarUrPaket(0, allPrylar, allPaket, False, prylar=inputData["extraPrylar"])
      for pryl in prylarUrPrylId["prylLista"]:
        prylLista.append(pryl)

    except KeyError:
      pass
    #print(prylLista)
    middle = time.time()
    inputData["prylar"] = prylLista
    try:
      inputData["svanis"] = prylarUrPaket["svanis"]
      inputData["personal"] = personal + inputData["extraPersonal"]
    except NameError:
      inputData["svanis"] = False
      inputData["personal"] = inputData["extraPersonal"]

    #fyfan

    #inputData.update(prylarOchPersonalAvPaket(inputData))
    
    #inputData["prylar"] = fixaPrylarna(inputData)
    #print(inputData["prylar"])
    for record in configTableList:
      config[record["fields"]["Name"]] = record["fields"]["Siffra i decimal"]
    print("Running the kalkylark\n")
    #print(inputData["prylar"], "\n")




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
    #print(kalkylOutput)

    kalkylOutput["debug"] = "`" + str([config, inputData, prylInfo, personalInfo, marginalInfo]) + "`"
    #print(kalkylOutput["debug"])
    #print(config, inputData, prylInfo, personalInfo, marginalInfo)
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
      #print(record)
      if record["fields"]["Gig Namn"] == inputData["gigNamn"]:
        outputId = record["id"]
        outputTable.update(outputId, kalkylOutput, replace=True)
        #print(outputId, "hi!!")
        duplicateOrNot = True
    if duplicateOrNot == False:
      print(kalkylOutput)
      outputId = outputTable.create(kalkylOutput)
      outputId = re.findall(r"(?:.*{'id': ')(\w+)(?:', 'fields': {'Gig Namn': '.*', 'Helpris')", str(outputId))[0]
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
    if projectExists == False:
      outputId = [outputId]
      projectTable.create({"Name": inputData["projekt"], "Leveranser": outputId})
    isItRunning = False
    Thread(target = everything).stop()
server()    
while True:
  if runItNext == True:
    print("Hello")
    runItNext = False
    everything()
  

areWeRunning = True
if __name__ == '__main__':
    Thread(target = server).start()
    Thread(target = everything).start()
    #print("hello")


 