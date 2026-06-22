with open('ventas/views.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

print("=== LINES WITH NON-ASCII IN PRINT ===")
for idx, line in enumerate(lines):
    line_num = idx + 1
    if 'print(' in line:
        try:
            line.encode('ascii')
        except UnicodeEncodeError:
            safe_line = line.strip().encode('ascii', errors='replace').decode('ascii')
            print(f"Line {line_num}: {safe_line}")
