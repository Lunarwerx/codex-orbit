"""Prove the dynamic engine reproduces the captured baseline from stock 26.5519:
   rename(4 files) + anchored code-edit replay  ==  stable/codex_assets ?"""
import zipfile, json
STOCK='Potentials/Codex/openai.chatgpt-26.5519.32039.vsix'
z=zipfile.ZipFile(STOCK); names=set(z.namelist())
def sget(rel):
    p='extension/'+rel; return z.read(p).decode('utf-8','ignore') if p in names else None
def pget(rel): return open('stable/codex_assets/'+rel,encoding='utf-8',errors='ignore').read()
spec=json.load(open('.tmp/spec/patch_spec_full.json',encoding='utf-8'))

RENAME_STEMS=['setting-storage-Dtu-rhmp','history-Dc-JS86K','header-BcIrXCOm','window-app-action-helpers-CuuVVkGv']
def stem_rewrite(text):
    for s in RENAME_STEMS:
        text=text.replace(s, s+'-codexpatch')
    return text

def apply_code_edits(text, edits):
    # locate all anchors in ORIGINAL text, then splice by descending position
    ops=[]
    for e in edits:
        if e['inserted']=='-codexpatch' and e['removed']=='':
            continue  # handled by stem_rewrite
        anc=e['anchor']
        if not anc:
            ops.append((0,e['removed'],e['inserted'])); continue
        i=text.find(anc)
        if i==-1: return None, f"anchor not found: ...{anc[-30:]!r}"
        if text.find(anc, i+1)!=-1: return None, f"anchor NOT UNIQUE: ...{anc[-30:]!r}"
        pos=i+len(anc)
        if e['removed'] and text[pos:pos+len(e['removed'])]!=e['removed']:
            return None, f"removed mismatch at ...{anc[-30:]!r}"
        ops.append((pos,e['removed'],e['inserted']))
    ops.sort(key=lambda o:o[0], reverse=True)
    for pos,rem,ins in ops:
        text=text[:pos]+ins+text[pos+len(rem):]
    return text, None

JSFILES=[('out/extension.js','out/extension.js'),
 ('webview/assets/header-BcIrXCOm-codexpatch.js','webview/assets/header-BcIrXCOm.js'),
 ('webview/assets/history-Dc-JS86K-codexpatch.js','webview/assets/history-Dc-JS86K.js'),
 ('webview/assets/setting-storage-Dtu-rhmp-codexpatch.js','webview/assets/setting-storage-Dtu-rhmp.js'),
 ('webview/assets/window-app-action-helpers-CuuVVkGv-codexpatch.js','webview/assets/window-app-action-helpers-CuuVVkGv.js'),
 ('webview/assets/app-main-B4greUYI.js','webview/assets/app-main-B4greUYI.js')]
allok=True
for prel,srel in JSFILES:
    S=sget(srel)
    txt,err=apply_code_edits(S, spec[prel]['edits'])
    if not err: txt=stem_rewrite(txt)
    if err:
        print('%-52s ENGINE-ERROR: %s'%(prel.split('/')[-1],err)); allok=False; continue
    want=pget(prel)
    ok = txt==want
    allok = allok and ok
    print('%-52s %s%s'%(prel.split('/')[-1], 'MATCH' if ok else 'DIFF', '' if ok else f' (got {len(txt)} want {len(want)})'))
print('GATE', 'GREEN' if allok else 'RED')
