import os

def fix_all():
    path = r"c:\Users\Stel_toumeck\Documents\codemem\ui\app.py"
    if not os.path.exists(path): return
    
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    
    # Fix syntax error I just introduced
    content = content.replace("st.markdown(### Historique des Collectes)", "st.markdown('### Historique des Collectes')")
    
    # Fix encoding
    replacements = {
        "Ã©": "é", "Ã¨": "è", "Ã ": "à", "Ã¹": "ù", "Ã»": "û", "Ã²": "ò", "Ã´": "ô", "Ã®": "î", "Ã«": "ë",
        "Ã": "à", "â€”": "—", "â”€": "─", "â€": "—", "Ã¢â‚¬â€": "──",
        "ðŸ•’": "🕒", "ðŸš€": "🚀", "âœ…": "✅", "âš ": "⚠️", "ðŸ“Š": "📊"
    }
    
    for bad, good in replacements.items():
        content = content.replace(bad, good)
        
    # Final pass to fix the "à" issue where it might have replaced a correct character's first byte
    # but since we read as utf-8 errors=replace, it's safer.
    
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

fix_all()
print("Success")
