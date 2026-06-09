import sys

filepath = 'c:\\Users\\pc\\source\\sgeplus\\app\\routes\\nutrition.py'
with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# We want to remove lines 28 through 221 (inclusive).
# In 0-indexed python arrays, that's index 27 through 220.

new_lines = lines[:27] + lines[221:]

with open(filepath, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Successfully removed duplicated lines 28-221.")
