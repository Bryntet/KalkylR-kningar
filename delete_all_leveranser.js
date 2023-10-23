/* Pick from a table */
let table = base.getTable("Leveranser");
let table2 = base.getTable("Projekt kalender")
let svar = await input.buttonsAsync('Det här kommer ta bort ***alla*** dina leveranser! Är du säker på att du vill det?',
    [
        {label: 'Nej!', value: false, variant: 'primary'},
        {label: 'Ja!', value: true, variant: 'danger'}

    ]);


let query = await table.selectRecordsAsync()
let query2 = await table2.selectRecordsAsync()
console.log(query)

let config_table = base.getTable("Config")
let auth_rec = await config_table.selectRecordAsync('recd7WhiqtNbEVZzZ')
if (auth_rec) {
    let auth_key = await auth_rec.getCellValue("key")
    if (auth_key) {

        if (svar == true) {
            for (let record of query.records) {

                await remoteFetchAsync("http://81.232.191.203:5000/delete", {
                    method: "POST",
                    body: JSON.stringify({"content": record["name"]}),
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': auth_key
                    }
                })
                await table.deleteRecordAsync(record.id);
            }
            for (let record of query2.records) {
                await table2.deleteRecordAsync(record.id);
            }
        } else {
            input.buttonsAsync('Bra val!', []);
        }
    }
}