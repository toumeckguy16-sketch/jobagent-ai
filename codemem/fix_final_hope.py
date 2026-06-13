import os
ui_dir = r'C:\Users\Stel_toumeck\Documents\codemem\ui'
in_p = os.path.join(ui_dir, 'app_locked.py')
out_p = os.path.join(ui_dir, 'app.py')
with open(in_p, 'rb') as f: d = f.read()
d = d.replace(b'\xC3\xA2\xE2\x80\xA0\xC2\x90', b'\xE2\x86\x90')
with open(out_p, 'wb') as f: f.write(d)
print('HOPE_DONE')
