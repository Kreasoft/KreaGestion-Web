with open('templates/base.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()
    
balance = 0
for i, line in enumerate(lines, 1):
    prev_balance = balance
    balance += line.count('{% if') - line.count('{% endif')
    if i >= 950 and i <= 1040:
        marker = " <-- ERROR" if prev_balance < 0 or (balance == 0 and '{% endif' in line and prev_balance == 0) else ""
        if '{% if' in line or '{% endif' in line:
            print(f"{i:4d} [{balance:+3d}] {line.rstrip()[:100]}{marker}")
