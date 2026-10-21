import json
class Book():
    def __init__(self, bID, btitle, bauthor, bavailable_copies):
        self.ID = bID
        self.title = btitle
        self.author = bauthor
        self.available_copies = bavailable_copies


class Member():
    def __init__(self, mID, mname, mphone):
        self.ID = mID
        self.name = mname
        self.phone = mphone


class Sale():
    def __init__(self, ssale_ID, smember_ID, sbook_title, squantity):
        self.sale_ID = ssale_ID
        self.member_ID = smember_ID
        self.book_title = sbook_title
        self.quantity = squantity


books = []
members = []
sales = []
copies = []
books_save=[]
data_load=[]
loaded_data=[]


def add_book():
    while True:
        try:
            bID = int(input("Enter Book ID: "))
            id_exist = False
        except ValueError:
            print("Invalid Book ID")
            continue
        if bID <= 0:
            print("Invalid Book ID")
            continue
        for z in books:
            if z.ID == bID:
                id_exist = True
                break
        if id_exist:
            print("invalid book ID")
            continue
        else:
            break
    while True:
        title = input("Enter Book Title: ")
        title = title.strip()
        if title == "":
            print("Invalid Title")
            continue
        else:
            break
    while True:
        author = input("Enter Book Author: ")
        author = author.strip()
        if author == "":
            print("Invalid Author")
            continue
        else:
            break
    while True:
        try:
            available_copies = int(input("Enter available copies: "))
        except ValueError:
            print("Invalid available copies")
            continue
        if available_copies <= 0:
            print("Invalid available copies")
            continue
        else:
            break
    print("Book ID: ", bID)
    print("Book Title: ", title)
    print("Book Author: ", author)
    print("Available copies: ", available_copies)
    print("Book added")
    books.append(Book(bID, title, author, available_copies))

def show_books():
    for x in books:
        print("Book ID: ", x.ID, "\nBook Title: ", x.title, "\nBook Author: ", x.author, "\nAvailable copies: ", x.available_copies)


def add_member():
    while True:
        try:
            ID = int(input("Enter Member ID: "))
            member_id_exist = False
        except ValueError:
            print("Invalid Member ID")
            continue
        if ID <= 0:
            print("Invalid Member ID")
            continue
        for member in members:
            if member.ID == ID:
                member_id_exist = True
                break
        if member_id_exist:
            print("invalid member ID")
            continue
        else:
            break

    while True:
        name = input("Enter Member Name: ")
        name = name.strip()
        if name == "":
            print("Invalid Member Name")
            continue
        else:
            break
    while True:
        phone = input("Enter Member Phone: ")
        phone = phone.strip()
        if phone == "":
            print("Invalid Member Phone")
            continue
        else:
            break
    members.append(Member(ID, name, phone))


def show_members():
    for x in members:
        print("member's ID: ", x.ID, "\nmember's Name: ", x.name, "\nmember's Phone: ", x.phone, "\n==================")


def add_sale ():
    sale_ID = len(sales)
    sale_ID += 1
    while True:
        try:
            member_ID = int(input("Enter member ID: "))
            id_member = False
        except ValueError:
            print("Invalid Member ID")
            continue
        for m in members:
            if m.ID == member_ID:
                id_member = True
                break
        if id_member:
            print("ID found")
            break
        else:
            print("ID not found")
            continue
    while True:
        book_title = input("Enter Book Title: ")
        book_name = False
        for book in books:
            if book.title == book_title:
                book_name = True
                break
        if book_name:
            print("Book found")
            break
        else:
            print("Book not found")
            continue
    while True:
        try :
            quantity = int(input("Enter Quantity: "))
        except ValueError:
            print("Invalid Quantity")
            continue
        if quantity <= 0:
            print("Invalid Quantity")
            continue
        elif quantity > book.available_copies:
            print("Invalid Quantity")
        else:
            break

    book.available_copies = book.available_copies - quantity
    copies.append(book.available_copies)

    sales.append(Sale(sale_ID, member_ID, book_title, quantity))

def show_sales():
    for s in sales:
        print("sale's ID: ", s.sale_ID, "\nmember's ID: ", s.member_ID, "\nbook's title: ", s.book_title, "\nquantity: ", s.quantity)

for book in books:
    saving_books = {
        "Book ID": book.ID,
        "Book Title": book.title,
        "Book Author": book.author,
        "Available copies": book.available_copies,
    }
    books_save.append(saving_books)

add_book()
with open ("data.txt", "w") as file:
    json.dump(books_save, file)

with open ("data.txt", "r") as file:
    data_load=json.load(file)

for book in data_load:
    books_loading = Book(
        book["Book ID"],
        book["Book Title"],
        book["Book Author"],
        book["Available copies"],
    )
    data_load.append(books_loading)


