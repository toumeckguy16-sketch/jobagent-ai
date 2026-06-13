import sys
import os

path = r'c:\Users\Stel_toumeck\Documents\codemem\ui\app.py'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

start = -1
end = -1
for i, line in enumerate(lines):
    if 'elif page == "Préparation à l\'entretien":' in line:
        start = i
    if start != -1 and "st.markdown(\"<h1>Préparer l'entretien d'embauche</h1>\"" in line:
        end = i
        break

if start != -1 and end != -1:
    new_block = [
        'elif page == "Préparation à l\'entretien":\n',
        '    col_b, _ = st.columns([1, 15])\n',
        '    with col_b:\n',
        '        if st.button("←", key="back_prep_top", help="Retour"):\n',
        '            if st.session_state.prep_view == "coach":\n',
        '                st.session_state.prep_view = "quiz"\n',
        '                st.rerun()\n',
        '            elif st.session_state.previous_page:\n',
        '                st.session_state.edit_mode = False\n',
        '                st.session_state.current_page = st.session_state.previous_page\n',
        '                st.session_state.previous_page = None\n',
        '                st.rerun()\n',
        '\n'
    ]
    # Replaces everything from 'elif' line up to (but not including) the 'st.markdown' line
    lines[start:end] = new_block
    with open(path, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    print(f"Successfully fixed app.py from line {start+1} to {end}")
else:
    print(f"Could not find the block to fix. Start: {start}, End: {end}")
