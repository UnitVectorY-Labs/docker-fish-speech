"""Copy only explicit audio executables and their dynamic-library closure.

Build-time tooling only; never copy a shell, package manager or full /usr/lib.
Debian 13 matches the final Distroless distribution. Its glibc/loader stay
authoritative, rather than being overwritten by builder libraries.
"""
import re
import shutil
import subprocess
from pathlib import Path

root = Path('/runtime-root')
skip = re.compile(r'^(libc\.so|libm\.so|libpthread\.so|libdl\.so|librt\.so|ld-linux)')
pending = [Path('/usr/bin/ffmpeg'), Path('/usr/bin/ffprobe'), Path('/usr/bin/tini')]
cache = subprocess.check_output(['ldconfig', '-p'], text=True)
for name in ['libsndfile.so.1', 'libgomp.so.1']:
    match = re.search(r'\s' + re.escape(name) + r' .* => (\S+)', cache)
    if match is None:
        raise RuntimeError(f'Missing runtime library: {name}')
    pending.append(Path(match.group(1)))
seen = set()
while pending:
    source = pending.pop()
    if source in seen or skip.match(source.name):
        continue
    seen.add(source)
    destination = root / str(source).lstrip('/')
    if str(source).startswith('/lib/'):
        destination = root / 'usr' / str(source).lstrip('/')
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source.resolve(), destination)
    output = subprocess.check_output(['ldd', str(source)], text=True)
    if 'not found' in output:
        raise RuntimeError(output)
    pending.extend(Path(path) for path in re.findall(r'(/\S+)\s+\(', output))
print(f'Curated {len(seen)} runtime executables/libraries')
