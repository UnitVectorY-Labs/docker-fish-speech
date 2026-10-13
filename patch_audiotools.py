"""Apply Fish upstream's explicit protobuf override to wheel metadata only.

Upstream uses uv.override-dependencies protobuf>=3.20,<6. Pip has no equivalent
override. Repacking updates RECORD correctly; audiotools Python is unchanged.
"""
from pathlib import Path

metadata, = Path('/tmp/audiotools-unpacked').glob('*/**/*.dist-info/METADATA')
text = metadata.read_text()
lines = text.splitlines()
matches = [i for i, line in enumerate(lines)
           if line.lower().startswith('requires-dist: protobuf')]
if len(matches) != 1:
    raise RuntimeError('Review changed audiotools metadata before overriding protobuf')
lines[matches[0]] = 'Requires-Dist: protobuf>=3.20,<6'
metadata.write_text('\n'.join(lines) + '\n')
