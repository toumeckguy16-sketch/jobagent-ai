import io
p = r'C:\Users\Stel_toumeck\Documents\codemem\ui\app.py'
with open(p, 'rb') as f: d = f.read()
d = d.replace(b'\xC3\xA2\xE2\x80\xA0\xC2\x90', b'\xE2\x86\x90')
d = d.replace(b'\xC3\xA2\xC5\x93\xE2\x80\x9C \xE2\x9C\x93', b'\xE2\x9C\x93')
d = d.replace(b'\xC3\xA2\xC5\x93\xE2\x80\x9C', b'\xE2\x9C\x93')
d = d.replace(b'\xC3\xA2\xC5\x93\xE2\x80\x94', b'\xE2\x9C\x97')
d = d.replace(b'\xC3\xA0la page', b'\xC3\xA0 la page')
with open(p, 'wb') as f: f.write(d)
print('DONE')
