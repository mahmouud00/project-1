import json


class Employee:
    def __init__(self, ID, name, salary, department):
        self.ID = ID
        self.name = name
        self.salary = salary
        self.department = department


employees = []
employee_save = []
employee_load = []
loaded_employee = []

while True:
    try:
        ID = int(input("Enter employee ID: "))
        id_exist = False
    except ValueError:
        print("Invalid ID")
        continue
    if ID <= 0:
        print("Invalid ID")
        continue
    for employee in employees:
        if employee.ID == ID:
            id_exist = True
            break
    if id_exist:
        print("Employee with ID", ID, "already exists")
        continue
    else:
        break
while True:
    name = input("Enter employee name: ")
    name = name.strip()
    if name == "":
        print("Invalid name")
        continue
    else:
        break
while True:
    try:
        salary = float(input("Enter employee salary: "))
    except ValueError:
        print("Invalid salary")
        continue
    if salary <= 0:
        print("Invalid salary")
        continue
    else:
        break
while True:
    department = input("Enter employee department: ")
    department = department.strip()
    if department == "":
        print("Invalid department")
        continue
    else:
        break
employees.append(Employee(ID, name, salary, department))

for employee in employees:
    employee_saving = {
        "ID": employee.ID,
        "name": employee.name,
        "salary": employee.salary,
        "department": employee.department
    }
    employee_save.append(employee_saving)

with open("employees.json", "w") as file:
    json.dump(employee_save, file)

with open("employees.json", "r") as file:
    employee_load = json.load(file)

for employee in employee_load:
    employee_loading = Employee(
        employee["ID"],
        employee["name"],
        employee["salary"],
        employee["department"]
    )
    loaded_employee.append(employee_loading)

for employee in loaded_employee:
    print(employee.ID, employee.name, employee.salary, employee.department)
