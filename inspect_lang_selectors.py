with open('dist/assets/index-C3UY75jP.js', 'r', encoding='utf-8') as f:
    js = f.read()

# Let's inspect uT at 1323115
print("uT at 1323115:")
print(js[1323115-50:1323115+350].encode('ascii', errors='backslashreplace').decode('ascii'))

# Let's inspect k at 2717549
print("\nk at 2717549:")
print(js[2717549-50:2717549+350].encode('ascii', errors='backslashreplace').decode('ascii'))
