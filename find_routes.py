with open('dist/assets/index-C3UY75jP.js', 'r', encoding='utf-8') as f:
    js = f.read()

pos = 0
found = []
while True:
    idx = js.find('path:"', pos)
    if idx == -1: break
    end = js.find('"', idx + 6)
    found.append(js[idx+6:end])
    pos = idx + 6

print("Router paths in React bundle:")
for p in sorted(list(set(found))):
    if len(p) < 40 and not p.startswith('M') and not p.startswith('C'): # filter svg paths
        print(" -", p)
