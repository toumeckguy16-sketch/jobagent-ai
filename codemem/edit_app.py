import sys
import os

file_path = r'C:\Users\Stel_toumeck\Documents\codemem\ui\app.py'
out_path = r'C:\Users\Stel_toumeck\Documents\codemem\ui\app_new.py'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

new_content = content.replace(
    '"quiz_questions\": [],',
    '"chats": [],\n        "current_chat": None,\n        "show_chat_history": False,\n        "quiz_questions": [],'
)

new_content = new_content.replace(
    'if isinstance(history, dict) and history:\n            st.session_state.chat_history = history',
    'if isinstance(history, dict) and history:\n            st.session_state.chat_history = history\n            if "chats_list" in history:\n                st.session_state.chats = history["chats_list"]'
)

subtab2_old = '''        # ====================================================
        # SUBTAB 2 — CHAT ET ENTRETIEN
        # ===================================================='''

subtab2_new = '''        # ====================================================
        # SUBTAB 2 — CHAT ET ENTRETIEN
        # ====================================================
        with subtab2:
            import time
            if "chats" not in st.session_state:
                st.session_state["chats"] = []
            if "current_chat" not in st.session_state:
                st.session_state["current_chat"] = None
            if "show_chat_history" not in st.session_state:
                st.session_state["show_chat_history"] = False

            if not st.session_state.get("show_chat_history", False):
                if st.button("Historique des chats", use_container_width=True):
                    st.session_state["show_chat_history"] = True
                    st.rerun()
            else:
                if st.button("Masquer l'historique", use_container_width=True):
                    st.session_state["show_chat_history"] = False
                    st.rerun()

            if st.session_state.get("show_chat_history", False):
                with st.expander("Vos précédentes conversations", expanded=True):
                    if not st.session_state["chats"]:
                        st.info("Aucun historique disponible")
                    else:
                        for idx, chat in enumerate(reversed(st.session_state["chats"])):
                            chat_id = chat.get("id", "Chat sans nom")
                            if st.button(f"Reprendre : {chat_id}", key=f"btn_hist_{chat_id}_{idx}", use_container_width=True):
                                st.session_state["current_chat"] = chat
                                st.session_state["show_chat_history"] = False
                                st.rerun()

            st.markdown("<hr>", unsafe_allow_html=True)

            if not st.session_state["current_chat"]:
                st.info("Cliquez sur 'Commencer un nouvel entretien virtuel' ou choisissez une conversation de l'historique.")
                
            col_new, _ = st.columns([1, 1])
            with col_new:
                if st.button("Commencer un nouvel entretien virtuel", use_container_width=True):
                    with st.spinner("Coach démarre l'entretien..."):
                        if st.session_state.use_mock:
                            welcome = f"Bonjour ! Bienvenue à votre entretien pour le poste de {job['title']}. Parlez-moi un peu de vous."
                        else:
                            welcome = CoachAgent().init_interview(job)
                                
                        new_chat_id = f"Entretien {job['title']} - {time.strftime('%H:%M:%S')}"
                        new_chat = {
                            "id": new_chat_id,
                            "messages": [{"role": "assistant", "content": welcome}]
                        }
                        
                        if "chats" not in st.session_state:
                           st.session_state["chats"] = []
                        st.session_state["chats"].append(new_chat)
                        st.session_state["current_chat"] = new_chat
                            
                        if st.session_state.get("logged_in") and st.session_state.get("user"):
                            uid = st.session_state.user.get("uid")
                            st.session_state.chat_history["chats_list"] = st.session_state["chats"]
                            AuthManager.save_chat_history(uid, st.session_state.chat_history)
                        st.rerun()

            active_chat = st.session_state["current_chat"]
            
            if active_chat:
                for idx, msg in enumerate(active_chat.get("messages", [])):
                    css = "chat-user" if msg["role"] == "user" else "chat-bot"
                    prefix = "Vous" if msg["role"] == "user" else "Coach"
                    st.markdown(
                        f"<div class='{css}'><strong>{prefix} :</strong> {msg['content']}</div>",
                        unsafe_allow_html=True
                    )

                if prompt := st.chat_input("Posez une question au Coach ou répondez à sa question..."):
                    active_chat["messages"].append({"role": "user", "content": prompt})

                    with st.spinner("Coach réfléchit..."):
                        if st.session_state.use_mock:
                            response = f"C'est une très bonne réponse pour {job['title']}. Avez-vous une autre question ?"
                        else:
                            response = CoachAgent().chat(
                                user_message=prompt,
                                job=job,
                                history=active_chat["messages"][:-1]
                            )

                        active_chat["messages"].append(
                            {"role": "assistant", "content": response}
                        )

                    st.session_state["current_chat"] = active_chat
                    for i, c in enumerate(st.session_state["chats"]):
                        if c["id"] == active_chat["id"]:
                            st.session_state["chats"][i] = active_chat
                            break

                    if st.session_state.get("logged_in") and st.session_state.get("user"):
                        uid = st.session_state.user.get("uid")
                        st.session_state.chat_history["chats_list"] = st.session_state["chats"]
                        AuthManager.save_chat_history(uid, st.session_state.chat_history)

                    st.rerun()'''

block_start = content.find(subtab2_old)
block_end = content.find('    if st.session_state.previous_page:', block_start)
if block_start != -1 and block_end != -1:
    new_content = new_content[:block_start] + subtab2_new + '\n\n' + new_content[block_end:]
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print('SUCCESS: Created app_new.py')
else:
    print('ERROR: block not found')
