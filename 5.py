def calc_shipping(shipping=0):
    ship = shipping + float(input("Enter shipping cost: "))
    return ship


def calc_coupon(coupon=0):
    coup = float(input("Enter coupon cost: "))
    return coup


def total_invoice():
    price = float(input("Enter the price: "))
    ask1 = input("there is a shipping cost: ")
    ask2 = input("there is a coupon cost: ")
    if ask1 == "yes" and ask2 == "yes":
        total = price + calc_shipping() - calc_coupon()
        return total
    elif ask1 == "yes" and ask2 == "no":
        total = price + calc_shipping()
        return total
    elif ask1 == "no" and ask2 == "yes":
        total = price - calc_coupon()
        return total
    else:
        return price


print(total_invoice())
