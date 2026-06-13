import re
import os

file_path = r'c:\Users\Stel_toumeck\Documents\codemem\ui\app.py'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Extract Apparence
apparence_regex = r'(    st\.markdown\("### Apparence"\).*?    with col_t2:\n        if st\.button\("Clair", use_container_width=True, type="primary" if st\.session_state\.theme == "light" else "secondary"\):\n            st\.session_state\.theme = "light"\n            st\.rerun\(\)\n)'
match = re.search(apparence_regex, content, flags=re.DOTALL)
if not match:
    print("Could not find Apparence block")
    exit(1)
apparence_code = match.group(1)

# Remove Apparence from original position
content = content.replace(apparence_code, '')

# Find insertion point which is at the end of Modifier le profil
# The end of Modifier le profil is:
end_mod_profil = r'            st.markdown("</div>", unsafe_allow_html=True)'

new_content = content.replace(end_mod_profil, end_mod_profil + "\n\n" + apparence_code)

with open(file_path + '.tmp', 'w', encoding='utf-8') as f:
    f.write(new_content)

os.replace(file_path + '.tmp', file_path)
print("Success")
