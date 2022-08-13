/* Pick from a table */
let table = base.getTable("Leveranser");
let record = await input.recordAsync('Pick a record', table);
let kalender_table = base.getTable("Projekt kalender")
let svar = await input.buttonsAsync('Det här kommer ta bort din leverans! Är du säker på att du vill det?',
    [
        { label: 'Nej!', value: false, variant: 'primary' },
        { label: 'Ja!', value: true, variant: 'danger' }

    ]);



if (record && svar == true) {
    let dagar = record.getCellValue("Projekt kalender")
    console.log(dagar)
    for (let dag in dagar) {
        let dag2 = dagar[dag]
        await kalender_table.deleteRecordAsync(dag2.id)
    }
    input.buttonsAsync('Okej!', []);
    await remoteFetchAsync("http://pi.levandevideo.se:5000/delete", {
        method: "POST",
        body: JSON.stringify({ "content": record.getCellValueAsString("Gig namn") }),
        headers: {
            'Content-Type': 'application/json',
        }
    })
    await table.deleteRecordAsync(record.id);
}
else {
    input.buttonsAsync('Bra val!', []);
}
