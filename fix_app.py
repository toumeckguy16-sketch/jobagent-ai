import re, io, os, tempfile

p = r'C:\Users\Stel_toumeck\Documents\codemem\ui\app.py'
p_out = os.path.join(tempfile.gettempdir(), 'app_fixed.py')

c = io.open(p, 'r', encoding='utf-8', errors='replace').read()

# Remove icon variable assignments (the 3 lines: icon = "...")
c = re.sub(r'\n(\s+)icon = [^\n]+', '', c)

# Remove {icon} from the markdown line in quiz options
c = c.replace('{icon} ', '')

# Fix quiz summary "Detail par question" - replace broken f-string icon expression
# The line looks like: f"{'corrupted' 'ok_icon' if ok else 'fail_icon'} **Q{qid}.**"
c = re.sub(r"f\"\{'[^']*'[^']*'[^']*' if ok else '[^']*'\} \*\*Q\{qid\}\.\*\* \"",
           r'f"**Q{qid}.** "', c)

# Fix back buttons - replace the corrupted label
c = re.sub(r'st\.button\("[^"]{1,10}", key="back_analyse_end"',
           'st.button("Retour", key="back_analyse_end"', c)
c = re.sub(r'st\.button\("[^"]{1,10}", key="back_prep_end"',
           'st.button("Retour", key="back_prep_end"', c)

f = open(p_out, 'w', encoding='utf-8')
f.write(c)
f.close()
print('WRITTEN_TO:', p_out)
