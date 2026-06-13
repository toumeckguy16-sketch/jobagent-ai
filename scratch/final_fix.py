import os

path = r'c:\Users\Stel_toumeck\Documents\codemem\ui\app.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

old = 'elif page == "Préparation à l\'entretien":\n                    st.session_state.edit_mode = False\n                st.session_state.current_page = st.session_state.previous_page\n                st.session_state.previous_page = None\n                st.rerun()'

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

if old in content:
    content = content.replace(old, new)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("SUCCESS: File updated.")
else:
    print("ERROR: Old content not found.")
    # Show what's actually there
    start_idx = content.find('elif page == "Préparation à l\'entretien":')
    if start_idx != -1:
        print("FOUND start. Fragment:")
        print(repr(content[start_idx:start_idx+300]))
