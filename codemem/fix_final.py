import os

def fix_content(content):
    # Map of common mojibake sequences to their correct characters
    replacements = {
        "Ã¢â‚¬â€": "───",
        "Ã¢â‚¬": "──",
        "Ã©": "é",
        "Ã¨": "è",
        "Ã ": "à",
        "Ã¹": "ù",
        "Ã»": "û",
        "Ã®": "î",
        "Ã´": "ô",
        "Ã«": "ë",
        "â€”": "—",
        "â”€": "─",
        "Ã Â§": "§", 
        "Ã Â·": "·",
        "Ã Â®": "®",
        "Ã â‚¬": "€",
        "Ã â€ž": "„",
        "Ã â€¦": "…",
        "Ã â‚¬": "€",
        "Ã Â Â": "", # cleanup
        "Ã Â": " ",
        "ðŸ•’": "🕒",
        "Ã°Å¸â€¢â€™": "🕒"
    }
    
    for bad, good in replacements.items():
        content = content.replace(bad, good)
    
    # Secondary cleanup for sequences that were partially fixed
    content = content.replace("à ", "à")
    content = content.replace("à©", "é")
    content = content.replace("à¨", "è")
    content = content.replace("à®", "î")
    content = content.replace("à´", "ô")
    content = content.replace("à»", "û")
    content = content.replace("àª", "ê")
    
    return content

path = r"c:\Users\Stel_toumeck\Documents\codemem\ui\app.py"
if os.path.exists(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    
    new_content = fix_content(content)
    
    if new_content != content:
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print("Fixed app.py")
    else:
        print("No changes in app.py")
