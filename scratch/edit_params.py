import re

file_path = r'c:\Users\Stel_toumeck\Documents\codemem\ui\app.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Extract "Apparence" section
apparence_pattern = r'(\s*st\.markdown\("### Apparence"\).*?st\.rerun\(\)\n\s*with col_t2:.*?st\.rerun\(\)\n)'
apparence_match = re.search(apparence_pattern, content, flags=re.DOTALL)
if not apparence_match:
    print("Could not find Apparence block.")
    exit(1)
apparence_block = apparence_match.group(1)

# Remove "Apparence" block from its original location
content = content.replace(apparence_block, '')

# 2. Extract "Modifier le profil" section
modifier_pattern = r'(\s*# Modifier le profil\n\s*if st\.session_state\.candidate_profile:\n\s*st\.markdown\("<hr>", unsafe_allow_html=True\)\n.*?\s*st\.markdown\("</div>", unsafe_allow_html=True\)\n)'
modifier_match = re.search(modifier_pattern, content, flags=re.DOTALL)
if not modifier_match:
    print("Could not find Modifier le profil block.")
    exit(1)
modifier_block = modifier_match.group(1)

# Remove "Modifier le profil" block from its original location
content = content.replace(modifier_block, '')

# Now insert them back in the new order: Modifier le profil THEN Apparence
insert_point = r'st.markdown("<h1>Paramètres</h1>", unsafe_allow_html=True)'

if insert_point not in content:
    print("Could not find insert point.")
    exit(1)

new_content = content.replace(
    insert_point,
    insert_point + modifier_block + "\n" + apparence_block
)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(new_content)
print("Reorganization done.")
