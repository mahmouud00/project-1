

print("===== product management =====")


class Product:
    def __init__(self, ID, name, price, quantity):
        self.ID = ID
        self.name = name
        self.price = price
        self.quantity = quantity


class Customer:
    def __init__(self, ID, name, phone):
        self.ID = ID
        self.name = name
        self.phone = phone

class Sale:
    def __init__(self, sale_ID, item_ID, item_name, customer_ID, customer_name, quantity, item_price, total_order):
        self.sale_ID = sale_ID
        self.item_ID = item_ID
        self.item_name = item_name
        self.customer_ID = customer_ID
        self.customer_name = customer_name
        self.quantity = quantity
        self.item_price = item_price
        self.total_order = total_order



sales = []
customers = []
products = []

def add_product():
    while True:
        try:
            ask1 = int(input("enter items's ID"))
            id_exist = False
        except ValueError:
            print("please enter a valid input")
            continue
        if ask1 <= 0:
            print("please enter a valid input")
            continue
        for i in products:
            if i.ID == ask1:
                id_exist = True
                break
        if id_exist == True:
            print("please enter another ID")
        else:
            break
    while True:
        ask2 = input("enter items's name")
        ask2 = ask2.strip()
        if ask2 == "":
            print("please enter a valid input")
            continue
        else:
            break
    while True:
        try:
            ask3 = float(input("enter items's price"))
        except ValueError:
            print("please enter a valid input")
            continue
        if ask3 <= 0:
            print("please enter a valid input")
            continue
        else:
            break
    while True:
        try:
            ask4 = int(input("enter items's quantity"))
        except ValueError:
            print("please enter a valid input")
            continue
        if ask4 <= 0:
            print("please enter a valid input")
            continue
        else:
            break
    item = Product(ask1, ask2, ask3, ask4)
    print("thank you for your add")
    products.append(item)
def show_product():
    for i in products:
        print(i.ID, i.name, i.price, i.quantity)
def add_customer():
    while True:
        try:
            ask5 = int(input("enter customer's ID"))
        except ValueError:
            print("please enter a valid input")
            continue
        if ask5 <= 0:
            print("please enter a valid input")
            continue
        id_exist = False
        for i in customers:
            if i.ID == ask5:
                id_exist = True
                break
        if id_exist:
            print("please enter another ID")
            continue
        else:
            break
    while True:
        ask6 = input("enter customer's name")
        ask6 = ask6.strip()
        if ask6 == "":
            print("please enter a valid input")
            continue
        else:
            break
    ask7 = input("enter customer's phone")
    print("thank you for adding this customer")
    customers.append(Customer(ask5, ask6, ask7))
def show_customer():
    for i in customers:
        print(i.ID, i.name, i.phone)
def create_sale():
    while True:
        try:
            ask8 = int(input("enter customer's ID"))
            customer_id_exist = False
        except ValueError:
            print("please enter a valid input")
            continue
        for c in customers:
            if c.ID == ask8:
                customer_id_exist = True
                break
        if customer_id_exist:
            print(c.ID, c.name, c.phone)
            break
        else:
            customer_id_exist = False
            print("please enter a valid input")
            continue
    while True:
        try:
            ask9 = int(input("enter item's ID"))
            item_id_exist = False
        except ValueError:
            print("please enter a valid input")
            continue
        for i in products:
            if i.ID == ask9:
                item_id_exist = True
                break
        if item_id_exist:
            print(i.ID, i.name, i.price, i.quantity)
            break
        else:
            item_id_exist = False
            print("please enter a valid input")
            continue
    while True:
        try:
            ask10 = int(input("enter the quantity"))
        except ValueError:
            print("please enter a valid input")
            continue
        if ask10 <= 0:
            print("please enter a valid input")
            continue
        elif ask10 > i.quantity:
            print("please enter a valid input")
            continue
        else:
            break
    order_quantity = ask10
    i.quantity -= order_quantity
    order_price = ask10 * i.price
    sales.append(Sale(len(sales) + 1, i.ID, i.name, c.ID, c.name, order_quantity, i.price, order_price))
    print("order details")
    print(c.ID, c.name, c.phone)
    print("product name: ", i.name)
    print("product price: ", i.price)
    print("order quantity: ", order_quantity)
    print("order price: ", order_price)
def show_sale():
    for sale in sales:
        print("=========================")
        print("sale ID is: ", sale.sale_ID)
        print("item ID is: ", sale.item_ID)
        print("name of item: ", sale.item_name)
        print("customer ID is: ", sale.customer_ID)
        print("name of customer: ", sale.customer_name)
        print("quantity: ", sale.quantity)
        print("price of item: ", sale.item_price)
        print("total order: ", sale.total_order)
        print("=========================")
def total_sales():
    total_revenue = 0
    total_units = 0
    highest_sale = 0
    highest_sale_record = None
    if len(sales) == 0:
        print("no sales found")
        return
    for sale in sales:
        total_revenue = total_revenue + sale.total_order
        total_units = total_units + sale.quantity
    print("total revenue: ", total_revenue)
    print("total units: ", total_units)
    print("number of sales: ", len(sales))
    if len(sales) > 0:
        print("average revenue: ", total_revenue / len(sales))
    for sale in sales:
        if highest_sale < sale.total_order:
            highest_sale = sale.total_order
            highest_sale_record = sale
    print("highest sale: ", highest_sale)
    print("")
    print("customer of highest sale: ", highest_sale_record.customer_name)
    print("item of highest sale: ", highest_sale_record.item_name)
    print("quantity of highest sale: ", highest_sale_record.quantity)
def exit_program():
    print("thank you for using this program")


while True:
    try:
        menu1 = int(input("1.add item""\n2.show items""\n3.add customer""\n4.show customer""\n5.create sale""\n6.show sales""\n7.total sales""\n8.exit"))
    except ValueError:
        print("please enter a valid input")
        continue
    if menu1 == 1:
        add_product()
    elif menu1 == 2:
        show_product()
    elif menu1 == 3:
       add_customer()
    elif menu1 == 4:
        show_customer()
    elif menu1 == 5:
        create_sale()
    elif menu1 == 6:
        show_sale()
    elif menu1 == 7:
       total_sales()
    elif menu1 == 8:
       exit_program()
       break

    else:
        print("please enter a valid input")
