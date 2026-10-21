
import json


class Student:
    def __init__(self, ID, Name, Grade):
        self.ID = ID
        self.Name = Name
        self.Grade = Grade

students=[]
students_save=[]
students_load=[]
loaded_students=[]

while True:
    try:
        ID = int(input("Enter Student ID: "))
        id_exist=False
    except ValueError:
        continue
    if ID <= 0:
        print("Student ID is invalid")
        continue
    for student in students:
        if student.ID == ID:
            id_exist=True
            break
    if id_exist:
        print("Student ID is invalid")
        continue
    else:
        break
while True:
    Name = input("Enter Student Name: ")
    Name=Name.strip()
    if Name == "":
        print("Student Name is invalid")
        continue
    else:
        break
while True:
    try:
        Grade = int(input("Enter Student Grade: "))
    except ValueError:
        print("Student Grade is invalid")
        continue
    if Grade <= 0:
        print("Student Grade is invalid")
        continue
    else:
        break

student = Student(ID, Name, Grade)
students.append(student)
for i in students:
    print(i.ID, i.Name, i.Grade)



for student in students:
    student_saving={
        "ID":student.ID,
        "Name":student.Name,
        "Grade":student.Grade
    }
    students_save.append(student_saving)

with open('students.json', 'w') as file:
    json.dump(students_save, file)

with open("students.json","r") as file:
    students_load=json.load(file)

for student in students_load:
    student_loaded = Student(
        student["ID"],
        student["Name"],
        student["Grade"]
    )
    loaded_students.append(student_loaded)

for student in loaded_students:
    print(student.ID, student.Name, student.Grade)