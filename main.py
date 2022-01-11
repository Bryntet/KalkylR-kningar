import os
import re
import time
from pyairtable import Table
api_key = os.environ['api_key']
import math


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

    riggTimmar = round(prylPris*andelRiggTimmar)
    
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
  #Pris = Pris för kund ellie e best
  #Kostnad = Kostnad för levande video kooperativet!
  prylPris = 0
  dagar = inputData["dagar"]
  prylKostnadMulti = config["prylKostnadMulti"]
  dagTvåMulti = config["dagTvåMulti"]


  try:
    for pryl in inputData["prylar"]:
      prylPris += round((float(pryl["pris"])*prylKostnadMulti)/10)*10
  except TypeError:
    prylPris = 0
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






def skaffaPrylarUrPaket(paketId, prylTable, paketTable, paket = True, personal = 0, svanis = False, **prylar):
  paketTable = Table(api_key, 'appdfwFF83lU6ipfH', 'Pryl Paket')
  prylTable = Table(api_key, 'appdfwFF83lU6ipfH', 'Prylar')
  #print(prylar)
  global inputFields
  global paketFields
  global prylFields
  if paket == True:
    paketIdPlace = paketTable.get(paketId)  
    personal += int(paketIdPlace["fields"]["Personal"])
    print(personal)
    try:
      if paketIdPlace["fields"]["Svanis"]:
        svanis = True
    except KeyError:
      pass
  prylTableList = prylTable.all(fields=prylFields)
  #print(prylTableList)

  prylLista = []

 
  #prelPrylLista = []

  #Recursion med möjliga paket i prylpaket, output till lista
  prelPrylLista = []
  if paket == True:
    try:
      for paketPaketId in paketIdPlace["fields"]["Paket i prylPaket"]:

        output = skaffaPrylarUrPaket(paketPaketId, prylTable, paketTable, personal, paket = True)
        #print(output["prylLista"])
        prelPrylLista.append(output["prylLista"])
        #prylLista.append(output["prylLista"])

      for pryl in prelPrylLista[0]:
        prylLista.append(pryl)
          
    except KeyError:
      pass
    #Kolla efter alla prylar 
    
    try:
      try:
        antalPrylar = paketIdPlace["fields"]["Antal Prylar"].split(",")
        
        for prylId in paketIdPlace["fields"]["Prylar"]:
          for item in prylTableList:
            #print(item["id"], prylId)
            if item["id"] == prylId:
              pryl = prylTableList[int(prylTableList.index(item))+1]
              platsILista = paketIdPlace["fields"]["Prylar"].index(prylId)
              
              for i in range(0, int(antalPrylar[platsILista])):
                prylLista.append(item["fields"])
              
      except KeyError:
        for prylId in paketIdPlace["fields"]["Prylar"]:
          for item in prylTableList:
            if item == prylId:
              pryl = prylTableList[int(prylTableList.index(item))+1]
              prylLista.append(pryl["fields"])
              
        #pryl = prylTable.get(prylId)

          
    except KeyError:
      pass

  if prylar:
    try:
      antalPrylar = inputData["antalPrylar"].split(",")
      print(antalPrylar)
      for prylId in prylar["prylar"]:
        for item in prylTableList:
          if item["id"] == prylId:
            
            pryl = prylTableList[int(prylTableList.index(item))+1]
            platsILista = prylar["prylar"].index(prylId)
            print(antalPrylar[int(platsILista)])
            for i in range(0, int(antalPrylar[platsILista])):
              prylLista.append(item["fields"])
            

    except KeyError:
      for prylId in prylar["prylar"]:
        #print(prylId)
        for item in prylTableList:
          #print(item)
          if item["id"] == prylId:
            prylLista.append(item["fields"])
            

  
  #print(prylLista)
  #print(stop - start, svanisTime - start, paketRecursionTime - svanisTime, prylTime - paketRecursionTime)
  return {"prylLista": prylLista, "personal": personal, "svanis": svanis}



inputFields=["gigNamn", "prylPaket", "dagLängd", "extraPrylar", "dagLängd", "dagar", "extraPersonal", "hyrKostnad", "textning", "syntolkning", "antalPaket", "antalPrylar", "extraPrylar"]
paketFields=["Paket Namn", "Paket i prylPaket", "Prylar", "Antal Prylar", "Personal", "Svanis", "Hyreskostnad"]
prylFields=["Pryl Namn", "pris"]

config = {}

inputTable = Table(api_key, 'appdfwFF83lU6ipfH', 'Input data')
paketTable = Table(api_key, 'appdfwFF83lU6ipfH', 'Pryl Paket')
prylTable = Table(api_key, 'appdfwFF83lU6ipfH', 'Prylar')
outputTable = Table(api_key, 'appdfwFF83lU6ipfH', 'Output table')
configTable = Table(api_key, 'appdfwFF83lU6ipfH', 'Config')
while True:

  inputTableList = inputTable.all(fields=inputFields)

  try:
    #om ny rad i "Input Data" (att man har submittat form): kör kod 
    if inputTableList[1]:

      outputTableList = outputTable.all()

      start = time.time()

      configTableList = configTable.all()
      inputData = inputTableList[1]["fields"]
      inputData.pop("Paket Namn (from prylPaket)", None)
      
      #uppdatera översta "Input Data" table, och sedan ta bort det nya som var underst
      inputTable.update(inputTableList[0]["id"], inputData)
      inputTable.delete(inputTableList[1]["id"])

      prylLista = []
      #Fixa prylar från paket ids + antal paket som används
      try: 
        try:
          inputData["antalPaket"] += ","
          inputData["antalPaket"] = inputData["antalPaket"].split(",")
          if inputData["antalPaket"][1] == '':
            del inputData["antalPaket"][1]
          #print(inputData["antalPaket"])
          for i in range(0, len(inputData["antalPaket"])):
            #print("hello")
            for j in range(0, int(inputData["antalPaket"][i])):
              #print("hello 2")
              paketId = inputData["prylPaket"][i]
              prylarUrPaket = skaffaPrylarUrPaket(paketId, prylTable, paketTable, paket=True)
              personal += prylarUrPaket["personal"]
              
              #print(prylarUrPaket)
              for pryl in prylarUrPaket["prylLista"]:
                prylLista.append(pryl)
          #print(prylLista)
        except KeyError:
          for paketId in inputData["prylPaket"]:
            prylarUrPaket = skaffaPrylarUrPaket(paketId, prylTable, paketTable, paket=True)
            personal += prylarUrPaket["personal"]
            #print(prylarUrPaket)
            for pryl in prylarUrPaket["prylLista"]:
              prylLista.append(pryl)
            #print(prylLista)
      except KeyError:
        pass

      #Fixa prylar från IDs  
      try:
        prylarUrPrylId = skaffaPrylarUrPaket(0, prylTable, paketTable, False, prylar=inputData["extraPrylar"])
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
      print(kalkylOutput)

      kalkylOutput["debug"] = "`" + str([config, inputData, prylInfo, personalInfo, marginalInfo]) + "`"
      #print(kalkylOutput["debug"])
      print(config, inputData, prylInfo, personalInfo, marginalInfo)
      
      duplicateOrNot = False

      for record in outputTableList:
        #print(record)
        if record["fields"]["Gig Namn"] == inputData["gigNamn"]:
          outputTable.update(record["id"], kalkylOutput, replace=True)
          duplicateOrNot = True
      if duplicateOrNot == False:
        outputTable.create(kalkylOutput)
      svanis = False
      stop = time.time()
      print("The time of the run:", stop - start, "\n Time to middle was: ", middle - start)
      
  except IndexError:
    pass

