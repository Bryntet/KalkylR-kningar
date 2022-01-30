import os
import time
from pyairtable import Table
import random
from threading import Thread


api_key = os.environ['api_key']
import math

from flask import Flask, request

app = Flask(  # Create a flask app
	__name__,
	template_folder='templates',  # Name of html file folder
	static_folder='static'  # Name of directory for static files
)



@app.route("/")
def home(methods=["GET"]):
  global areWeRunning
  areWeRunning = True
  return "hi"



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
  print("in raknaPryl", inputData["prylar"])
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
  print("in skaffaPrylarUrPaket")
  global inputData
  #print(prylar)
  #print(prylTableList)
  if paket == True:
    for record in paketTableList:
      #print(record["id"], paketId)
      #print(record["id"], paketId)
      print(record["id"], paketId)
      if paketId == record["id"]:
        paketIdPlace = record
        break

    print(paketIdPlace)
    personal += int(paketIdPlace["fields"]["Personal"])
    #print(personal)
    try:
      if paketIdPlace["fields"]["Svanis"]:
        svanis = True
    except KeyError as e:
      print(e)
      #pass
  
  #print(prylTableList)

  prylLista = []

 
  #prelPrylLista = []
  
  #Recursion med möjliga paket i prylpaket, output till lista
  prelPrylLista = []
  if paket == True:
    print("hello")
    try:
      for paketPaketId in paketIdPlace["fields"]["Paket i prylPaket"]:
        #print(prylTableList[0], paketTableList[0])
        output = skaffaPrylarUrPaket(paketPaketId, prylTableList, paketTableList, personal, paket = True)
        #print(output["prylLista"])
        prelPrylLista.append(output["prylLista"])
        #prylLista.append(output["prylLista"])

      for pryl in prelPrylLista[0]:
        prylLista.append(pryl)
          
    except KeyError as e:
      print(e)
      #pass
    #Kolla efter alla prylar 
    try:
      try:
        
        antalPrylar = str(paketIdPlace["fields"]["Antal Prylar"])+","
        antalPrylar = antalPrylar.split(",")
        if antalPrylar[-1] == "":
          del antalPrylar[-1]
        
        for prylId in paketIdPlace["fields"]["Prylar"]:
          for record in prylTableList:
            #print(item["id"], prylId)
            if record["id"] == prylId:
              pryl = prylTableList[int(prylTableList.index(record))+1]
              platsILista = paketIdPlace["fields"]["Prylar"].index(prylId)
              #print(prylId, platsILista)
              
              for i in range(0, platsILista):
                prylLista.append(record["fields"])
              break
              
      except KeyError as e:
        print(e)
        for prylId in paketIdPlace["fields"]["Prylar"]:
          for record in prylTableList:
            if record == prylId:
              pryl = prylTableList[int(prylTableList.index(record))+1]
              prylLista.append(pryl["fields"])
              
        #pryl = prylTable.get(prylId)

          
    except KeyError as e:
      print(e)
      #pass
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
            

    except KeyError as e:
      print(e)
      for prylId in prylar["prylar"]:
        #print(prylId)
        for record in prylTableList:
          #print(item)
          if record["id"] == prylId:
            prylLista.append(record["fields"])
            
  #print(prylLista)
  #print(stop - start, svanisTime - start, paketRecursionTime - svanisTime, prylTime - paketRecursionTime)

  return {"prylLista": prylLista, "personal": personal, "svanis": svanis}



inputFields=["gigNamn", "prylPaket", "dagLängd", "extraPrylar", "dagLängd", "dagar", "extraPersonal", "hyrKostnad", "antalPaket", "antalPrylar", "extraPrylar"]
paketFields=["Paket Namn", "Paket i prylPaket", "Prylar", "Antal Prylar", "Personal", "Svanis", "Hyreskostnad"]
prylFields=["Pryl Namn", "pris"]

config = {}
baseName = "appG1QEArAVGABdjm"
inputTable = Table(api_key, baseName, 'Input data')
paketTable = Table(api_key, baseName, 'Pryl Paket')
prylTable = Table(api_key, baseName, 'Prylar')
outputTable = Table(api_key, baseName, 'Output table')
configTable = Table(api_key, baseName, 'Config')

areWeRunning = False
def everything():
  global paketFields
  global inputData
  global areWeRunning
  global svanis
  global prylFields
  global inputFields
  
  while True:
    personal = 0
    if areWeRunning == True:
      areWeRunning = False
      allPrylar = prylTable.all(fields=prylFields)
      allPaket = paketTable.all(fields=paketFields)
      inputTableList = inputTable.all(fields=inputFields)
      #print(allPrylar)
      outputTableList = outputTable.all()

      start = time.time()

      configTableList = configTable.all()
      try:
          
        inputData = inputTableList[1]["fields"]
        inputData.pop("Paket Namn (from prylPaket)", None)
        
        #uppdatera översta "Input Data" table, och sedan ta bort det nya som var underst
        inputTable.update(inputTableList[0]["id"], inputData)
        inputTable.delete(inputTableList[1]["id"])
        dontRunAnyMore = False
      except IndexError:
        dontRunAnyMore = True
      if dontRunAnyMore != True:
          
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
                print(inputData["prylPaket"])
                paketId = inputData["prylPaket"][i]
                prylarUrPaket = skaffaPrylarUrPaket(paketId, allPrylar, allPaket, paket=True)
                personal += prylarUrPaket["personal"]
                print(time.time() - startILoopLoop)

                for pryl in prylarUrPaket["prylLista"]:
                  prylLista.append(pryl)
              print(time.time() - startILoop)
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
        print("hello")
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
      

areWeRunning = True
if __name__ == '__main__':
    Thread(target = server).start()
    Thread(target = everything).start()
    #print("hello")