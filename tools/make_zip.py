"""Pack the addon into dist/ForeverRoute-<version>.zip (one top folder, ForeverRoute, ready to unzip into AddOns).

Usage: python -I tools/make_zip.py
"""
import os
import re
import zipfile

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
SRC = os.path.join(ROOT, 'addon', 'ForeverRoute')

toc = open(os.path.join(SRC, 'ForeverRoute.toc'), encoding='utf-8').read()
version = re.search(r'## Version: (\S+)', toc).group(1)
os.makedirs(os.path.join(ROOT, 'dist'), exist_ok=True)
out = os.path.join(ROOT, 'dist', 'ForeverRoute-%s.zip' % version)
with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for folder, _, files in os.walk(SRC):
        for name in sorted(files):
            path = os.path.join(folder, name)
            z.write(path, 'ForeverRoute/' + os.path.relpath(path, SRC).replace(os.sep, '/'))
print(out, '%.2f MB' % (os.path.getsize(out) / 1e6), len(zipfile.ZipFile(out).namelist()), 'files')
