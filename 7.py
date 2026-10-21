def say_hello():
    name = input("enter your name: ")
    print("Hello " + name )

def add_numbers():
    num1=int(input("enter first number"))
    num2=int(input("enter second number"))
    print("sum is ",num1+num2)

def exit_program():
    print("goodbye")

choice = int(input("1.Say Hello""\n2.Add Numbers""\n3.Exit"))

def menu():
    print("Greet to see you")
    while choice is not int:
        try:
            choice = int(input("1.Say Hello""\n2.Add Numbers""\n3.Exit"))
        except ValueError:
            print("please enter valid choice")
    while True:
        if choice == 1:
            say_hello()
            break
        elif choice == 2:
            add_numbers()
            break
        elif choice == 3:
            exit_program()
            break
        else:
            print("please enter valid choice")
            continue

menu()