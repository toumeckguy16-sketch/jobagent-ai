import os

files_to_fix = [
    r"c:\Users\Stel_toumeck\Documents\codemem\ui\app.py",
    r"c:\Users\Stel_toumeck\Documents\codemem\auth\auth_manager.py",
    r"c:\Users\Stel_toumeck\Documents\codemem\agents\scraper_agent.py"
]

def clean_mojibake(text):
    # Fix common mojibake patterns
    # Em-dash
    text = text.replace("â€”", "—").replace("â€", "—").replace("â", "—")
    # Horizontal line
    text = text.replace("â”€", "─").replace("Ã¢â‚¬â€", "──")
    # Accents
    text = text.replace("Ã¨", "è").replace("Ã©", "é").replace("Ã ", "à").replace("Ã", "à")
    # Emojis (replace corrupted ones with text versions for stability)
    text = text.replace("ðŸ•’", "🕒").replace("Ã°Å¸â€¢â€™", "🕒")
    return text

def fix_app_py(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    
    # Target specific messy lines by content markers
    for i in range(len(lines)):
        if "SECTION HISTORIQUE" in lines[i]:
            lines[i] = "    # --- SECTION HISTORIQUE ---\n"
        if "Historique des Collectes" in lines[i] and "###" in lines[i]:
            lines[i] = "    st.markdown('### Historique des Collectes')\n"
        if "Interface Utilisateur Streamlit" in lines[i]:
            lines[i] = 'Interface Utilisateur Streamlit — JobAgent AI\n'
        if "Deux th" in lines[i] and "mes :" in lines[i]:
            lines[i] = 'Deux thèmes : Sombre (#0F0F0F / #E5E5E5 / #FF6B00)\n'
        if "RÃ©partition" in lines[i]:
            lines[i] = lines[i].replace("RÃ©partition", "Répartition")
            
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)

for p in files_to_fix:
    if os.path.exists(p):
        fix_app_py(p)
