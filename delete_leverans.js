/* Pick from a table */
let table = base.getTable("Leveranser");
let record = await input.recordAsync('Pick a record', table);
let kalender_table = base.getTable("Projektkalender")
let svar = await input.buttonsAsync('Det här kommer ta bort din leverans! Är du säker på att du vill det?',
    [
        { label: 'Nej!', value: false, variant: 'primary' },
        { label: 'Ja!', value: true, variant: 'danger' }

    ]);



if (record && svar == true) {
    let dagar = record.getCellValue("Projektkalender")
    console.log(dagar)
    for (let dag in dagar) {
        let dag2 = dagar[dag]
        await kalender_table.deleteRecordAsync(dag2.id)
    }
    input.buttonsAsync('Okej!', []);
    let config_table = base.getTable("Config")
    let auth_rec = await config_table.selectRecordAsync('recd7WhiqtNbEVZzZ')
    if (auth_rec) {
        let auth_key = await auth_rec.getCellValue("key")
        if (auth_key) {
            await remoteFetchAsync("http://pi.levandevideo.se:5000/delete", {
                method: "POST",
                body: JSON.stringify({ "content": record.getCellValueAsString("Gig namn") }),
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': auth_key
                }
            })
        }
    }
    await table.deleteRecordAsync(record.id);
}
else {
    input.buttonsAsync('Bra val!', []);
}
