/* Pick from a table */
let table = base.getTable("Leveranser");
let record = await input.recordAsync('Pick a record', table);
let kalender_table = base.getTable("Projektkalender")
if (record) {
    let dagar = record.getCellValue("Projekt kalender")
    console.log(dagar)
    for (let dag in dagar) {
        let dag2 = dagar[dag]
        await kalender_table.deleteRecordAsync(dag2.id)
    }
    input.buttonsAsync('Okej!', []);

    await table.deleteRecordAsync(record.id);
}