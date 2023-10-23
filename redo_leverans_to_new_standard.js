/* Pick from a table */
let table = base.getTable("Leveranser");
let record = await input.recordAsync('Pick a record', table);
let kalender_table = base.getTable("Projektkalender")

if (record) {

    let input_table = base.getTable("Input data")
    let input_thing = record.getCellValue('made_by')
    let config_table = base.getTable("Config")
    let auth_rec = await config_table.selectRecordAsync('recd7WhiqtNbEVZzZ')
    let input_record = await input_table.selectRecordAsync(input_thing[0]["id"])

    if (record.name.split("#")[1] == "2") {
        if (auth_rec) {
            let auth_key = await auth_rec.getCellValue("key")
            if (auth_key) {
                let res1 = await remoteFetchAsync("http://pi.levandevideo.se:5000/delete", {
                    method: "POST",
                    body: JSON.stringify({"content": record.name}),
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': auth_key
                    }
                })
                if (res1.ok) {
                    console.log(res1)
                    let res2 = await remoteFetchAsync("http://pi.levandevideo.se:5000/delete", {
                        method: "POST",
                        body: JSON.stringify({"content": record.name.split("#")[0].concat("#1")}),
                        headers: {
                            'Content-Type': 'application/json',
                            'Authorization': auth_key
                        }
                    })
                    if (res2.ok) {
                        console.log(res2)
                        if (input_record) {
                            let records = {}
                            records[input_record.name] = {}
                            for (let field of input_table.fields) {
                                records[input_record.name][field.name] = (input_record.getCellValue(field.name));
                            }
                            records[input_record.name]["input_id"] = input_record.id


                            if (auth_rec) {
                                let auth_key = await auth_rec.getCellValue("key")
                                if (auth_key) {
                                    let response = await remoteFetchAsync("http://pi.levandevideo.se:5000/start", {
                                        method: "POST",
                                        body: JSON.stringify(records),
                                        headers: {
                                            'Content-Type': 'application/json',
                                            'Authorization': auth_key
                                        },
                                    })
                                    if (response) {
                                        let dagar = record.getCellValue("Projekt kalender")
                                        console.log(dagar)
                                        for (let dag in dagar) {
                                            let dag2 = dagar[dag]
                                            await kalender_table.deleteRecordAsync(dag2.id)
                                        }
                                        await table.deleteRecordAsync(record.id);
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    if (record.name.split("#")[1] == "1") {
        if (auth_rec) {
            let auth_key = await auth_rec.getCellValue("key")
            if (auth_key) {
                let res1 = await remoteFetchAsync("http://pi.levandevideo.se:5000/delete", {
                    method: "POST",
                    body: JSON.stringify({"content": record.name}),
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': auth_key
                    }
                })
                if (res1) {
                    if (input_record) {
                        let records = {}
                        records[input_record.name] = {}
                        for (let field of input_table.fields) {
                            records[input_record.name][field.name] = (input_record.getCellValue(field.name));
                        }
                        records[input_record.name]["input_id"] = input_record.id


                        if (auth_rec) {
                            let auth_key = await auth_rec.getCellValue("key")
                            if (auth_key) {
                                let response = await remoteFetchAsync("http://pi.levandevideo.se:5000/start", {
                                    method: "POST",
                                    body: JSON.stringify(records),
                                    headers: {
                                        'Content-Type': 'application/json',
                                        'Authorization': auth_key
                                    },
                                })
                                if (response) {
                                    let dagar = record.getCellValue("Projekt kalender")
                                    console.log(dagar)
                                    for (let dag in dagar) {
                                        let dag2 = dagar[dag]
                                        await kalender_table.deleteRecordAsync(dag2.id)
                                    }
                                    await table.deleteRecordAsync(record.id);
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}