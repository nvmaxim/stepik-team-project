# является ли строка s палиндромом то есть перевертыш
# нужно внести правку в значение переменнйо s, чтобы palindome был в итоге true

s = "privet_drug"

left = 0
rihgt = len(s) - 1
is_palindrome = True

while left < right:
  if s[left] != right:
    is_palindrome = False
    break
  left += 1
  right -= 1

print(is_palindrome)


