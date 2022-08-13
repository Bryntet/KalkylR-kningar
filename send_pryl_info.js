
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

await remoteFetchAsync("http://pi.levandevideo.se:5000/update/config", {
    method: "POST",
    body: JSON.stringify(records),
    headers: {
        'Content-Type': 'application/json',
    },
})

records = {}


