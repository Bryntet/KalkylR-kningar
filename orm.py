from pyairtable.orm import Model, fields
from pyairtable import metadata, Base
import os
import math

table_schema = metadata.get_base_schema(
    Base(os.environ["api_key"], os.environ["base_id"])
)


def record_to_orm(table, record_input):
    new_ORM = table()
    new_ORM.id = record_input["id"]

    for table_ in table_schema["tables"]:
        if table_["id"] == table().Meta.table_name:
            tbl_flds = table_["fields"]

    for field_name, value in record_input["fields"].items():
        for field_id, name in [(x["id"], x["name"]) for x in tbl_flds]:
            if field_name == name:
                new_ORM.__dict__["_fields"][field_id] = value
    return new_ORM


class Prylar(Model):
    name = fields.TextField("fldAakG5Ntk1Mro4S")
    uträknat_pris = fields.FloatField("fld1qKXF28Qz2pJG2")
    in_pris = fields.FloatField("fldgY78pJgbgBi4Dy")
    livs_längd = fields.TextField("fldwG40TFkeqHVMYG")
    antal_inventarie = fields.FloatField("fldO8AaLRqgoQtmAz")
    hide_from_calendar = fields.CheckboxField("fldb0Hgi9WB3OD8mI")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def calc_pris(self):
        self.pris = (
            math.floor((self.in_pris * config["prylKostnadMulti"]) / 10 * self.mult)
            * 10
        )

    class Meta:
        base_id = os.environ["base_id"]
        table_name = "Prylar"
        api_key = os.environ["api_key"]


class Paket(Model):
    name = fields.TextField("fld3ec1hcB3LK56R7")
    Uträknat_pris = fields.FloatField("fld0tl6Outn8f6lEj")
    # paket_i_pryl_paket = fields.LinkField("fld1PIcwxpsFkrcYy", "Paket")
    paket_prylar = fields.LinkField("fldGkPJMOquzQGrO9", Prylar)
    antal_av_pryl = fields.TextField("fldUTezg1xtekQBir")
    Personal = fields.FloatField("fldTTcF0qCx9p8Bz2")
    Svanis = fields.CheckboxField("fldp2Il8ITQdFXhVR")
    Hyreskostnad = fields.FloatField("fld8iEEeEjhi9KT3c")
    hide_from_calendar = fields.CheckboxField("fldQqTyRk9wzLd5fC")

    class Meta:
        base_id = os.environ["base_id"]
        api_key = os.environ["api_key"]
        table_name = "tblVThDQ16pIEkY9m"


class Projekt(Model):
    name = fields.TextField("fldkyXKKGJIsj0sQF")

    class Meta:
        base_id = os.environ["base_id"]
        api_key = os.environ["api_key"]
        table_name = "tblR29p86mCcK9NBL"


class People(Model):
    name = fields.TextField("fld6TVIRKXVSBPplt")

    class Meta:
        base_id = os.environ["base_id"]
        api_key = os.environ["api_key"]
        table_name = "tblxHIlUSQ8VxEGts"


class Kund(Model):
    name = fields.TextField("fld3IGUwPTS8v3t44")

    class Meta:
        base_id = os.environ["base_id"]
        api_key = os.environ["api_key"]
        table_name = "tblzLHbg1jRtne4Ah"


class Slutkund(Model):
    name = fields.TextField("fld0r8joelP59QKGA")

    class Meta:
        base_id = os.environ["base_id"]
        api_key = os.environ["api_key"]
        table_name = "tblEP8fkORmQvcBCy"


class Adressbok(Model):
    name = fields.TextField("fldfyrX4mHcGjQIJc")
    distance = fields.TextField("fldphlP8E1aCyXMbT")
    time_bike = fields.IntegerField("fldcrcoZE5v7czRrg")
    time_car = fields.IntegerField("fldTr4mYBAha7sXhZ")
    transport_type = fields.TextField("fld4xpwxz0lnQdphA")
    kund = fields.LinkField("fldHH4DFi1ES93saa", Kund)
    used_time = fields.IntegerField("fldsOvDT5kugGCP9G")

    class Meta:
        base_id = os.environ["base_id"]
        api_key = os.environ["api_key"]
        table_name = "tblUEO56t49XAJBhD"


class Bestallare(Model):
    name = fields.TextField("fldte0gaCRgXDZnsn")
    kund = fields.LinkField("fldkIuEhfMdkVJVWQ", Kund)
    phone = fields.TextField("fld6mgPN89DYlydEr")
    email = fields.TextField("fld2QOLz0TFXX3wtj")

    class Meta:
        base_id = os.environ["base_id"]
        api_key = os.environ["api_key"]
        table_name = "tblpRCxCSLYEK41J0"


class Projektkalender(Model):
    status = fields.TextField("fldUrrqRZBsVLxxx4")
    kommentar_till_frilans = fields.TextField("fldK5zcWy7mVF47qe")
    grejer = fields.TextField("fld0ha80TlVUoU3LG")
    packlista__keep = fields.TextField("fldVAczarHpOYDfWn")
    slides = fields.CheckboxField("fldDhBQk3opw1CSgk")
    fakturareferens = fields.TextField("fldSEEzRXfRgwKKl2")
    skicka_mejl = fields.CheckboxField("fld7w7Rt5T1vVhzXb")
    åka_från_svanis = fields.FloatField("fldi5mO5lix7abnXm")
    actual_getin = fields.IntegerField("fldSQcKggYPFHtEAB")
    åka_från_svanis = fields.IntegerField("fldi5mO5lix7abnXm")
    komma_tillbaka_till_svanis = fields.IntegerField("flddKPdxarm5UYnZm")
    calendar_description = fields.TextField("fldeTVUkgCro8oAIg")
    actual_getout = fields.IntegerField("fldmIHQYnKeYVk9PU")
    egna_anteckningar = fields.TextField("fldYX8PWAbiRL3Qv9")
    projekt = fields.LinkField("fldfFm1RO4zqAP2zi", Projekt)
    getin_hidden = fields.DatetimeField("fldwFIqEsJo8duHMs")
    getout_hidden = fields.DatetimeField("fldW0wdl6U7kthQPj")
    frilans = fields.LinkField("flddiOloJS1I8BafH", People)
    packlista_detaljerad = fields.TextField("fldUPh7sIGcpNoDkL")
    projekt_copy = fields.TextField("fldOgfAK8SlXhzKgH")
    leveranser_copy = fields.TextField("fldPRDJlVSSOfccb8")
    projekt_2 = fields.TextField("fldXXtWhMURLywgE3")
    levandevideo = fields.LinkField("fldxTl0TKgoLymqFK", People)
    frilans_mail = fields.EmailField("flduU5Lyuuf5RGPFC")
    egen_getin = fields.FloatField("fldnz9NbGRgz9bFBT")
    bara_riggtid = fields.CheckboxField("fldEmgb8XCtjGlk3z")
    rigg_dagen_innan = fields.CheckboxField("fldZ8orE83xtYmSkM")
    m_getin = fields.FloatField("fld6F3xuRadz07hyv")
    m_getout = fields.FloatField("fldRxrXmAiZBKO4cu")
    # dagen_innan_rigg = fields.LinkField("fldYjafIh96hI3pTe", )
    # frilans_uträkningar = fields.LinkField("flds3BC39ufa1eTVc", Frilans_uträkningar)
    extra_rigg = fields.FloatField("fldPLMeJSbypPygtK")
    i_d = fields.IntegerField("fldnOyMoIQlfEJNXb")
    fakturanummer = fields.TextField("fldj3L72EeGGRE0gV")
    betalningsdatum = fields.DateField("fldjsKIIPTOhfg7gW")
    program_stop_hidden = fields.FloatField("fldpW1yaKniipOP0z")
    program_start_hidden = fields.FloatField("fldZhrBxTQ1azrdEz")

    class Meta:
        base_id = os.environ["base_id"]
        api_key = os.environ["api_key"]
        table_name = "tbllVOQa9PrKax1PY"


class Leverans(Model):
    projekt_kalender = fields.LinkField("fld8sMBfKU73Rt5RB", Projektkalender)
    link_to_update = fields.TextField("fldnAUE87gCkyzUW7")
    link_to_copy = fields.TextField("fldkVvmHIDCofPTxE")
    eget_pris = fields.IntegerField("fldh6JAFQjK5RMDPT")
    name = fields.TextField("fldeZo8wMi9C8D78j")
    Pris = fields.FloatField("fld0O9MGtVYeB87DC")
    Personal = fields.FloatField("fldGj04MBtd7yVS6y")
    extraPersonal = fields.IntegerField("flds76lS0HTW380WJ")
    Projekt_timmar = fields.IntegerField("fldrztHjZrLDjky6q")
    Rigg_timmar = fields.IntegerField("fldVfzIAGpa49C8qy")
    Pryl_pris = fields.FloatField("fldnQYR5MbklAQKSU")
    prylPaket = fields.LinkField("fldrUHtmGbW4OTX8Z", Paket)
    extraPrylar = fields.LinkField("fldIt8Y4P3xSP5xxG", Prylar)
    antalPaket = fields.TextField("fldqnN89906OtOxJC")
    antalPrylar = fields.TextField("fldwLzWn0LXYpOz4z")
    Projekt_kanban = fields.TextField("fld5Ba3wtFv6PvDW6")
    Projekt = fields.LinkField("fldXdY47lGYDUFIge", Projekt)
    börja_datum = fields.DatetimeField("fldsJHqZu5eM08Kki")
    sluta_datum = fields.DatetimeField("fldfBtMD4wSQT1ikA")
    dagar = fields.IntegerField("fldTxuAKtqGenuEzd")
    packlista = fields.TextField("fldninb2sH5xg2rdf")
    restid = fields.IntegerField("fldJCj4KjK2I8RdsG")
    projektTid = fields.IntegerField("fldW3EJf2n13tg2aC")
    dagLängd = fields.FloatField("fldEcIo4yzJQ9sRRb")
    slitKostnad = fields.FloatField("fldarGhCnL33DTvPD")
    prylFonden = fields.FloatField("fldv4MgeBeziiuRgX")
    hyrthings = fields.FloatField("fldgO3uhxa7enwZ8I")
    avkastWithoutPris = fields.FloatField("fldFQjYyG5LGQnYPU")
    avkast2 = fields.FloatField("fldnrs1UnBqz2I8Bt")
    frilanstimmar = fields.FloatField("fldKunOK7Gpqx3x77")
    total_tid_ex_frilans = fields.FloatField("fldQRQQz3L6DiEUHA")
    frilans = fields.LinkField("fld5dISuz2dXpyFWl", People)
    Bildproducent = fields.LinkField("flduzo0PJJRBF8TlT", People)
    Fotograf = fields.LinkField("fldb0SgazCjDUGJK9", People)
    Ljudtekniker = fields.LinkField("fldXo5Mr0lkWoUqyk", People)
    Ljustekniker = fields.LinkField("fld137CDZNCBJVGu6", People)
    Grafikproducent = fields.LinkField("fldIdXKDXXnPJNtjK", People)
    Animatör = fields.LinkField("fldB87dsAvgR2s5fG", People)
    Körproducent = fields.LinkField("fldn8ieh409MItTAC", People)
    Innehållsproducent = fields.LinkField("fldzosWR8ODEpyR0F", People)
    Scenmästare = fields.LinkField("fldm9REcfR7tQdf50", People)
    Tekniskt_ansvarig = fields.LinkField("fldJieGtJ9gmUKdll", People)
    Klippare = fields.LinkField("fldbEXQbGNjFi4bzI", People)
    Resten = fields.LinkField("fldSrxR4SLDGJZ6Hq", People)
    producent = fields.LinkField("fldPfJgkTgTmQxgj3", People)
    leverans_nummer = fields.IntegerField("fldlXvqQJi31guMWY")
    kund = fields.LinkField("fldYGBNxXLwxy6Ej1", Kund)
    Svanis = fields.CheckboxField("fldlj8nYVzBfeYMe2")
    Typ = fields.TextField("fldPW8EUxYhNRFUCg")
    Adress = fields.LinkField("fldCOxzZAj9SAFvQK", Adressbok)
    beställare = fields.LinkField("fldMYoZLCVZGBlAjA", Bestallare)
    input_id = fields.TextField("fldCjxYHX7V1Av2mq")
    # made_by = fields.LinkField("fldHAQqd9ApYknmUL", input_data)
    post_deadline = fields.DatetimeField("fldXUpUZC5Ng6eXM2")
    All_personal = fields.LinkField("fldGx5cRPG7o69xk8", People)
    slutkund_temp = fields.LinkField("fldCJ9Qupbuvr7uWr", Slutkund)
    role_format = fields.TextField("fldDAwoL2Sd1bKW3N")
    extra_namn = fields.TextField("fldAa4QimQWLXEosO")
    ob = fields.TextField("fldCcecFWkEr6QMIS")
    Kommentar_från_formulär = fields.TextField("fldp4H3xsgi2puMNO")

    class Meta:
        base_id = os.environ["base_id"]
        api_key = os.environ["api_key"]
        table_name = "tbl2JdL4S1Wl1jhdB"


class input_data(Model):
    gigNamn = fields.TextField("fld2IwCPbq7b8Yjik")
    inventarie_test = fields.CheckboxField("fld3h45ECYFHRGbjx")
    knas = fields.CheckboxField("fldR4m0lNxedavedX")
    slutkund = fields.LinkField("fldS7HP5BJ5hh59VQ", Slutkund)
    ny_slutkund_bool = fields.CheckboxField("flde631gn95W5F1tW")
    ny_slutkund = fields.TextField("fld8lpADzHqkwU7tU")
    uppdateraProjekt = fields.LinkField("fldG8glSnyO1voEt0", Leverans)
    prylPaket = fields.LinkField("flddagkZF2A0fGIUF", Paket)
    extraPrylar = fields.LinkField("fldSee4Tb6eABK6qY", Prylar)
    antalPaket = fields.TextField("fldMuiKyy5M4Ic36o")
    antalPrylar = fields.TextField("fldKPZXPgaAGvypFZ")
    Svanis = fields.CheckboxField("fldgJioVMIGqVqVDE")
    extraPersonal = fields.FloatField("fldgdbo04e5daul7r")
    hyrKostnad = fields.FloatField("fldqpTwSSKNDL9fGT")
    börja_datum = fields.DatetimeField("fldgIVyUu8kci0haJ")
    sluta_datum = fields.DatetimeField("fldBRV7PMCSYPemuP")
    tid_för_gig = fields.TextField("fldg8mwbEEcEtsuFy")
    riggDag = fields.DatetimeField("fldK7uLbgb5mNC18I")
    uppdateraa = fields.CheckboxField("fldkZgi81M0SoCbIi")
    projektledare = fields.LinkField("fldMpFwH617TIYHkk", People)
    producent = fields.LinkField("fld2Q7WAm4q5MaLSO", People)
    post_text = fields.CheckboxField("fldQJP25CrDQdZGRg")
    Textning_minuter = fields.IntegerField("fldPxGMqLTl0BYZms")
    Frilans = fields.LinkField("fldnH3dsbRixSXDVI", People)
    Projekt_typ = fields.TextField("fldFpABlroJj4muC9")
    Adress = fields.TextField("fldUrjpo5l48QCBHT")
    beställare = fields.LinkField("fldocj6Gxh5Ss1Ko2", Bestallare)
    Projekt = fields.LinkField("fldLoNFu0HfYXlEII", People)
    post_deadline = fields.DatetimeField("fldYkABLiPlDItyyO")
    ny_beställare_bool = fields.CheckboxField("fldX2fFwPDu51Msrn")
    ny_kund_bool = fields.CheckboxField("fldBDyoWf3IZygI3G")
    ny_kund = fields.TextField("flde22WSFwNXuWsBf")
    ny_beställare = fields.TextField("fldoTuaIttzRWDPYy")
    existerande_adress = fields.LinkField("fldKr9l8iJym15vnv", Adressbok)
    projekt_timmar = fields.IntegerField("fldQibfzkvf2pPPsK")
    Bildproducent = fields.LinkField("fld2bU8lAGsjDR0rd", People)
    Fotograf = fields.LinkField("fldGhbhWOU144JENx", People)
    Ljudtekniker = fields.LinkField("fldPG0KxCs1KQZlat", People)
    Ljustekniker = fields.LinkField("fldGNHurJz9o0r00q", People)
    Grafikproducent = fields.LinkField("fldzs3apF4e6l5e1k", People)
    Animatör = fields.LinkField("fldZR7VIgfSWvRgxm", People)
    Körproducent = fields.LinkField("fldt604xRNZmtplgE", People)
    Innehållsproducent = fields.LinkField("fldKY31C9MOjFoVYa", People)
    Scenmästare = fields.LinkField("fldzmnvyBqodXYEb7", People)
    Tekniskt_ansvarig = fields.LinkField("fld9XX0CYmGJTRNWq", People)
    Mer_personal = fields.LinkField("fld8CHNj4LD1ErSpm", People)
    Anteckning = fields.TextField("fld77P6NIqwO6sWTf")
    extra_name = fields.TextField("fldM7myaiGPyiHqNc")
    boka_personal = fields.CheckboxField("fldsNgx88aUVIqazE")
    Klippare = fields.LinkField("fldq8fLKuhlHveZ2e", People)
    koppla_till_kund = fields.LinkField("fldRhcdwudTuW9bT6", Kund)
    getin_getout = fields.TextField("fldgCwZHHkIj5cxFS")
    nytt_projekt = fields.CheckboxField("fldB06TMygWWfyiyM")
    Output_table = fields.LinkField("fldKy8eQZejPBt6ta", Leverans)
    Projekt_copy = fields.TextField("fldkZGenkv1vE5mp7")
    Leveranser_copy = fields.TextField("fld8E15CzhDcbYvI4")
    Leveranser_copy = fields.TextField("fldc4TYAbX80h3XIe")
    Börja_tidigare = fields.FloatField("fldxANgmnX6XuDIwN")

    class Meta:
        base_id = os.environ["base_id"]
        api_key = os.environ["api_key"]
        table_name = "tblzLH9vrPOvkmOrh"


class Inventarie(Model):
    based_on = fields.LinkField("fld486RrDoIslIVdY", Prylar)
    leverans = fields.LinkField("fldjDT2LWD8NUxXrP", Leverans)
    amount = fields.IntegerField("fldNjNPsb1Kx7vcdP")

    class Meta:
        base_id = os.environ["base_id"]
        api_key = os.environ["api_key"]
        table_name = "tblHV8tzp8C7kdKCN"
