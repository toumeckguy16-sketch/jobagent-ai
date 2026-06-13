import io
import os

p_in = r"C:\Users\Stel_toumeck\Documents\codemem\ui\app_locked.py"
p_out = r"C:\Users\Stel_toumeck\Documents\codemem\ui\app.py"

with io.open(p_in, "r", encoding="utf-8", errors="ignore") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    # 1. Back arrows corrupted -> Use simple string
    if 'st.button("' in line and 'back_' in line:
        # Replace the first quoted string (the label) with "<"
        import re
        line = re.sub(r'st\.button\(".*?",', 'st.button("<",', line)
    
    # 2. Quiz icons in loop
    if 'icon = "' in line and ('\xe2\x9c\x93' in line or '\xe2\x9c\x97' in line or '\u2713' in line or '\u2717' in line or '\u00e2' in line):
         line = line.replace('icon = "âœ“"', 'icon = ""').replace('icon = "âœ—"', 'icon = ""')
         line = re.sub(r'icon = ".*?"', 'icon = ""', line)

    # 3. Quiz summary icons
    if "f\"{'âœ“' '✓' if ok else '✗'}" in line or "f\"{'✓' if ok else '✗'}" in line or "{'âœ“' if ok else 'âœ—'}" in line:
        line = re.sub(r"f\"\{.*?\}\s+", 'f"', line)

    # 4. Clean up any remaining â† or âœ“
    line = line.replace("â† ", "<").replace("âœ“", "").replace("âœ—", "")
    
    new_lines.append(line)

with io.open(p_out, "w", encoding="utf-8", newline="\n") as f:
    f.writelines(new_lines)
print("FIX_COMPLETED")
