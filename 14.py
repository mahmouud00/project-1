import json

class Game:
    def __init__(self, ID, name, category, price):
        self.ID = ID
        self.name = name
        self.category = category
        self.price = price

games = []
games_save = []
games_load = []
loaded_games = []

try:
    with open('games.json', 'r') as file:
        games_load = json.load(file)
except FileNotFoundError:
    with open('games.json', 'w') as file:
        json.dump(games_save, file)

for game in games_load:
    games_loading = Game(
        game['ID'],
        game['name'],
        game['category'],
        game['price'],
    )
    loaded_games.append(games_loading)

for game in loaded_games:
    games.append(game)

for game in games:
    games_saving = {
        "ID": game.ID,
        "name": game.name,
        "category": game.category,
        "price": game.price,
    }
    games_save.append(games_saving)

while True:
    try:
        ID = int(input("Enter ID: "))
        id_exist=False
    except ValueError:
        print("ID must be an integer")
        continue
    if ID <=0:
        print("ID must be greater than 0")
        continue
    for game in games:
        if game.ID == ID:
            id_exist = True
            break
    if id_exist:
        print("ID already exists")
        continue
    else:
        break
while True:
    name = input("Enter name: ")
    name=name.strip()
    if name == "":
        print("Name cannot be empty")
        continue
    else:
        break
while True:
    category = input("Enter category: ")
    category = category.strip()
    if category == "":
        print("Category cannot be empty")
        continue
    else:
        break
while True:
    try:
        price = float(input("Enter price: "))
    except ValueError:
        print("Price must be number")
        continue
    if price <= 0:
        print("Price must be greater than 0")
        continue
    else:
        break
games.append(Game(ID, name, category, price))
games_save=[]
for game in games:
    games_saving = {
        "ID": game.ID,
        "name": game.name,
        "category": game.category,
        "price": game.price,
    }
    games_save.append(games_saving)

with open('games.json', 'w') as file:
    json.dump(games_save, file)

with open('games.json', 'r') as file:
    games_load = json.load(file)

loaded_games = []

for game in games_load:
    games_loading = Game(
        game["ID"],
        game["name"],
        game["category"],
        game["price"],
    )
    loaded_games.append(games_loading)

for game in loaded_games:
    print(game.ID, game.name, game.category, game.price)