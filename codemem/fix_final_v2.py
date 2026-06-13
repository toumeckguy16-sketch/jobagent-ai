import io
path = r"C:\Users\Stel_toumeck\Documents\codemem\ui\app_fix.py"
with io.open(path, "r", encoding="utf-8") as f:
    content = f.read()
import re
content = re.sub(r"\'âœ“\'\s+\'✓\'", "'✓'", content)
content = content.replace("â† ", "←")
content = content.replace("â†", "←")
with io.open(path, "w", encoding="utf-8", newline="\n") as f:
    f.write(content)
print("FIXED")
