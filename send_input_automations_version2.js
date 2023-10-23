let inputConfig = input.config();
let record_id = inputConfig.record_id
let table = base.getTable("Input data")
let beställareid = inputConfig.beställareid
let beställarename = inputConfig.beställarename
let beställare = [{"id": beställareid, "name": beställarename}]
let record = await table.selectRecordAsync(record_id)
console.log(record)


console.log()

let dict = {}
if (record) {
    dict[record.name] = {}
    for (let field of table.fields) {
        try {
            dict[record.name][field.name] = (record.getCellValue(field.id));
        } catch (TypeError) {

        }
    }
    dict[record.name]["input_id"] = record_id
    dict[record.name]["Beställare"] = beställare
    console.log(dict)
    let config_table = base.getTable("Config")
    let auth_rec = await config_table.selectRecordAsync('recd7WhiqtNbEVZzZ')
    if (auth_rec) {
        let auth_key = await auth_rec.getCellValue("key")
        if (auth_key) {
            await fetch("http://pi.levandevideo.se:5000/start", {
                method: "POST",
                body: JSON.stringify(dict),
                headers: {
                    'Content-Type': 'application/json',
                },
            })

        }
    }
}
