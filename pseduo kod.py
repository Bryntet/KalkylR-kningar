
def getThePrylarFromThePaket(prylTable, inputTable, paketTable):

  paketTableList = paketTable.all()
  inputTableList = inputTable.all()
  prylListaPrel = []
  prylLista = []
  for prylPaket in inputTableList[0]["fields"]["prylPaket"]:

    try:
      
      for pryl in paketTable.get(prylPaket)["fields"]["Prylar"]:
        #print(prylTable.get(pryl)["fields"])
        prylListaPrel.append(prylTable.get(pryl)["fields"])
      
        
    except KeyError:
      print("hello")
  #print(paketTable.get(prylPaket))

    for paket in paketTable.get(prylPaket)["fields"]["Paket i prylPaket"]:
      print("hi")
      #print(paket)
      for pryl in paketTable.get(paket)["fields"]["Prylar"]:
        #print(prylTable.get(pryl)["fields"])
        prylListaPrel.append(prylTable.get(pryl)["fields"])
        #print("hello")
    print(prylListaPrel)




  #print(prylListaPrel)

  for i in range(0, len(prylListaPrel)):
    try:
      if paketTableList[i]["fields"]["Antal Prylar"] == "1":
        prylLista.append(prylListaPrel[i])
      else:
        #print(paketTableList[i]["fields"]["Antal Prylar"])
        for siffra in paketTableList[i]["fields"]["Antal Prylar"]:
          prylLista.append(prylListaPrel[i])
    except KeyError:
      continue

  #print(prylLista)
  for pryl in prylLista:
    print(pryl["Pryl Namn"])
