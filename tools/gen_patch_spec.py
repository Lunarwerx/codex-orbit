"""Generate a data-driven patch spec from (stock 26.5519 -> captured codex_assets).
Each edit = {anchor (stable stock text BEFORE the edit), removed, inserted}.
Uses a fast greedy-resync differ (O(n) typical) instead of difflib (O(n^2))."""
import zipfile, json, sys
from pathlib import Path
STOCK='Potentials/Codex/openai.chatgpt-26.5519.32039.vsix'
stock=zipfile.ZipFile(STOCK); names=set(stock.namelist())
def sget(rel):
    p='extension/'+rel; return stock.read(p).decode('utf-8','ignore') if p in names else None
def pget(rel): return open('stable/codex_assets/'+rel,encoding='utf-8',errors='ignore').read()

def greedy_edits(S,P,K=48,WIN=400000):
    """Return list of (pos_in_S, removed_len, inserted_text). Walks both strings,
    resyncing on the next K-char chunk of S found in P."""
    edits=[]; i=0; j=0; n=len(S); m=len(P)
    # fast common prefix
    while i<n and j<m and S[i]==P[j]: i+=1; j+=1
    while i<n or j<m:
        # try resync: find S[i:i+K] in P[j:]
        chunk=S[i:i+K]
        if not chunk:
            # remainder of P is pure insertion at end
            if j<m: edits.append((i,0,P[j:])); j=m
            break
        k=P.find(chunk, j, j+WIN) if len(chunk)==K else P.find(chunk,j)
        if k==-1:
            # S chunk not found ahead in P: treat one char of S as removed (advance i)
            # but first, accumulate by searching for a later S anchor. Simplify: find next
            # long S-substring that appears in P.
            # advance i by 1 (deletion) — rare for our insert-heavy patch
            # record nothing yet; accumulate into a pending replace
            # Find next resync: smallest a such that S[i+a:i+a+K] in P[j:]
            a=1; found=False
            while i+a<=n:
                c=S[i+a:i+a+K]
                if not c: break
                kk=P.find(c, j, j+WIN) if len(c)==K else P.find(c,j)
                if kk!=-1:
                    # S[i:i+a] removed, P[j:kk] inserted
                    edits.append((i, a, P[j:kk])); i+=a; j=kk; found=True; break
                a+=1
            if not found:
                edits.append((i, n-i, P[j:])); i=n; j=m
            continue
        if k>j:
            # P[j:k] inserted at position i
            edits.append((i,0,P[j:k])); j=k
        # now S[i:i+K]==P[j:j+K]; consume the matching run
        while i<n and j<m and S[i]==P[j]: i+=1; j+=1
    return edits

files=[('package.json','package.json'),
 ('out/extension.js','out/extension.js'),
 ('webview/assets/header-BcIrXCOm-codexpatch.js','webview/assets/header-BcIrXCOm.js'),
 ('webview/assets/history-Dc-JS86K-codexpatch.js','webview/assets/history-Dc-JS86K.js'),
 ('webview/assets/setting-storage-Dtu-rhmp-codexpatch.js','webview/assets/setting-storage-Dtu-rhmp.js'),
 ('webview/assets/window-app-action-helpers-CuuVVkGv-codexpatch.js','webview/assets/window-app-action-helpers-CuuVVkGv.js'),
 ('webview/assets/app-main-B4greUYI.js','webview/assets/app-main-B4greUYI.js')]
spec={}
for prel,srel in files:
    S=sget(srel); P=pget(prel)
    edits=greedy_edits(S,P)
    # verify edits reproduce P exactly
    out=[]; pos=0
    for (p,rl,ins) in edits:
        out.append(S[pos:p]); out.append(ins); pos=p+rl
    out.append(S[pos:])
    rebuilt=''.join(out)
    ok = (rebuilt==P)
    def uniq_anchor(S,p):
        L=60
        while L<=4000:
            a=S[max(0,p-L):p]
            if a and S.count(a)==1: return a
            L+=60
        return S[max(0,p-4000):p]
    spec[prel]={'srel':srel,'edits':[{'pos':p,'anchor':uniq_anchor(S,p),'removed':S[p:p+rl],'inserted':ins} for (p,rl,ins) in edits],'reproduces':ok}
    print('%-58s %3d edits  reproduces=%s' % (prel.split('/')[-1], len(edits), ok),flush=True)
Path('.tmp/spec').mkdir(parents=True,exist_ok=True)
json.dump(spec,open('.tmp/spec/patch_spec_full.json','w',encoding='utf-8'),ensure_ascii=False)
print('wrote .tmp/spec/patch_spec_full.json',flush=True)
