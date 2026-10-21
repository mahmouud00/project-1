import json


class Room:
    def __init__(self, ID, room_type, price, floor):
        self.ID = ID
        self.room_type = room_type
        self.price = price
        self.floor = floor


rooms = []
rooms_save = []
rooms_load = []
loaded_rooms = []

try:
    with open("rooms.json", "r") as file:
        rooms_load = json.load(file)
except FileNotFoundError:
    with open("rooms.json", "w") as file:
        json.dump(rooms_save, file)

for room in rooms_load:
    rooms_loading = Room(
    room["ID"],
    room["room_type"],
    room["price"],
    room["floor"],
    )
    loaded_rooms.append(rooms_loading)

for room in loaded_rooms:
    rooms.append(Room(room.ID, room.room_type, room.price, room.floor))

while True:
    try:
        ID = int(input("enter room ID: "))
        id_exists = False
    except ValueError:
        print("invalid room ID")
        continue
    if ID <= 0:
        print("invalid room ID")
        continue
    for room in rooms:
        if room.ID == ID:
            id_exists = True
            break
    if id_exists:
        print("ID exists")
        continue
    else:
        break
while True:
    room_type = input("enter room type: ")
    room_type = room_type.strip()
    if room_type == "":
        print("invalid room type")
        continue
    else:
        break
while True:
    try:
        price = float(input("enter room price: "))
    except ValueError:
        print("invalid room price")
        continue
    if price <= 0:
        print("invalid room price")
        continue
    else:
        break
while True:
    try:
        floor = int(input("enter room floor: "))
    except ValueError:
        print("invalid room floor")
        continue
    if floor <= 0:
        print("invalid room floor")
        continue
    else:
        break
rooms.append(Room(ID, room_type, price, floor))

rooms_save = []

for room in rooms:
    rooms_saving = {
        "ID": room.ID,
        "room_type": room.room_type,
        "price": room.price,
        "floor": room.floor,
    }
    rooms_save.append(rooms_saving)
with open("rooms.json", "w") as file:
    json.dump(rooms_save, file)

with open("rooms.json", "r") as file:
    rooms_load = json.load(file)

loaded_rooms = []

for room in rooms_load:
    rooms_loading = Room(
    room["ID"],
    room["room_type"],
    room["price"],
    room["floor"],
    )
    loaded_rooms.append(rooms_loading)

for room in rooms_load:
    print(room(room.ID, room.room_type, room.price, room.floor))