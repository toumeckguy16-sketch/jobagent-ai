import io
p = r'C:\Users\Stel_toumeck\Documents\codemem\ui\app_temp_backup.py'
o = r'C:\Users\Stel_toumeck\Documents\codemem\ui\app.py'
with io.open(p, 'r', encoding='utf-8') as f: c = f.read()
c = c.replace('\u00e2\u2020 ', '\u2190').replace('\u2190 ', '\u2190')
c = c.replace('\u00e2\u0153\u201c \u2713', '\u2713').replace('\u00e2\u0153\u201c', '\u2713')
c = c.replace('\u00e2\u0153\u2014', '\u2717')
c = c.replace('\u00e0la page', '\u00e0 la page')
with io.open(o, 'w', encoding='utf-8', newline='\n') as f: f.write(c)
print('SUCCESS')
