
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

//output.inspect(records);


//console.log(JSON.stringify(records))
await remoteFetchAsync("http://pi.levandevideo.se:5000/start", {
    method: "POST",
    body: JSON.stringify(records),
    headers: {
        'Content-Type': 'application/json',
    },
})

records = {}


