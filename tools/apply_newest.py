import zipfile, json, shutil, subprocess
from pathlib import Path
NEW='.tmp/openai.chatgpt-26.5527.60818-win32-x64.vsix'
spec=json.load(open('.tmp/spec/patch_spec_full.json',encoding='utf-8'))
out=Path('.tmp/new'); shutil.rmtree(out,ignore_errors=True); out.mkdir(parents=True)
with zipfile.ZipFile(NEW) as z: z.extractall(out)
ext=out/'extension'; wv=ext/'webview/assets'
# role -> newest filename by prefix
ROLES={'header':'header-','history':'history-','setting-storage':'setting-storage-',
       'helper':'window-app-action-helpers-','app-main':'app-main-'}
fnames={}
for role,pref in ROLES.items():
    matches=[p.name for p in wv.glob(pref+'*.js') if not p.name.endswith('.map')]
    print(f'role {role:16s} -> {matches}')
    fnames[role]=matches[0] if len(matches)==1 else None
# spec key -> (disk path, role)
SPECMAP={'out/extension.js':(ext/'out/extension.js',None),
 'webview/assets/header-BcIrXCOm-codexpatch.js':('header','header'),
 'webview/assets/history-Dc-JS86K-codexpatch.js':('history','history'),
 'webview/assets/setting-storage-Dtu-rhmp-codexpatch.js':('setting-storage','setting-storage'),
 'webview/assets/window-app-action-helpers-CuuVVkGv-codexpatch.js':('helper','helper'),
 'webview/assets/app-main-B4greUYI.js':('app-main','app-main')}
def apply_edits(text, edits, label):
    ops=[]; miss=0; total=0
    for e in edits:
        if e['inserted']=='-codexpatch' and e['removed']=='': continue
        total+=1
        if e['anchor'].endswith('.js.map'):   # big IIFE appended at EOF
            ops.append((len(text),0,e['inserted'])); continue
        anc=e['anchor']; i=text.find(anc)
        if i==-1 or text.find(anc,i+1)!=-1:
            miss+=1; print(f'    [{label}] MISS anchor ...{anc[-32:]!r}'); continue
        pos=i+len(anc)
        if e['removed'] and text[pos:pos+len(e['removed'])]!=e['removed']:
            miss+=1; print(f'    [{label}] REMOVED-MISMATCH ...{anc[-32:]!r}'); continue
        ops.append((pos,len(e['removed']),e['inserted']))
    ops.sort(key=lambda o:o[0],reverse=True)
    for pos,rl,ins in ops: text=text[:pos]+ins+text[pos+rl:]
    return text, total, miss
# apply code edits
for speckey,(disk,role) in SPECMAP.items():
    path = disk if role is None else (wv/fnames[role] if fnames[role] else None)
    if path is None: print(f'  {speckey}: ROLE FILE NOT FOUND'); continue
    txt=path.read_text(encoding='utf-8',errors='ignore')
    txt,total,miss=apply_edits(txt, spec[speckey]['edits'], speckey.split('/')[-1])
    path.write_text(txt,encoding='utf-8')
    print(f'  {speckey.split("/")[-1]:48s} edits {total-miss}/{total} applied')
# rename + stem rewrite using NEWEST stems
stems=[fnames[r][:-3] for r in ['setting-storage','history','header','helper'] if fnames[r]]
alljs=list(wv.glob('*.js'))+[ext/'out/extension.js']
for f in alljs:
    t=f.read_text(encoding='utf-8',errors='ignore'); orig=t
    for s in stems: t=t.replace(s,s+'-codexpatch')
    if t!=orig: f.write_text(t,encoding='utf-8')
for r in ['setting-storage','history','header','helper']:
    if fnames[r]:
        src=wv/fnames[r]; dst=wv/(fnames[r][:-3]+'-codexpatch.js'); src.rename(dst)
print('renamed + rewrote refs')
# node --check
node=shutil.which('node')
print('=== node --check ===')
for f in list(wv.glob('*.js'))+[ext/'out/extension.js']:
    if '-codexpatch' in f.name or f.name.startswith('app-main') or f.name=='extension.js':
        r=subprocess.run([node,'--check',str(f)],capture_output=True,text=True)
        if r.returncode!=0: print(f'  FAIL {f.name}: {r.stderr.strip().splitlines()[-1] if r.stderr else "?"}')
print('node --check done (only failures shown above)')
