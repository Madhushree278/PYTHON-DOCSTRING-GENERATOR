# sample_context_test.py

def find_max(numbers):
    max_value = numbers[0]
    for n in numbers:
        if n > max_value:
            max_value = n
    return max_value


def check_login(username, password):
    if username == "admin" and password == "1234":
        return True
    return False


def calculate_average(numbers):
    total = 0
    for n in numbers:
        total += n
    return total / len(numbers)


def is_palindrome(text):
    text = text.lower()
    return text == text[::-1]


def format_phone_number(number):
    cleaned = str(number)
    return f"({cleaned[:3]}) {cleaned[3:6]}-{cleaned[6:]}"


class ShoppingCart:

    def __init__(self):
        self.items = []

    def add_item(self, item):
        self.items.append(item)

    def remove_item(self, item):
        if item in self.items:
            self.items.remove(item)

    def total_items(self):
        return len(self.items)

    def clear_cart(self):
        self.items = []