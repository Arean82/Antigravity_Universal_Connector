with open('dist/assets/index-C3UY75jP.js', 'r', encoding='utf-8') as f:
    js = f.read()

needles = [':"zh"', '="zh"', '("zh"', '["zh"', '"zh-CN"', '"zh-TW"', '"zh"']
for n in needles:
    pos = 0
    matches = []
    while True:
        idx = js.find(n, pos)
        if idx == -1: break
        matches.append(idx)
        pos = idx + len(n)
    print(n, 'total matches:', len(matches))
    for m in matches[:5]:
        print('  at', m, ':', js[max(0, m-40):m+60].encode('ascii', errors='backslashreplace').decode('ascii'))
