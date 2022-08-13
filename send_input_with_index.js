/* Pick from a table */
let table = base.getTable("Input data");
let records = {}
let record = await input.recordAsync('Pick a record', table);
if (record) {
    records[record.name] = {}
    for (let field of table.fields) {
        records[record.name][field.name] = (record.getCellValue(field.name));
    }
    records[record.name]["input_id"] = record.id
}

await remoteFetchAsync("http://pi.levandevideo.se:5000/start", {
    method: "POST",
    body: JSON.stringify(records),
    headers: {
        'Content-Type': 'application/json',
    },
})

