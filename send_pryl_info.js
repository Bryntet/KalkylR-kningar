
let table = base.getTable("Leveranser")
let records = {}

for (let table of base.tables) {
    let tName = table.name
    if (tName == "Prylar" || tName == "Config" || tName == "Pryl Paket" || tName == "Frilans") {
        records[tName] = {}
        let queryResult = await table.selectRecordsAsync();
        for (let record of queryResult.records) {
            let recordName = record.name
            records[tName][recordName] = {}
            for (let field of table.fields) {
                let notAllowed = ["Pryl Paket 2", null, recordName, "debug", "Uppdatera", "Input data"]
                if (notAllowed.includes(record.getCellValue(field)) == false && notAllowed.includes(field.name) == false) {
                    records[tName][recordName][field.name] = record.getCellValue(field)
                }
            }
        }
    }
}

let folk_table = base.getTable("Frilans")
let fields_filter = ["Name", 'hyrkostnad', 'timpeng', 'timpeng efter', 'Levande Video', 'Kan göra dessa uppgifter']
let folkQuery = await folk_table.selectRecordsAsync({fields: fields_filter});
let folk_dict = {}
for (let person of folkQuery.records) {
    let fields = {}
    for (let field of fields_filter) {
        if (field == 'Levande Video') {
            if (person.getCellValue(field) === null) {
                fields[field] = false
            }
            else {
                fields[field] = true
            }
        }
        else if (field == 'Kan göra dessa uppgifter') {
            if (person.getCellValue(field) != null) {
                let uppgift_lista = []
                for (let uppgift of person.getCellValue(field)) {
                    uppgift_lista.push(uppgift['name'])
                }
                fields[field] = uppgift_lista

            }
        }
        else {
            fields[field] = await person.getCellValue(field)
        }
    }
    
    folk_dict[person.id] = fields
}


let config_table = base.getTable("Config")
let auth_rec = await config_table.selectRecordAsync('recd7WhiqtNbEVZzZ')
if (auth_rec) {
    let auth_key = await auth_rec.getCellValue("key")
    if (auth_key) {

        await remoteFetchAsync("http://pi.levandevideo.se:5000/update/config", {
            method: "POST",
            body: JSON.stringify(records),
            headers: {
                'Content-Type': 'application/json',
                'Authorization': auth_key
            },
        })
    }
}

