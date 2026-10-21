import json
class Course:
    def __init__(self, ID, name, instructor, hours, price):
        self.ID = ID
        self.name = name
        self.instructor = instructor
        self.hours = hours
        self.price = price

courses = []
courses_save=[]
courses_load=[]
loaded_courses = []

while True:
    try:
        ID=int(input("Enter your ID: "))
        id_exist=False
    except ValueError:
        print("Invalid ID")
        continue
    if ID <=0:
        print("invalid ID")
        continue
    for course in courses:
        if ID == course.ID:
            id_exist=True
            break
    if id_exist:
        print("ID is already taken")
        continue
    else:
        break
while True:
    name=input("Enter your name: ")
    name=name.strip()
    if name == "":
        print("Invalid name")
        continue
    else:
        break
while True:
    instructor=input("Enter your instructor: ")
    instructor=instructor.strip()
    if instructor == "":
        print("Invalid instructor")
        continue
    else:
        break
while True:
    try:
        hours=int(input("Enter your hours: "))
    except ValueError:
        print("Invalid hours")
        continue
    if hours <= 0:
        print("Invalid hours")
        continue
    else:
        break
while True:
    try:
        price=float(input("Enter your price: "))
    except ValueError:
        print("Invalid price")
        continue
    if price <= 0:
        print("Invalid price")
        continue
    else:
        break
courses.append(Course(ID, name, instructor, hours, price))

for course in courses:
    course_saving = {
        "ID": course.ID,
        "name": course.name,
        "instructor": course.instructor,
        "hours": course.hours,
        "price": course.price
    }
    courses_save.append(course_saving)

with open("courses.json", "w") as file:
    json.dump(courses_save, file)

with open("courses.json", "r") as file:
    json.dump(courses_load, file)

for course in courses_load:
    course_loading = Course(
        course["ID"],
        course["name"],
        course["instructor"],
        course["hours"],
        course["price"]
    )
    loaded_courses.append(course_loading)

for course in loaded_courses:
    print(course.ID, course.name, course.instructor, course.hours,)