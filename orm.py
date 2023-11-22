import math
import os
import re
from typing import TypeVar, Type, List

import pyairtable
from pyairtable import metadata
from pyairtable.orm import Model, fields

LinkSelf = fields.LinkSelf

api = pyairtable.Api(os.environ['api_key'])
base = api.base(os.environ['base_id'])

table_schema = metadata.get_base_schema(base)

config = {
    record['fields']['fldkXGyb94cqSXzhU']: record['fields']['fldVAEPybe7cvFFrS']
    for record in base.table("tbloHfNdwu6Adw97g").all(return_fields_by_field_id=True)
}

ORMType = TypeVar('ORMType', bound=Model)


def get_all_in_orm(orm: Type[ORMType]) -> List[ORMType]:
    return orm().all(return_fields_by_field_id=True)


def record_to_orm(table, record_input):
    new_ORM = table()
    new_ORM.id = record_input['id']
    tbl_flds = None
    for table_ in table_schema['tables']:
        if table_['id'] == table().Meta.table_name:
            tbl_flds = table_['fields']

    if tbl_flds is not None:
        for field_name, value in record_input['fields'].items():
            for field_id, name in [(x['id'], x['name']) for x in tbl_flds]:
                if field_name == name:
                    new_ORM.__dict__['_fields'][field_id] = value
    return new_ORM


class Prylar(Model):
    name = fields.TextField("fldAakG5Ntk1Mro4S")
    # noinspection PyArgumentList
    pris = fields.FloatField("fld1qKXF28Qz2pJG2")
    # noinspection PyArgumentList
    in_pris = fields.IntegerField("fldgY78pJgbgBi4Dy")
    lifespan = fields.SelectField("fldwG40TFkeqHVMYG")
    # noinspection PyArgumentList
    antal_inventarie = fields.FloatField("fldO8AaLRqgoQtmAz")
    hide_from_calendar = fields.CheckboxField("fldb0Hgi9WB3OD8mI")

    def make_mult(self):
        mult = 100 + (config['livsLängdSteg'] * 3)
        if self.lifespan is None:
            self.lifespan = "3"
        mult -= int(self.lifespan) * config['livsLängdSteg']
        mult /= 100
        return mult

    def calc_pris(self):
        self.mult = self.make_mult()
        if self.in_pris is None:
            self.in_pris = 0
        self.pris = (math.floor((self.in_pris * config["prylKostnadMulti"]) / 10 * self.mult) * 10) * 1.0

    def _update_all(self):
        prylar = self.all(return_fields_by_field_id=True)
        prylar_list = []
        for pryl in prylar:
            pryl.calc_pris()
            prylar_list.append(pryl)
        return super().batch_save(prylar_list)

    class Meta:
        base_id = os.environ["base_id"]
        api_key = os.environ["api_key"]
        table_name = "tblsxui7L2zsDDdiy"
        timeout = (5, 5)
        typecast = True


# noinspection PyTypeChecker
class Paket(Model):
    # noinspection PyArgumentList
    name = fields.TextField("fld3ec1hcB3LK56R7")
    # noinspection PyArgumentList
    pris = fields.FloatField("fld0tl6Outn8f6lEj")
    prylar = fields.LinkField("fldGkPJMOquzQGrO9", Prylar)
    paket_i_pryl_paket: fields.LinkField = fields.LinkField("fld1PIcwxpsFkrcYy", fields.LinkSelf, True)
    antal_prylar = fields.TextField("fldUTezg1xtekQBir")
    # noinspection PyArgumentList
    personal = fields.FloatField("fldTTcF0qCx9p8Bz2")
    svanis = fields.CheckboxField("fldp2Il8ITQdFXhVR")
    # noinspection PyArgumentList
    hyra = fields.FloatField("fld8iEEeEjhi9KT3c")
    hide_from_calendar = fields.CheckboxField("fldQqTyRk9wzLd5fC")
    _force_update = False
    amount_list: [str] = []

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
        for pryl, amount in self.get_amount():
            for _ in range(amount):
                pryl_list.append(pryl)

        print(self.paket_i_pryl_paket)
        for paket in self.paket_i_pryl_paket:
            if paket.pris is None:
                paket.fetch()
            pryl_list.extend(paket.get_all_prylar())

        for pryl in pryl_list:
            if pryl.name is None:
                pryl.fetch()
            print(pryl.name, pryl.pris)
        if self.name == "Trekamera G2 [1 personal]" or self.name == "Trekamera Angela G2 [1 personal]":
            print(self.name, self.pris, pryl_list)
        return pryl_list

    def calculate(self):
        self.pris = 0.0
        if self.prylar is not None:
            for pryl, amount in self.get_amount():
                self.pris += pryl.pris * amount
        if self.paket_i_pryl_paket is not None:
            for paket in self.paket_i_pryl_paket:
                print(paket)
                if paket.pris is None:
                    paket.fetch()
                    paket.calculate()
                if paket.pris is not None:
                    self.pris += paket.pris
        if self.hyra is not None and self.pris is not None:
            self.pris += self.hyra

    def _update_all(self, force_update=False):
        self._force_update = force_update
        if self._force_update:
            Prylar()._update_all()
        paket = self.all(return_fields_by_field_id=True)
        amount_of_paket = len(paket)
        paket_list = []
        for idx, p in enumerate(paket):
            p.calculate()
            paket_list.append(p)
            print(paket, round((idx+1) / amount_of_paket * 1000) / 10, "%", p.pris, "KR")
        temp_tups = []

        # for rec_id, paket in self._linked_cache.items():
        #     if isinstance(PaketPaket(), type(paket)):
        #         print(paket)
        #         temp_tups.append((rec_id, paket))

        # for rec_id, paket in temp_tups:
        #     self._linked_cache.pop(rec_id, None)
        return super().batch_save(paket_list)

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
    # noinspection PyArgumentList
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
    conditions_dict: dict[int, dict[str | None, tuple[int, int]]] = {}
    konstant_kostnad = 0
    available_tasks = None
    timpris = 0
    lön_kostnad = 0
    tim_kostnad = 0

    def fix(self):
        if self.name is None:
            self.fetch()
        if self.kan_göra is None:
            self.kan_göra = ""
        self.available_tasks = re.findall(r"\[*'([\w\såäöÅÄÖ]+)']*", self.kan_göra)
        self.kan_göra = ", ".join(self.available_tasks)
        if self.levande_video:
            self.timpris = config["levandeVideoLön"]
            self.lön_kostnad = self.timpris * (config["socialaAvgifter"] + 1)
        else:
            self.make_frilans_costs()

    def make_frilans_costs(self):
        if self.input_string is not None:
            input_string = self.input_string.split("--")

            self.konstant_kostnad = int(input_string[0])

            from typing import List, Tuple, Union

            tuples: List[Tuple[int, int, int, Union[str, None]]] = []

            for s in input_string[1].split("-"):
                parts = s.split("|")
                p1 = parts[0].split(",")
                nums: Tuple[int, int, int] = (int(p1[0]), int(p1[1]), int(p1[2]))
                condition = parts[1] if len(parts) > 1 else None
                tuples.append(nums + (condition, ))

            self.conditions_dict: dict[int, dict[str | None, tuple[int, int]]] = {}

            for fixed_price, timpris_in_tup, hour_p, condition in tuples:
                if hour_p not in self.conditions_dict.keys():
                    self.conditions_dict[hour_p] = {}

                self.conditions_dict[hour_p].update({condition: (fixed_price, timpris_in_tup)})

    def can_do(self, task):
        if self.available_tasks is not None:
            return task in self.available_tasks

    def get_cost(self, timmar: dict[str, int], typ_av_jobb: str | None = None):
        """Returns the money that the person should get for the time spent

        Args:
            timmar (dict): dict with type of hours

        Returns:
            int: Money
        """

        if self.levande_video:  # TODO kan finnas stora problem här
            tim_total = timmar['gig'] + timmar['rigg'] + timmar['proj'] + timmar['res']
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
        self.uträkning = [FrilansAccounting(gissad_kostnad=self.kostnad * 1.0)]
        self.uträkning[0].save()
        self.save()
        return self.uträkning[0]

    class Meta:
        base_id = os.environ["base_id"]
        api_key = os.environ["api_key"]
        table_name = "tblxHIlUSQ8VxEGts"


class Tidrapport(Model):
    person = fields.TextField("fld0rfqy45K5IOb34")
    datum = fields.DateField("fldZd6hRrxR5T0KL2")
    # noinspection PyArgumentList
    tid = fields.FloatField("fldzCupBWoGl6cgR8")
    # noinspection PyArgumentList
    start_tid = fields.FloatField("fldS7uDn92PtAEYCR")
    o_b = fields.TextField("fld5jc0S4rQALPsvY")
    kommentar = fields.TextField("fldnpajIJz62nDCk8")
    # noinspection PyArgumentList
    mil = fields.FloatField("fldcL3qksoVqN9le6")
    is_default = fields.CheckboxField("fldzupNeSCkJ0hMcl")
    månad = fields.TextField("fldWhREtVWvRThp4b")
    unused = fields.CheckboxField("fldcbw9qh1f5Aq8XG")
    # noinspection PyArgumentList
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
    # noinspection PyArgumentList
    time_bike = fields.IntegerField("fldcrcoZE5v7czRrg")
    # noinspection PyArgumentList
    time_car = fields.IntegerField("fldTr4mYBAha7sXhZ")
    transport_type = fields.TextField("fld4xpwxz0lnQdphA")
    kund = fields.LinkField("fldHH4DFi1ES93saa", Kund)
    # noinspection PyArgumentList
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
    # noinspection PyArgumentList
    getin = fields.IntegerField("fldITTqANmwPUjYuC")
    # noinspection PyArgumentList
    getout = fields.IntegerField("fldAnBswzCzNt7OFs")
    # noinspection PyArgumentList
    program_start = fields.IntegerField("fldDVxfuTkDruHHL8")
    # noinspection PyArgumentList
    program_slut = fields.IntegerField("flddD7XrPVHYHIPST")
    datum = fields.DateField("fld81rwHaQu7eRx53")
    status = fields.TextField("fldUrrqRZBsVLxxx4")
    kommentar_till_frilans = fields.TextField("fldK5zcWy7mVF47qe")
    grejer = fields.TextField("fld0ha80TlVUoU3LG")
    packlista__keep = fields.TextField("fldVAczarHpOYDfWn")
    slides = fields.CheckboxField("fldDhBQk3opw1CSgk")
    fakturareferens = fields.TextField("fldSEEzRXfRgwKKl2")
    skicka_mejl = fields.CheckboxField("fld7w7Rt5T1vVhzXb")
    # noinspection PyArgumentList
    actual_getin = fields.IntegerField("fldSQcKggYPFHtEAB")
    # noinspection PyArgumentList
    åka_från_svanis = fields.IntegerField("fldi5mO5lix7abnXm")
    # noinspection PyArgumentList
    komma_tillbaka_till_svanis = fields.IntegerField("flddKPdxarm5UYnZm")
    calendar_description = fields.TextField("fldeTVUkgCro8oAIg")
    # noinspection PyArgumentList
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
    # noinspection PyArgumentList
    egen_getin = fields.FloatField("fldnz9NbGRgz9bFBT")
    bara_riggtid = fields.CheckboxField("fldEmgb8XCtjGlk3z")
    rigg_dagen_innan = fields.CheckboxField("fldZ8orE83xtYmSkM")
    # noinspection PyArgumentList
    m_getin = fields.FloatField("fld6F3xuRadz07hyv")
    # noinspection PyArgumentList
    m_getout = fields.FloatField("fldRxrXmAiZBKO4cu")
    # dagen_innan_rigg = fields.LinkField("fldYjafIh96hI3pTe", )
    frilans_uträkningar = fields.LinkField("flds3BC39ufa1eTVc", FrilansAccounting)
    # noinspection PyArgumentList
    extra_rigg = fields.FloatField("fldPLMeJSbypPygtK")
    # noinspection PyArgumentList
    i_d = fields.IntegerField("fldnOyMoIQlfEJNXb")
    fakturanummer = fields.TextField("fldj3L72EeGGRE0gV")
    betalningsdatum = fields.DateField("fldjsKIIPTOhfg7gW")
    # noinspection PyArgumentList
    program_stop_hidden = fields.FloatField("fldpW1yaKniipOP0z")
    # noinspection PyArgumentList
    program_start_hidden = fields.FloatField("fldZhrBxTQ1azrdEz")
    projekt_typ = fields.TextField("fldjq2WoRhwPnO2xE")
    leverans_rid = fields.TextField("fldJunVGOofzOVrov")

    class Meta:
        base_id = os.environ["base_id"]
        api_key = os.environ["api_key"]
        table_name = "tbllVOQa9PrKax1PY"


class EdvinsProblem(Model):
    class Meta:
        base_id = os.environ["base_id"]
        api_key = os.environ["api_key"]
        table_name = "tblleX4SfjkO9DyFR"


class Leverans(Model):
    projekt_kalender = fields.LinkField("fld8sMBfKU73Rt5RB", Projektkalender)
    link_to_update = fields.TextField("fldnAUE87gCkyzUW7")
    link_to_copy = fields.TextField("fldkVvmHIDCofPTxE")
    # noinspection PyArgumentList
    eget_pris = fields.IntegerField("fldh6JAFQjK5RMDPT")
    name = fields.TextField("fldeZo8wMi9C8D78j")
    # noinspection PyArgumentList
    pris = fields.FloatField("fld0O9MGtVYeB87DC")
    # noinspection PyArgumentList
    personal = fields.FloatField("fldGj04MBtd7yVS6y")
    # noinspection PyArgumentList
    extra_personal = fields.FloatField("flds76lS0HTW380WJ")
    # noinspection PyArgumentList
    projekt_timmar = fields.IntegerField("fldrztHjZrLDjky6q")
    # noinspection PyArgumentList
    rigg_timmar = fields.IntegerField("fldVfzIAGpa49C8qy")
    # noinspection PyArgumentList
    pryl_pris = fields.FloatField("fldnQYR5MbklAQKSU")
    pryl_paket = fields.LinkField("fldrUHtmGbW4OTX8Z", Paket)
    extra_prylar = fields.LinkField("fldIt8Y4P3xSP5xxG", Prylar)
    antal_paket = fields.TextField("fldqnN89906OtOxJC")
    antal_prylar = fields.TextField("fldwLzWn0LXYpOz4z")
    projekt_kanban = fields.TextField("fld5Ba3wtFv6PvDW6")
    projekt = fields.LinkField("fldXdY47lGYDUFIge", Projekt)
    börja_datum = fields.DateField("fldsJHqZu5eM08Kki")
    sluta_datum = fields.DateField("fldfBtMD4wSQT1ikA")
    # noinspection PyArgumentList
    dagar = fields.IntegerField("fldTxuAKtqGenuEzd")
    packlista = fields.TextField("fldninb2sH5xg2rdf")
    # noinspection PyArgumentList
    restid = fields.IntegerField("fldJCj4KjK2I8RdsG")
    # noinspection PyArgumentList
    projekt_tid = fields.IntegerField("fldW3EJf2n13tg2aC")
    # noinspection PyArgumentList
    dag_längd = fields.FloatField("fldEcIo4yzJQ9sRRb")
    # noinspection PyArgumentList
    slit_kostnad = fields.FloatField("fldarGhCnL33DTvPD")
    # noinspection PyArgumentList
    pryl_fonden = fields.FloatField("fldv4MgeBeziiuRgX")
    # noinspection PyArgumentList
    hyrthings = fields.FloatField("fldgO3uhxa7enwZ8I")
    # noinspection PyArgumentList
    avkast_without_pris = fields.FloatField("fldFQjYyG5LGQnYPU")
    # noinspection PyArgumentList
    avkast2 = fields.FloatField("fldnrs1UnBqz2I8Bt")
    # noinspection PyArgumentList
    frilanstimmar = fields.FloatField("fldKunOK7Gpqx3x77")
    frilans = fields.LinkField("fld5dISuz2dXpyFWl", Person)
    bildproducent = fields.LinkField("flduzo0PJJRBF8TlT", Person)
    fotograf = fields.LinkField("fldb0SgazCjDUGJK9", Person)
    ljudtekniker = fields.LinkField("fldXo5Mr0lkWoUqyk", Person)
    ljustekniker = fields.LinkField("fld137CDZNCBJVGu6", Person)
    grafikproducent = fields.LinkField("fldIdXKDXXnPJNtjK", Person)
    animatör = fields.LinkField("fldB87dsAvgR2s5fG", Person)
    körproducent = fields.LinkField("fldn8ieh409MItTAC", Person)
    innehållsproducent = fields.LinkField("fldzosWR8ODEpyR0F", Person)
    scenmästare = fields.LinkField("fldm9REcfR7tQdf50", Person)
    tekniskt_ansvarig = fields.LinkField("fldJieGtJ9gmUKdll", Person)
    klippare = fields.LinkField("fldbEXQbGNjFi4bzI", Person)
    resten = fields.LinkField("fldSrxR4SLDGJZ6Hq", Person)
    producent = fields.LinkField("fldPfJgkTgTmQxgj3", Person)
    projektledare = fields.LinkField("fld4ALH1wr3eoi1wj", Person)
    latest_added = fields.CheckboxField("fldVW1DEIYPH0fcUG")
    status = fields.TextField("fldWbvJbz9N20yFww")
    # noinspection PyArgumentList
    leverans_nummer = fields.IntegerField("fldlXvqQJi31guMWY")
    kund = fields.LinkField("fldYGBNxXLwxy6Ej1", Kund)
    svanis = fields.CheckboxField("fldlj8nYVzBfeYMe2")
    typ = fields.TextField("fldPW8EUxYhNRFUCg")
    adress = fields.LinkField("fldCOxzZAj9SAFvQK", Adressbok)
    beställare = fields.LinkField("fldMYoZLCVZGBlAjA", Bestallare)
    input_id = fields.TextField("fldCjxYHX7V1Av2mq")
    frilans_uträkningar = fields.LinkField("fldtDfWE1Wj7jXEN9", FrilansAccounting)
    tidrapport = fields.LinkField("flduRCHi8EEYlsA4B", Tidrapport)
    # made_by = fields.LinkField("fldHAQqd9ApYknmUL", input_data)
    post_deadline = fields.DatetimeField("fldXUpUZC5Ng6eXM2")
    all_personal = fields.LinkField("fldGx5cRPG7o69xk8", Person)
    slutkund_temp = fields.LinkField("fldCJ9Qupbuvr7uWr", Slutkund)
    role_format = fields.TextField("fldDAwoL2Sd1bKW3N")
    extra_namn = fields.TextField("fldAa4QimQWLXEosO")
    ob = fields.TextField("fldCcecFWkEr6QMIS")
    kommentar_från_formulär = fields.TextField("fldp4H3xsgi2puMNO")
    # noinspection PyArgumentList
    rabatt = fields.FloatField("fldQw9OqKfVWNrDru")
    equipment_url = fields.TextField("fldecfG6DnmrybU1X")
    edvs_probs = fields.LinkField("fldAkqW8feXXld8ED", EdvinsProblem)
    # noinspection PyArgumentList
    personal_kostnad = fields.FloatField("fldSLwsJFWFdyVThg")
    personal_pris = 0

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
    # noinspection PyArgumentList
    extraPersonal = fields.FloatField("fldgdbo04e5daul7r")
    # noinspection PyArgumentList
    hyrKostnad = fields.FloatField("fldqpTwSSKNDL9fGT")
    börja_datum = fields.DatetimeField("fldWI184kPDtbd76h")
    sluta_datum = fields.DatetimeField("fldBRV7PMCSYPemuP")
    tid_för_gig = fields.TextField("fldg8mwbEEcEtsuFy")
    riggDag = fields.DatetimeField("fldK7uLbgb5mNC18I")
    uppdateraa = fields.CheckboxField("fldkZgi81M0SoCbIi")
    projektledare = fields.LinkField("fldMpFwH617TIYHkk", Person)
    producent = fields.LinkField("fld2Q7WAm4q5MaLSO", Person)
    post_text = fields.CheckboxField("fldQJP25CrDQdZGRg")
    # noinspection PyArgumentList
    Textning_minuter = fields.IntegerField("fldPxGMqLTl0BYZms")
    Frilans = fields.LinkField("fldnH3dsbRixSXDVI", Person)
    Projekt_typ = fields.TextField("fldFpABlroJj4muC9")
    Adress = fields.TextField("fldUrjpo5l48QCBHT")
    beställare = fields.LinkField("fldocj6Gxh5Ss1Ko2", Bestallare)
    Projekt = fields.LinkField("fldLoNFu0HfYXlEII", Projekt)
    post_deadline = fields.DatetimeField("fldYkABLiPlDItyyO")
    ny_beställare_bool = fields.CheckboxField("fldX2fFwPDu51Msrn")
    ny_kund_bool = fields.CheckboxField("fldBDyoWf3IZygI3G")
    ny_kund = fields.TextField("flde22WSFwNXuWsBf")
    ny_beställare = fields.TextField("fldoTuaIttzRWDPYy")
    existerande_adress = fields.LinkField("fldKr9l8iJym15vnv", Adressbok)
    # noinspection PyArgumentList
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
    _ = fields.TextField("fld8E15CzhDcbYvI4")  # Leveranser_copy knas
    _ = fields.TextField("fldc4TYAbX80h3XIe")  # |==================|
    # noinspection PyArgumentList
    Börja_tidigare = fields.FloatField("fldxANgmnX6XuDIwN")
    # noinspection PyArgumentList
    special_rigg = fields.IntegerField("fld9Blpuyi40ZI4YR")
    # noinspection PyArgumentList
    rigg_timmar_spec = fields.FloatField("fldnnOlN8Z9opg4eD")

    class Meta:
        base_id = os.environ["base_id"]
        api_key = os.environ["api_key"]
        table_name = "tblzLH9vrPOvkmOrh"


class Inventarie(Model):
    based_on = fields.LinkField("fld486RrDoIslIVdY", Prylar)
    leverans = fields.LinkField("fldjDT2LWD8NUxXrP", Leverans)
    # noinspection PyArgumentList
    amount = fields.IntegerField("fldNjNPsb1Kx7vcdP")

    class Meta:
        base_id = os.environ["base_id"]
        api_key = os.environ["api_key"]
        table_name = "tblHV8tzp8C7kdKCN"


if __name__ == "__main__":
    Paket()._update_all(True)
