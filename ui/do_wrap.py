import sys

filepath = 'c:/Users/Stel_toumeck/Documents/codemem/ui/app.py'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_wrapper = [
    '        if "show_edit_profile" not in st.session_state:\n',
    '            st.session_state.show_edit_profile = False\n',
    '\n',
    '        if st.button("Modifier le profil", use_container_width=True):\n',
    '            st.session_state.show_edit_profile = not st.session_state.show_edit_profile\n',
    '            \n',
    '        if st.session_state.show_edit_profile:\n'
]

# line 1376 is lines[1375] !
indented_lines = ['    ' + line if line.strip() else line for line in lines[1375:1498]]

new_lines = lines[:1375] + new_wrapper + indented_lines + lines[1498:]

with open(filepath, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print('Success modification.')
