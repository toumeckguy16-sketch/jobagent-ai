import os
files = [
    r"c:\Users\Stel_toumeck\Documents\codemem\ui\app.py",
    r"c:\Users\Stel_toumeck\Documents\codemem\auth\auth_manager.py",
    r"c:\Users\Stel_toumeck\Documents\codemem\agents\scraper_agent.py"
]
for p in files:
    if not os.path.exists(p): continue
    with open(p, "rb") as f: data = f.read()
    # Replace UTF-8 bytes of mojibake
    data = data.replace(b"\xc3\xa2\xe2\x82\xac\xe2\x80\x94", "—".encode("utf-8"))
    data = data.replace(b"\xc3\xa2\xe2\x80\x9d\xe2\x94\x80", "─".encode("utf-8"))
    data = data.replace(b"\xc3\xa3\xc2\xa8", "è".encode("utf-8"))
    data = data.replace(b"\xc3\xa3\xc2\xa9", "é".encode("utf-8"))
    data = data.replace(b"\xc3\xa2\xe2\x80\x94\xe2\x80\x94", "──".encode("utf-8"))
    # Let's try string replacement too
    try:
        text = data.decode("utf-8")
        text = text.replace("â€”", "—").replace("â”€", "─").replace("Ã¨", "è").replace("Ã©", "é")
        text = text.replace("Ã ", "à").replace("Ã¹", "ù").replace("Ã", "à")
        with open(p, "w", encoding="utf-8") as f: f.write(text)
    except: pass
