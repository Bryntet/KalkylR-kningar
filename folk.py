import json


class Folk():

    def __init__(self, lön, timpris, hyr_multi):

        with open("folk.json", "r") as f:
            json_data = json.load(f)
            self.folk_dictionary = {x: Person(json_data[x], lön, timpris, hyr_multi) for x in json_data}

    def get_person(self, id: str):
        """Get person object

        Args:
            id (str): The record id from airtable

        Returns:
            class: Person
        """
        return self.folk_dictionary[id]

    def lowest_cost(self, task: str, timmar: int):
        """Returns person with lowest cost

        Args:
            task (str): The task the person needs to be capable of doing
            timmar (int): Hours needed to complete the task

        Returns:
            class: Person
            int: The cost
        """
        candidates = {}
        for person in {self.folk_dictionary[x] for x in self.folk_dictionary}:
            if person.can_do(task):
                candidates[person.id] = person.get_cost(timmar)
        v = list(candidates.values())
        k = list(candidates.keys())

        # Get id of person with lowest cost and then get person object
        return self.folk_dictionary[k[v.index(min(v))]], min(v)

    def total_cost(self, personer: list, timmar: dict, levande_video: bool):
        """Make list of people into a total cost

        Args:
            personer (list): record ids for the people
            timmar (int): hours per person
            levande_video (bool, optional): If false, ignore all levande_video people if true, ignore all frilans

        Returns:
            int: Money
            int: Hours
        """



        total_kostnad = 0
        tim_total = 0
        total_pris = 0
        for person in personer:
            if self.get_person(person).levande_video == levande_video:
                temp_total_kostnad, temp_total_pris, temp_tim = self.get_person(person).get_cost(timmar)
                total_kostnad += temp_total_kostnad
                tim_total += temp_tim
                total_pris += temp_total_pris
                

        return total_kostnad, total_pris, tim_total


class Person():

    def __init__(self, information, lv_timpeng, lv_timpris, hyr_multi=0.2):
        """Person object

        Args:
            information (dict): dict with information from airtable
            lv_timpeng (int): The Levande Video cost per hour for labour
        """
        self.name = information['Name']
        self.available_tasks = information['Kan göra dessa uppgifter']
        self.id = information['id']
        self.levande_video = information['Levande Video']
        self.hyr_multi = hyr_multi
        if self.levande_video:
            self.frilans = False
            self.hyrkostnad = False
            self.tim_kostnad = lv_timpeng
            self.tim_kostnad_after_time = False
            self.timpris = lv_timpris
        else:
            self.frilans = True

            if information['hyrkostnad'] is not None:
                self.hyrkostnad = information['hyrkostnad']
            else:
                self.hyrkostnad = False

            if information['timpeng'] is not None:
                self.tim_kostnad = information['timpeng']
                
            else:
                self.tim_kostnad = False

            if information['timpeng efter'] is not None:
                self.tim_kostnad_after_time = information['timpeng efter'] / 60 / 60
            else:
                self.tim_kostnad_after_time = False

    def get_cost(self, timmar: dict):
        """Returns the money that the person should get for the time spent

        Args:
            timmar (dict): dict with type of hours

        Returns:
            int: Money
        """
        total_kostnad = 0
        if self.levande_video:
            tim_total = timmar['gig'] + timmar['rigg'] + timmar['proj'] + timmar['res']
            total_kostnad = tim_total * self.tim_kostnad
            total_pris = tim_total * self.timpris
        else:
            tim_total = timmar['gig'] + timmar['rigg']

            if self.hyrkostnad:
                total_kostnad += self.hyrkostnad
            if self.tim_kostnad_after_time:
                total_kostnad += (tim_total - self.tim_kostnad_after_time) * self.tim_kostnad
                total_pris = total_kostnad * (1+self.hyr_multi)
            elif self.tim_kostnad:
                total_kostnad += self.tim_kostnad * tim_total
                total_pris = total_kostnad * (1+self.hyr_multi)

        return total_kostnad, total_pris, tim_total

    def can_do(self, task):
        return task in self.available_tasks
