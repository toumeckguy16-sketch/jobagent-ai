import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(BASE, 'auth', 'serviceAccountKey.json'), 'r') as f:
    sa = json.load(f)

# On remplace les vrais retours a la ligne par \n literal pour TOML
pk = sa['private_key'].replace('\n', '\\n')

toml_lines = [
    f'FIREBASE_PRIVATE_KEY_ID = "{sa["private_key_id"]}"',
    f'FIREBASE_PRIVATE_KEY = "{pk}"',
    f'FIREBASE_CLIENT_EMAIL = "{sa["client_email"]}"',
    f'FIREBASE_CLIENT_ID = "{sa["client_id"]}"',
    f'FIREBASE_CLIENT_CERT_URL = "{sa["client_x509_cert_url"]}"',
]

output = '\n'.join(toml_lines)

out_path = os.path.join(BASE, 'streamlit_firebase_secrets.txt')
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(output)

print(f'Fichier genere : {out_path}')
