import json
class Movie:
    def __init__(self, ID, title, genre, rating):
        self.ID = ID
        self.title = title
        self.genre = genre
        self.rating = rating

movies = []
movies_save= []
movies_load= []
loaded_movies = []

try:
    with open('movies.json', 'r') as file:
        movies_load = json.load(file)
except FileNotFoundError:
    with open('movies.json', 'w') as file:
        json.dump(movies_save, file)

for movie in movies_load:
    movies_loading = Movie(
        movie['ID'],
        movie['title'],
        movie['genre'],
        movie['rating']
    )
    loaded_movies.append(movies_loading)
for movie in loaded_movies:
    movies.append(movie)



while True:
    try:
        ID = int(input("Enter movie ID: "))
        id_exist=False
    except ValueError:
        print("Enter a valid movie ID.")
        continue
    if ID <=0:
        print("Enter a valid movie ID.")
        continue
    for movie in movies:
        if movie.ID == ID:
            id_exist = True
            break
    if id_exist:
        print("Movie with ID", ID, "already exists.")
        continue
    else:
        break
while True:
    title = input("Enter movie title: ")
    title=title.strip()
    if title == '':
        print("Enter a valid movie title.")
        continue
    else:
        break
while True:
    genre = input("Enter movie genre: ")
    genre = genre.strip()
    if genre == '':
        print("Enter a valid movie genre.")
        continue
    else:
        break
while True:
    try:
        rating = float(input("Enter movie rating: "))
    except ValueError:
        print("Enter a valid movie rating.")
        continue
    if rating <= 0 or rating > 10:
        print("Enter a valid movie rating.")
        continue
    else:
        break
movies.append(Movie(ID, title, genre, rating))

movies_save=[]
for movie in movies:
    movies_saving = {
        "ID": movie.ID,
        "title": movie.title,
        "genre": movie.genre,
        "rating": movie.rating
    }
    movies_save.append(movies_saving)

with open('movies.json', 'w') as file:
    json.dump(movies_save, file)

with open('movies.json', 'r') as file:
    movies_load = json.load(file)

loaded_movies = []

for movie in movies_load:
    movies_loading = Movie(
        movie['ID'],
        movie['title'],
        movie['genre'],
        movie['rating']
    )
    loaded_movies.append(movies_loading)

for movie in loaded_movies:
    print(movie.ID, movie.title, movie.genre, movie.rating)