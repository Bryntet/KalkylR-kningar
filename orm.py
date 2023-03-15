from pyairtable.orm import Model, fields
from pyairtable import metadata, Base
import os
import math
import time
import json
base = Base(os.environ['api_key'], os.environ['base_id'])


table_schema = metadata.get_base_schema(base)
config = {record['fields']['fldkXGyb94cqSXzhU']: record['fields']['fldVAEPybe7cvFFrS'] for record in base.get_table("tbloHfNdwu6Adw97g").all(return_fields_by_field_id=True)}

def get_all_in_orm(orm):
    return [orm().from_record(record) for record in orm().all(return_fields_by_field_id=True)]

def record_to_orm(table, record_input):
    new_ORM = table()
    new_ORM.id = record_input['id']

    for table_ in table_schema['tables']:
        if table_['id'] == table().Meta.table_name:
            tbl_flds = table_['fields']

    for field_name, value in record_input['fields'].items():
        for field_id, name in [(x['id'], x['name']) for x in tbl_flds]:
            if field_name == name:
                new_ORM.__dict__['_fields'][field_id] = value
    return new_ORM



class Prylar(Model):
    name = fields.TextField("fldAakG5Ntk1Mro4S")
    pris = fields.FloatField("fld1qKXF28Qz2pJG2")
    in_pris = fields.IntegerField("fldgY78pJgbgBi4Dy")
    livs_längd = fields.TextField("fldwG40TFkeqHVMYG")
    antal_inventarie = fields.FloatField("fldO8AaLRqgoQtmAz")
    hide_from_calendar = fields.CheckboxField("fldb0Hgi9WB3OD8mI")

    def make_mult(self):
        mult = 100 + (config['livsLängdSteg'] * 3)
        mult -= int(self.livs_längd) * config['livsLängdSteg']
        mult /= 100
        return mult


    def calc_pris(self):
        self.mult = self.make_mult()
        self.pris = (
            math.floor((self.in_pris * config["prylKostnadMulti"]) /
                       10 * self.mult) * 10
        ) * 1.0

    def _update_all(self):
        prylar = self.all(return_fields_by_field_id=True)
        prylar_list = []
        for pryl in prylar:
            pryl = self.from_record(pryl)
            pryl.calc_pris()
            prylar_list.append(pryl.to_record())
        return self.get_table().batch_update(prylar_list, return_fields_by_field_id=True)



    class Meta:
        base_id = os.environ["base_id"]
        api_key = os.environ["api_key"]
        table_name = "tblsxui7L2zsDDdiy"




class PaketPaket(Model):
    name = fields.TextField("fld3ec1hcB3LK56R7")
    pris = fields.FloatField("fld0tl6Outn8f6lEj")
    prylar = fields.LinkField("fldGkPJMOquzQGrO9", Prylar)
    antal_prylar = fields.TextField("fldUTezg1xtekQBir")
    Personal = fields.FloatField("fldTTcF0qCx9p8Bz2")
    Svanis = fields.CheckboxField("fldp2Il8ITQdFXhVR")
    hyra = fields.FloatField("fld8iEEeEjhi9KT3c")
    hide_from_calendar = fields.CheckboxField("fldQqTyRk9wzLd5fC")

    def get_amount(self) -> list[tuple[Prylar, int]]:
        if self.antal_prylar is None:
            self.antal_prylar = ""
        self.amount_list = self.antal_prylar.split(",")
        output = []
        if self.prylar is not None:
            for idx, pryl in enumerate(self.prylar):
                if idx < len(self.amount_list) and self.amount_list[idx] != "":
                    output.append((pryl, int(self.amount_list[idx])))
                else:
                    output.append((pryl, 1))
        return output

    def get_all_prylar(self):
        pryl_list = []
        if self.prylar is not None:
            for pryl, amount in self.get_amount():
                for _ in range(amount):
                    pryl_list.append(pryl)
        return pryl_list

    def calculate(self):
        self.pris = 0.0
        for pryl, amount in self.get_amount():

            if pryl.pris is None:
                pryl.fetch()
                if pryl.pris is None:
                    pryl.calc_pris()
                    pryl.save()
            assert pryl.pris is not None
            self.pris += pryl.pris * amount
        if self.hyra is not None:
            self.pris += self.hyra

    class Meta:
        base_id = os.environ["base_id"]
        api_key = os.environ["api_key"]
        table_name = "tblVThDQ16pIEkY9m"

class Paket(Model):

    name = fields.TextField("fld3ec1hcB3LK56R7")
    pris = fields.FloatField("fld0tl6Outn8f6lEj")
    paket_i_pryl_paket = fields.LinkField("fld1PIcwxpsFkrcYy", PaketPaket)
    prylar = fields.LinkField("fldGkPJMOquzQGrO9", Prylar)
    antal_prylar = fields.TextField("fldUTezg1xtekQBir")
    personal = fields.FloatField("fldTTcF0qCx9p8Bz2")
    svanis = fields.CheckboxField("fldp2Il8ITQdFXhVR")
    hyra = fields.FloatField("fld8iEEeEjhi9KT3c")
    hide_from_calendar = fields.CheckboxField("fldQqTyRk9wzLd5fC")
    _force_update = False
    def get_amount(self):
        if self.antal_prylar is None:
            self.antal_prylar = ""
        self.amount_list = self.antal_prylar.split(",")
        output = []

        for idx, pryl in enumerate(self.prylar):
            if pryl.pris is None:
                pryl.fetch()
                if pryl.pris is None or self._force_update:
                    pryl.calc_pris()
                    pryl.save()
            if idx < len(self.amount_list) and self.amount_list[idx] != "":
                output.append((pryl, int(self.amount_list[idx])))
            else:
                output.append((pryl, 1))
        return output

    def get_all_prylar(self):
        pryl_list = []
        if self.prylar is not None:
            for pryl, amount in self.get_amount():
                for _ in range(amount):
                    pryl_list.append(pryl)

        if self.paket_i_pryl_paket is not None:
            for paket in self.paket_i_pryl_paket:
                if paket.pris is None:
                    paket.fetch()
                pryl_list.extend(paket.get_all_prylar())
        for pryl in pryl_list:
            if pryl.name is None:
                pryl.fetch()
            print(pryl.name, pryl.pris)
        print(self.name, self.pris, pryl_list)
        return pryl_list
    def calculate(self):
        self.pris = 0.0
        if self.prylar is not None:
            for pryl, amount in self.get_amount():
                self.pris += pryl.pris * amount
        if self.paket_i_pryl_paket is not None:
            for paket in self.paket_i_pryl_paket:
                if paket.pris is None:
                    paket.fetch()
                    paket.calculate()
                assert type(paket.pris) is float
                self.pris += paket.pris
        if self.hyra is not None:
            self.pris += self.hyra

    def _update_all(self, force_update=False):
        self._force_update = force_update
        if self._force_update:
            Prylar()._update_all()
        paket = self.all(return_fields_by_field_id=True)
        amount_of_paket = len(paket)
        paket_list = []
        for idx, paket in enumerate(paket):
            paket = Paket().from_record(paket)
            paket.calculate()
            paket_list.append(paket.to_record())
            print(round((idx+1)/amount_of_paket*1000)/10, "%", paket.pris, "KR")
        temp_tups = []
        for rec_id, paket in self._linked_cache.items():
            if isinstance(PaketPaket(), type(paket)):
                print(paket)
                temp_tups.append((rec_id, paket))

        for rec_id, paket in temp_tups:
            self._linked_cache.pop(rec_id, None)

        return self.get_table().batch_update(paket_list, return_fields_by_field_id=True)

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

class FrilansAccounting(Model):
    gissad_kostnad = fields.FloatField("fldx8vULV8QQ57Bfq")

    class Meta:
        base_id = os.environ["base_id"]
        api_key = os.environ["api_key"]
        table_name = "tblfUnngvWcn2u2at"




class Person(Model):
    name = fields.TextField("fld6TVIRKXVSBPplt")
    levande_video = fields.CheckboxField("fldbKIKHToEe4oA7x")
    epost = fields.EmailField("fld91TTZnGJBtPESY")
    input_string = fields.TextField("fld8XSSOjSjACYIBy")
    kan_göra = fields.TextField("fld6khXiTavP5xtOc")
    uträkning = fields.LinkField("fldDgH3SedjG0X1bS", FrilansAccounting)

    def fix(self):
        if self.kan_göra is None:
            self.kan_göra = ""
        self.available_tasks = "".join(self.kan_göra[1:-1].split("'")).split(", ")
        if self.levande_video:
            self.timpris = config["levandeVideoLön"]
            self.lön_kostnad = self.timpris * (config["socialaAvgifter"] + 1)
        else:
            self.make_frilans_costs()

    def make_frilans_costs(self):
        if self.input_string is not None:
            input_string = self.input_string.split("--")

            self.konstant_kostnad = int(input_string[0])

            tuples: list[tuple[int, int, int, str|None]] = []  # fixed, timpris, hourly_point, condition
            for s in input_string[1].split("-"):
                if "|" in s:

                    tuples.append(tuple(list(map(int, s.split("|")[0].split(","))) + [s.split("|")[1]]))
                else:
                    tuples.append(tuple(list(map(int, s.split(","))) + [None]))

            self.conditions_dict: dict[int,dict[str|None,tuple[int,int]]] = {}

            for fixed_price, timpris_in_tup, hour_p, condition in tuples:
                if hour_p not in self.conditions_dict.keys():
                    self.conditions_dict[hour_p] = {}

                self.conditions_dict[hour_p].update({condition:(fixed_price, timpris_in_tup)})

    def can_do(self, task):
        return task in self.available_tasks

    def get_cost(self, timmar: dict[str, int], typ_av_jobb: str | None = None):
        """Returns the money that the person should get for the time spent

        Args:
            timmar (dict): dict with type of hours

        Returns:
            int: Money
        """
        total_kostnad = 0
        total_pris = 0
        tim_total = 0
        if self.levande_video:  # TODO kan finnas stora problem här
            tim_total = timmar['gig'] + timmar['rigg'] + timmar[
                'proj'] + timmar['res']
            total_kostnad = tim_total * self.tim_kostnad
            total_pris = tim_total * self.timpris
            return total_kostnad, total_pris, tim_total
        elif self.input_string is not None:

            total_kostnad = self.konstant_kostnad
            tim_total = timmar['gig'] + timmar['rigg']
            counter = 0
            current_hourly = 0

            while counter <= tim_total:
                temp = self.conditions_dict.get(counter, {}).get(typ_av_jobb)
                if temp is not None:
                    total_kostnad += temp[0]
                    current_hourly = temp[1]

                total_kostnad += current_hourly
                counter += 1
            self.kostnad = total_kostnad
            return total_kostnad, tim_total

    def set_frilans_cost(self):
        self.uträkning = [FrilansAccounting(gissad_kostnad=self.kostnad)]
        self.uträkning[0].save()
        self.save()
        return self.uträkning[0].id

    class Meta:
        base_id = os.environ["base_id"]
        api_key = os.environ["api_key"]
        table_name = "tblxHIlUSQ8VxEGts"


class Tidrapport(Model):
    person = fields.TextField("fld0rfqy45K5IOb34")
    datum = fields.DateField("fldZd6hRrxR5T0KL2")
    tid = fields.FloatField("fldzCupBWoGl6cgR8")
    start_tid = fields.FloatField("fldS7uDn92PtAEYCR")
    o_b = fields.TextField("fld5jc0S4rQALPsvY")
    kommentar = fields.TextField("fldnpajIJz62nDCk8")
    mil = fields.FloatField("fldcL3qksoVqN9le6")
    is_default = fields.CheckboxField("fldzupNeSCkJ0hMcl")
    månad = fields.TextField("fldWhREtVWvRThp4b")
    unused = fields.CheckboxField("fldcbw9qh1f5Aq8XG")
    i_d = fields.IntegerField("fldSnPZyBh7cjv8bc")
    month_calculations = fields.TextField("fldvdZjWPhlMAJIfu")
    robot = fields.CheckboxField("fld4JqaTdWzgTwdiC")
    person_link = fields.LinkField("fldT3ZLsQpw9S7Y2h", Person)

    class Meta:
        base_id = os.environ["base_id"]
        api_key = os.environ["api_key"]
        table_name = "tblCxKQvWh3QfVIRg"



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

    name2 = fields.TextField("fldO8TzRQVNgt02qU")
    getin = fields.IntegerField("fldITTqANmwPUjYuC")
    getout = fields.IntegerField("fldAnBswzCzNt7OFs")
    program_start = fields.IntegerField("fldDVxfuTkDruHHL8")
    program_slut = fields.IntegerField("flddD7XrPVHYHIPST")
    datum = fields.DateField("fld81rwHaQu7eRx53")
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
    frilans = fields.LinkField("flddiOloJS1I8BafH", Person)
    packlista_detaljerad = fields.TextField("fldUPh7sIGcpNoDkL")
    projekt_copy = fields.TextField("fldOgfAK8SlXhzKgH")
    leveranser_copy = fields.TextField("fldPRDJlVSSOfccb8")
    projekt_2 = fields.TextField("fldXXtWhMURLywgE3")
    levandevideo = fields.LinkField("fldxTl0TKgoLymqFK", Person)
    frilans_mail = fields.EmailField("flduU5Lyuuf5RGPFC")
    egen_getin = fields.FloatField("fldnz9NbGRgz9bFBT")
    bara_riggtid = fields.CheckboxField("fldEmgb8XCtjGlk3z")
    rigg_dagen_innan = fields.CheckboxField("fldZ8orE83xtYmSkM")
    m_getin = fields.FloatField("fld6F3xuRadz07hyv")
    m_getout = fields.FloatField("fldRxrXmAiZBKO4cu")
    #dagen_innan_rigg = fields.LinkField("fldYjafIh96hI3pTe", )
    frilans_uträkningar = fields.LinkField("flds3BC39ufa1eTVc", FrilansAccounting)
    extra_rigg = fields.FloatField("fldPLMeJSbypPygtK")
    i_d = fields.IntegerField("fldnOyMoIQlfEJNXb")
    fakturanummer = fields.TextField("fldj3L72EeGGRE0gV")
    betalningsdatum = fields.DateField("fldjsKIIPTOhfg7gW")
    program_stop_hidden = fields.FloatField("fldpW1yaKniipOP0z")
    program_start_hidden = fields.FloatField("fldZhrBxTQ1azrdEz")
    projekt_typ = fields.TextField("fldjq2WoRhwPnO2xE")
    leverans_rid = fields.TextField("fldJunVGOofzOVrov")
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
    extraPersonal = fields.FloatField("flds76lS0HTW380WJ")
    Projekt_timmar = fields.IntegerField("fldrztHjZrLDjky6q")
    Rigg_timmar = fields.IntegerField("fldVfzIAGpa49C8qy")
    Pryl_pris = fields.FloatField("fldnQYR5MbklAQKSU")
    prylPaket = fields.LinkField("fldrUHtmGbW4OTX8Z", Paket)
    extraPrylar = fields.LinkField("fldIt8Y4P3xSP5xxG", Prylar)
    antalPaket = fields.TextField("fldqnN89906OtOxJC")
    antalPrylar = fields.TextField("fldwLzWn0LXYpOz4z")
    Projekt_kanban = fields.TextField("fld5Ba3wtFv6PvDW6")
    Projekt = fields.LinkField("fldXdY47lGYDUFIge", Projekt)
    börja_datum = fields.DateField("fldsJHqZu5eM08Kki")
    sluta_datum = fields.DateField("fldfBtMD4wSQT1ikA")
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
    frilans = fields.LinkField("fld5dISuz2dXpyFWl", Person)
    Bildproducent = fields.LinkField("flduzo0PJJRBF8TlT", Person)
    Fotograf = fields.LinkField("fldb0SgazCjDUGJK9", Person)
    Ljudtekniker = fields.LinkField("fldXo5Mr0lkWoUqyk", Person)
    Ljustekniker = fields.LinkField("fld137CDZNCBJVGu6", Person)
    Grafikproducent = fields.LinkField("fldIdXKDXXnPJNtjK", Person)
    Animatör = fields.LinkField("fldB87dsAvgR2s5fG", Person)
    Körproducent = fields.LinkField("fldn8ieh409MItTAC", Person)
    Innehållsproducent = fields.LinkField("fldzosWR8ODEpyR0F", Person)
    Scenmästare = fields.LinkField("fldm9REcfR7tQdf50", Person)
    Tekniskt_ansvarig = fields.LinkField("fldJieGtJ9gmUKdll", Person)
    Klippare = fields.LinkField("fldbEXQbGNjFi4bzI", Person)
    Resten = fields.LinkField("fldSrxR4SLDGJZ6Hq", Person)
    producent = fields.LinkField("fldPfJgkTgTmQxgj3", Person)
    projektledare = fields.LinkField("fld4ALH1wr3eoi1wj", Person)
    latest_added = fields.CheckboxField("fldVW1DEIYPH0fcUG")

    leverans_nummer = fields.IntegerField("fldlXvqQJi31guMWY")
    kund = fields.LinkField("fldYGBNxXLwxy6Ej1", Kund)
    Svanis = fields.CheckboxField("fldlj8nYVzBfeYMe2")
    typ = fields.TextField("fldPW8EUxYhNRFUCg")
    Adress = fields.LinkField("fldCOxzZAj9SAFvQK", Adressbok)
    beställare = fields.LinkField("fldMYoZLCVZGBlAjA", Bestallare)
    input_id = fields.TextField("fldCjxYHX7V1Av2mq")
    frilans_uträkningar = fields.LinkField("fldtDfWE1Wj7jXEN9", FrilansAccounting)
    tidrapport = fields.LinkField("flduRCHi8EEYlsA4B", Tidrapport)
    #made_by = fields.LinkField("fldHAQqd9ApYknmUL", input_data)
    post_deadline = fields.DatetimeField("fldXUpUZC5Ng6eXM2")
    All_personal = fields.LinkField("fldGx5cRPG7o69xk8", Person)
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
    börja_datum = fields.DatetimeField("fldWI184kPDtbd76h")
    sluta_datum = fields.DatetimeField("fldBRV7PMCSYPemuP")
    tid_för_gig = fields.TextField("fldg8mwbEEcEtsuFy")
    riggDag = fields.DatetimeField("fldK7uLbgb5mNC18I")
    uppdateraa = fields.CheckboxField("fldkZgi81M0SoCbIi")
    projektledare = fields.LinkField("fldMpFwH617TIYHkk", Person)
    producent = fields.LinkField("fld2Q7WAm4q5MaLSO", Person)
    post_text = fields.CheckboxField("fldQJP25CrDQdZGRg")
    Textning_minuter = fields.IntegerField("fldPxGMqLTl0BYZms")
    Frilans = fields.LinkField("fldnH3dsbRixSXDVI", Person)
    Projekt_typ = fields.TextField("fldFpABlroJj4muC9")
    Adress = fields.TextField("fldUrjpo5l48QCBHT")
    beställare = fields.LinkField("fldocj6Gxh5Ss1Ko2", Bestallare)
    Projekt = fields.LinkField("fldLoNFu0HfYXlEII", Person)
    post_deadline = fields.DatetimeField("fldYkABLiPlDItyyO")
    ny_beställare_bool = fields.CheckboxField("fldX2fFwPDu51Msrn")
    ny_kund_bool = fields.CheckboxField("fldBDyoWf3IZygI3G")
    ny_kund = fields.TextField("flde22WSFwNXuWsBf")
    ny_beställare = fields.TextField("fldoTuaIttzRWDPYy")
    existerande_adress = fields.LinkField("fldKr9l8iJym15vnv", Adressbok)
    projekt_timmar = fields.IntegerField("fldQibfzkvf2pPPsK")
    Bildproducent = fields.LinkField("fld2bU8lAGsjDR0rd", Person)
    Fotograf = fields.LinkField("fldGhbhWOU144JENx", Person)
    Ljudtekniker = fields.LinkField("fldPG0KxCs1KQZlat", Person)
    Ljustekniker = fields.LinkField("fldGNHurJz9o0r00q", Person)
    Grafikproducent = fields.LinkField("fldzs3apF4e6l5e1k", Person)
    Animatör = fields.LinkField("fldZR7VIgfSWvRgxm", Person)
    Körproducent = fields.LinkField("fldt604xRNZmtplgE", Person)
    Innehållsproducent = fields.LinkField("fldKY31C9MOjFoVYa", Person)
    Scenmästare = fields.LinkField("fldzmnvyBqodXYEb7", Person)
    Tekniskt_ansvarig = fields.LinkField("fld9XX0CYmGJTRNWq", Person)
    Mer_personal = fields.LinkField("fld8CHNj4LD1ErSpm", Person)
    Anteckning = fields.TextField("fld77P6NIqwO6sWTf")
    extra_name = fields.TextField("fldM7myaiGPyiHqNc")
    boka_personal = fields.CheckboxField("fldsNgx88aUVIqazE")
    Klippare = fields.LinkField("fldq8fLKuhlHveZ2e", Person)
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


if __name__ == "__main__":
    Paket()._update_all()