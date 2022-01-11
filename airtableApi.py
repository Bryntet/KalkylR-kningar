import time
import os
from pyairtable import Table
api_key = os.environ['api_key']




table = Table(api_key, 'appdfwFF83lU6ipfH', 'Real time test')
records = [{'Name': 'John'}, {'Name': 'Marc'}]

table.batch_update('base_id', 'table_name', records)


while True:
    time.sleep(1)
    table = Table(api_key, 'appdfwFF83lU6ipfH', 'Real time test')
    theTable = table.get("rec2Rs4no9ntkCZfV")
    try:
        print(theTable["fields"]["Number"])
        if theTable["fields"]["Number"] == 57:
            print("Hooray!")
            table.update("recunMNRpzvKSywXt", {"Name": "You wrote 57!"})


        else:
            table.update("recunMNRpzvKSywXt", {"Name": "You didn't write 57!"})
    except KeyError:
        continue
config = {

}