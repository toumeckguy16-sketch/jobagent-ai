import streamlit as st
import base64

html_content = """
<html>
  <body style="background: red;">
    <h1>Test</h1>
    <button onclick="window.parent.postMessage({type: 'login'}, '*');">Click Me</button>
  </body>
</html>
"""

st.markdown("""
<script>
window.addEventListener('message', function(e) {
    if (e.data && e.data.type === 'login') {
        alert("Login requested!");
        window.location.href = "?action=login";
    }
});
</script>
""", unsafe_allow_html=True)

b64 = base64.b64encode(html_content.encode('utf-8')).decode('utf-8')
st.markdown(f'<iframe src="data:text/html;base64,{b64}" style="width:100vw; height:50vh;"></iframe>', unsafe_allow_html=True)
