def calculate_area(radius):
    return 3.14159 * radius * radius


def format_email(username, domain="gmail.com"):
    return f"{username}@{domain}"


def is_even(number):
    if number % 2 == 0:
        return True
    return False


class BankAccount:
    def __init__(self, owner, balance=0):
        self.owner = owner
        self.balance = balance

    def deposit(self, amount):
        self.balance += amount
        return self.balance

    def withdraw(self, amount):
        if amount > self.balance:
            return "Insufficient funds"
        self.balance -= amount
        return self.balance