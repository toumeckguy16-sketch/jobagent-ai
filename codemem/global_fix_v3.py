import os
import re

def fix_mojibake(text):
    # Mapping of common UTF-8 mojibake (encoded as UTF-8 but interpreted as something else then re-encoded)
    d = {
        'Ã©': 'é',
        'Ã¨': 'è',
        'Ã ': 'à',
        'Ã¹': 'ù',
        'Ã»': 'û',
        'Ãª': 'ê',
        'Ã®': 'î',
        'Ã´': 'ô',
        'Ã«': 'ë',
        'Ã¯': 'ï',
        'Ã ': 'à',
        'Ã‚': 'Â',
        'Ã€': 'À',
        'Ã‡': 'Ç',
        'Ã§': 'ç',
        'â€”': '—',
        'â€“': '–',
        'â”€': '─',
        'â€™': "'",
        'â€˜': "'",
        'â€¦': '...',
        'â€': '—', # partial em-dash
        'Ã ': 'à ', # A with space
    }
    
    for bad, good in d.items():
        text = text.replace(bad, good)
        
    # Fix triple encoding or weird Streamlit transformations
    # Ex: Ã¢â‚¬â€”
    text = text.replace('Ã¢â‚¬â€”', '—')
    text = text.replace('Ã¢â‚¬â€', '─')
    text = text.replace('Ã Â§', '§')
    text = text.replace('Ã Â·', '·')
    
    return text

files = [
    r"c:\Users\Stel_toumeck\Documents\codemem\ui\app.py",
    r"c:\Users\Stel_toumeck\Documents\codemem\auth\auth_manager.py",
    r"c:\Users\Stel_toumeck\Documents\codemem\orchestrator.py",
    r"c:\Users\Stel_toumeck\Documents\codemem\agents\scraper_agent.py",
    r"c:\Users\Stel_toumeck\Documents\codemem\agents\extractor_agent.py",
    r"c:\Users\Stel_toumeck\Documents\codemem\agents\analyst_agent.py",
    r"c:\Users\Stel_toumeck\Documents\codemem\agents\coach_agent.py"
]

for p in files:
    if not os.path.exists(p): continue
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        
        new_content = fix_mojibake(content)
        
        if new_content != content:
            with open(p, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"Fixed: {p}")
    except Exception as e:
        print(f"Error fixing {p}: {e}")
