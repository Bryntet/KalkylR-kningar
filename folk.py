import json

class Folk():

    def __init__(self):
        with open("folk.json", "r") as f:
            json_data = json.load(f)
            self.folk_dictionary = {x: Person(json_data[x]) for x in json_data}

    def get_person(self, id: str):
        """Get person object

        Args:
            id (str): The record id from airtable

        Returns:
            Object: Person
        """
        return self.folk_dictionary[id]

    def lowest_cost(self, task: str, timmar: int):
        """Returns person with lowest cost

        Args:
            task (str): The task the person needs to be capable of doing
            timmar (int): Hours needed to complete the task

        Returns:
            Object: Person
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
    
    def total_cost(self, personer: list, timmar: int):
        """Make list of people into a total cost

        Args:
            personer (list): record ids for the people
            timmar (int): hours per person

        Returns:
            int: Money
        """
        total = 0
        for person in personer:
            total += self.get_person(person).get_cost(timmar)
            
        return total



class Person():

    def __init__(self, information):
        self.name = information['Name']
        self.available_tasks = information['Kan göra dessa uppgifter']
        self.id = information['id']
        if information['hyrkostnad'] is not None:
            self.hyrkostnad = information['hyrkostnad']
        else:
            self.hyrkostnad = False
        if information['timpeng'] is not None:
            self.timpeng = information['timpeng']
        else:
            self.timpeng = False
        if information['timpeng efter'] is not None:
            self.timpeng_after_time = information['timpeng efter'] / 60 / 60
        else:
            self.timpeng_after_time = False

    def get_cost(self, timmar: int):
        """Returns the money that the person should get for the time spent

        Args:
            timmar (int): amount of hours spent working

        Returns:
            int: Money
        """
        total = 0
        if self.hyrkostnad:
            total += self.hyrkostnad
        if self.timpeng_after_time:
            total += (timmar - self.timpeng_after_time) * self.timpeng
        elif self.timpeng:
            total += self.timpeng * timmar

        return total

    def can_do(self, task):
        return task in self.available_tasks


test = Folk()
pengar = test.get_person('rectoY83gJUuy9D3E').get_cost(3)
person, minst_pengar = test.lowest_cost('Bildproducent', 5)
total = test.total_cost(['rectoY83gJUuy9D3E', 'rectoY83gJUuy9D3E'], 5)
breakpoint()