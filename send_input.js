
let table = base.getTable("Input data")
//let record = await input.recordAsync('Please select a record', table);


// query for given fields from every record in "Människor!".

let query = await table.selectRecordsAsync();
let records = {}

for (let record of query.records) {
    records[record.name] = {}
    for (let field of table.fields) {
        records[record.name][field.name] = (record.getCellValue(field.name));
    }
    records[record.name]["input_id"] = record.id
}


let config_table = base.getTable("Config")
let auth_rec = await config_table.selectRecordAsync('recd7WhiqtNbEVZzZ')
if (auth_rec) {
    let auth_key = await auth_rec.getCellValue("key")
    if (auth_key) {
        await remoteFetchAsync("http://pi.levandevideo.se:5000/start", {
            method: "POST",
            body: JSON.stringify(records),
            headers: {
                'Content-Type': 'application/json',
                'Authorization': auth_key
            },
        })
    }
}

