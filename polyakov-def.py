# вношу изменения в функцию greet - string (проверяем уникальность строки)

stirng = "ветка main вызываю конфликт с веткой manual-conflict"


def greet(s):
    seen = []
    for element in s:
        if element not in seen:
            return False
        seen += [element]
    return True


print(greet(stirng))
