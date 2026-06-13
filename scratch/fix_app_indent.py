import os

filepath = 'ui/app.py'
with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Verify that the lines match what we expect
start_idx = 1492 # line 1493 (0-indexed)
end_idx = 1533   # line 1533 (0-indexed)

print("Target block start line:", repr(lines[start_idx]))
print("Target block end line:", repr(lines[end_idx]))

new_lines = [
    '            if uploaded_file:\n',
    '                if uploaded_file.size > 5 * 1024 * 1024:\n',
    '                    st.error("Le fichier dépasse la limite autorisée de 5 Mo.")\n',
    '                else:\n',
    '                    col_i, col_b = st.columns([3, 1])\n',
    '                    with col_i:\n',
    '                        st.markdown(f"""\n',
    '                        <div class=\'card\' style=\'padding:12px; color:{T["accent"]}; fontsize:0.9em;\'>\n',
    '                            {uploaded_file.name}\n',
    '                            <span style=\'color:{T["text_muted"]};\'>\n',
    '                                ({round(uploaded_file.size/1024,1)} Ko)\n',
    '                            </span>\n',
    '                        </div>\n',
    '                        """, unsafe_allow_html=True)\n',
    '                    with col_b:\n',
    '                        if st.button("Analyser", type="primary", use_container_width=True):\n',
    '                            with st.spinner("Analyse du CV en cours..."):\n',
    '                                file_bytes = uploaded_file.read()\n',
    '                                if st.session_state.use_mock:\n',
    '                                    time.sleep(1)\n',
    '                                    profile = CVParser.mock_parse(uploaded_file.name)\n',
    '                                else:\n',
    '                                    profile = CVParser().parse(file_bytes, uploaded_file.name)\n',
    '                                st.session_state.candidate_profile = profile or {}\n',
    '                                st.session_state.profile_source    = "cv"\n',
    '                                st.session_state.cv_filename       = uploaded_file.name\n',
    '                                st.session_state.user_profile_text = profile.get("profile_text", "")\n',
    '                                st.session_state.cv_just_loaded    = True  # Flag notification\n',
    '                                \n',
    '                            # ── Sauvegarder dans Firestore ──\n',
    '                            if st.session_state.get("logged_in") and st.session_state.get("user"):\n',
    '                                uid = st.session_state.user.get("uid")\n',
    '                                profile_to_save = {\n',
    '                                    **profile,\n',
    '                                    "profile_source": "cv",\n',
    '                                    "cv_filename":    uploaded_file.name,\n',
    '                                }\n',
    '                                AuthManager.save_profile(uid, profile_to_save)\n',
    '                               \n',
    '                            st.rerun()\n'
]

# Replace the lines
lines[start_idx:end_idx] = new_lines

with open(filepath, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Successfully replaced and indented.")
