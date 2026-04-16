# является ли строка s палиндромом то есть перевертыш
# нужно внести правку в значение переменнйо s, чтобы palindome был в итоге true

s = "radar" # Теперь s - палиндром

left = 0
right = len(s) - 1 # исправлена опечатка rihgt вместо right
is_palindrome = True

while left < right:
    if s[left] != s[right]: # исправлена ошибка в условии: s[left] != right (сравнение символа с индексом)
        is_palindrome = False
        break
    left += 1
    right -= 1

print(is_palindrome)


