import os
import shutil

path = r'c:\Users\Stel_toumeck\Documents\codemem\ui\app.py'
temp_path = path + '.tmp'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

old = 'elif page == "Préparation à l\'entretien":\n                    st.session_state.edit_mode = False\n                st.session_state.current_page = st.session_state.previous_page\n                st.session_state.previous_page = None\n                st.rerun()'

# In case line endings are \r\n
old_rn = old.replace('\n', '\r\n')

new = """elif page == "Préparation à l'entretien":
    col_b, _ = st.columns([1, 15])
    with col_b:
        if st.button("←", key="back_prep_top", help="Retour"):
            if st.session_state.prep_view == "coach":
                st.session_state.prep_view = "quiz"
                st.rerun()
            elif st.session_state.previous_page:
                st.session_state.edit_mode = False
                st.session_state.current_page = st.session_state.previous_page
                st.session_state.previous_page = None
                st.rerun()"""

found = False
if old in content:
    content = content.replace(old, new)
    found = True
elif old_rn in content:
    content = content.replace(old_rn, new)
    found = True

if found:
    with open(temp_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    # Use os.replace for atomic operation
    os.replace(temp_path, path)
    print("SUCCESS: File updated using atomic replace.")
else:
    print("ERROR: Old content not found.")
    idx = content.find('elif page == "Préparation à l\'entretien":')
    if idx != -1:
        print("FOUND start. Repr:")
        print(repr(content[idx:idx+250]))
