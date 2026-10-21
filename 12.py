import json
class Car:
    def __init__(self, ID, brand, model, price):
        self.ID = ID
        self.brand = brand
        self.model = model
        self.price = price

cars=[]
cars_save=[]
cars_load=[]
loaded_cars=[]

while True:
    try:
        ID = int(input("Enter car id: "))
        id_exist=False
    except ValueError:
        print("Invalid car id")
        continue
    if ID <=0:
        print("Invalid car id")
        continue
    for car in cars:
        if car.ID == ID:
            id_exist=True
            break
    if id_exist:
        print("Invalid car id")
        continue
    else:
        break
while True:
    brand = input("Enter brand: ")
    brand=brand.strip()
    if brand == "":
        print("Invalid brand")
        continue
    else:
        break
while True:
    model = input("Enter model: ")
    model=model.strip()
    if model == "":
        print("Invalid model")
        continue
    else:
        break
while True:
    try:
        price = float(input("Enter price: "))
    except ValueError:
        print("Invalid price")
        continue
    if price <= 0:
        print("Invalid price")
        continue
    else:
        break

cars.append(Car(ID, brand, model, price))

for car in cars:
    cars_saving = {
        "ID": car.ID,
        "brand": car.brand,
        "model": car.model,
        "price": car.price
    }
    cars_save.append(cars_saving)

with open('cars.json', 'w') as file:
    json.dump(cars_save, file)

with open('cars.json', 'r') as file:
    cars_load = json.load(file)

for car in cars_load:
    cars_loading = Car(
        ID=car["ID"],
        brand=car["brand"],
        model=car["model"],
        price=car["price"]
    )
    loaded_cars.append(cars_loading)

for car in loaded_cars:
    print(car.ID, car.brand, car.model, car.price)