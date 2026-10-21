import json


class Person:
    def __init__(self, name, age, city):
        self.name = name
        self.age = age
        self.city = city


persons = []
persons_data = []
loaded_persons = []
while True:
    add_person = input("Add a person: ")
    if add_person == "yes":
        name = input("Enter name: ")
        age = input("Enter age: ")
        city = input("Enter city: ")
        persons.append(Person(name, age, city))
        continue
    else:
        break

for person in persons:

    person_data = {
    "name" : person.name,
    "age" : person.age,
    "city" : person.city
    }
    persons_data.append(person_data)





with open('person.json', 'w') as file:
    json.dump(persons_data, file, indent=4)
with open('person.json', 'r') as file:
    persons_data = json.load(file)

for person_data in persons_data:
    person = Person(person_data["name"], person_data["age"], person_data["city"])
    loaded_persons.append(person)

for person in loaded_persons:
    print(person.name, person.age, person.city)

print(persons_data)
