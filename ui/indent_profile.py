import sys

filepath = r'c:\Users\Stel_toumeck\Documents\codemem\ui\app.py'
out_filepath = r'c:\Users\Stel_toumeck\Documents\codemem\ui\app_new.py'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

start_idx = -1
end_idx = -1

for i, line in enumerate(lines):
    if '# Header "Édition du profil" vs "Changer de photo"' in line:
        start_idx = i
    if 'st.markdown("</div>", unsafe_allow_html=True)' in line and i > 1400:
        end_idx = i
        break

if start_idx != -1 and end_idx != -1:
    new_wrapper = [
        '        if "show_edit_profile" not in st.session_state:\n',
        '            st.session_state.show_edit_profile = False\n',
        '\n',
        '        if st.button("Modifier le profil", use_container_width=True):\n',
        '            st.session_state.show_edit_profile = not st.session_state.show_edit_profile\n',
        '            \n',
        '        if st.session_state.show_edit_profile:\n'
    ]
    
    indented_lines = ['    ' + line if line.strip() else line for line in lines[start_idx:end_idx+1]]
    
    new_lines = lines[:start_idx] + new_wrapper + indented_lines + lines[end_idx+1:]
    
    with open(out_filepath, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    print("Success")
else:
    print("Bounds not found")
