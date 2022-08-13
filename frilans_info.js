let table = base.getTable("Projekt kalender")
let input_table = base.getTable("Input data")
let view = table.getView("Grid view");
/* Pick from a table */

let thing = await input.recordAsync('Pick a record', view);


let record_id = thing.getCellValue("input_id")



let record = await input_table.selectRecordAsync(record_id)
console.log(record)


console.log()

let dict = {}
if (record) {
    dict[record.name] = {}
    for (let field of input_table.fields) {
        try {
            dict[record.name][field.name] = (record.getCellValue(field.id));
        } catch (TypeError) {
            continue
        }
    }

    dict[record.name]["uppdateraa"] = true
    dict[record.name]["uppdateraProjekt"] = thing.getCellValue("Projekt")
    dict[record.name]["input_id"] = record_id
    dict[record.name]["Frilans"] = thing.getCellValue("Frilans")
    console.log(dict)
    let config_table = base.getTable("Config")
    let auth_rec = await config_table.selectRecordAsync('recd7WhiqtNbEVZzZ')
    if (auth_rec) {
        let auth_key = await auth_rec.getCellValue("key")
        if (auth_key) {
            await remoteFetchAsync("http://pi.levandevideo.se:5000/start", {
                method: "POST",
                body: JSON.stringify(dict),
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': auth_key
                },
            })
        }
    }
}




