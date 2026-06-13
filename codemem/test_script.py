import streamlit as st
st.markdown("<script>alert('Hello from Markdown!');</script>", unsafe_allow_html=True)
st.write("If you see an alert, st.markdown scripts execute.")
