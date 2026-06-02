"""Generate the self-contained dynamic stable/patch_codex.py from the extracted
spec. Embeds the edits (gzip+base64); no codex_assets needed at runtime."""
import json, gzip, base64
spec=json.load(open('.tmp/spec/patch_spec_full.json',encoding='utf-8'))

# roles that carry code edits (+ which get the -codexpatch rename)
ROLE_SPEC={
 'host':        ('out/extension.js', False),
 'header':      ('webview/assets/header-BcIrXCOm-codexpatch.js', True),
 'history':     ('webview/assets/history-Dc-JS86K-codexpatch.js', True),
 'setting-storage':('webview/assets/setting-storage-Dtu-rhmp-codexpatch.js', True),
 'helper':      ('webview/assets/window-app-action-helpers-CuuVVkGv-codexpatch.js', True),
}
ROLE_PREFIX={'header':'header-','history':'history-','setting-storage':'setting-storage-','helper':'window-app-action-helpers-'}

embed={'roles':{}}
for role,(speckey,rename) in ROLE_SPEC.items():
    edits=[]
    for e in spec[speckey]['edits']:
        if e['inserted']=='-codexpatch' and e['removed']=='':
            continue  # cache-bust rename -> handled programmatically
        op='append' if e['anchor'].endswith('.js.map') else 'anchor'
        edits.append({'op':op,'anchor':e['anchor'],'removed':e['removed'],'inserted':e['inserted']})
    embed['roles'][role]={'prefix':ROLE_PREFIX.get(role),'rename':rename,'edits':edits}

blob=base64.b64encode(gzip.compress(json.dumps(embed,ensure_ascii=False).encode('utf-8'))).decode('ascii')
print('embed blob bytes:', len(blob), ' roles:', {r:len(v['edits']) for r,v in embed['roles'].items()})

# package.json contributions (literal, version-agnostic)
PKG = '''PKG_COMMANDS = [
    {"command": "chatgpt.renameTask", "title": "Rename Task", "category": "Codex", "icon": "$(edit)"},
    {"command": "chatgpt.pinTask", "title": "Pin Task", "category": "Codex", "icon": "$(pinned)"},
    {"command": "chatgpt.unpinTask", "title": "Unpin Task", "category": "Codex", "icon": "$(pinned-dirty)"},
    {"command": "chatgpt.starTask", "title": "Star Task", "category": "Codex", "icon": "$(star-full)"},
    {"command": "chatgpt.unstarTask", "title": "Unstar Task", "category": "Codex", "icon": "$(star-empty)"},
]
_WV = "(webviewId == 'chatgpt.sidebarView' || webviewId == 'chatgpt.sidebarSecondaryView') && codexTask == true"
PKG_MENUS = {
    "webview/context": [
        {"command": "chatgpt.renameTask", "group": "navigation@1", "when": _WV},
        {"command": "chatgpt.pinTask", "group": "navigation@2", "when": _WV + " && !codexPinned"},
        {"command": "chatgpt.unpinTask", "group": "navigation@2", "when": _WV + " && codexPinned == true"},
        {"command": "chatgpt.starTask", "group": "navigation@3", "when": _WV + " && !codexStarred"},
        {"command": "chatgpt.unstarTask", "group": "navigation@3", "when": _WV + " && codexStarred == true"},
    ],
    "chat/chatSessions": [
        {"command": "chatgpt.renameTask", "group": "inline@50", "when": "chatSessionType == openai-codex"},
    ],
}'''

open('.tmp/embed_blob.txt','w').write(blob)
open('.tmp/pkg_block.txt','w',encoding='utf-8').write(PKG)
print('wrote .tmp/embed_blob.txt and .tmp/pkg_block.txt')
