with open('dist/assets/index-C3UY75jP.js', 'r', encoding='utf-8') as f:
    js = f.read()

# Let's inspect where Route components are mapped: <Route path="/security" element={...}
idx = js.find('path:"/security"')
print("Surroundings of /security:")
while idx != -1:
    print("At", idx, ":", js[idx-50:idx+250].encode('ascii', errors='backslashreplace').decode('ascii'))
    idx = js.find('path:"/security"', idx + 10)
