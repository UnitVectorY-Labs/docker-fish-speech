"""Correct NVIDIA's invalid SBSA wheel tag after verifying ARM64 ELF binaries.

The 0.8.0 filename is manylinux2014_aarch64, but internal WHEEL says sbsa,
which pip check rejects. No binaries, requirements or sources are modified.
"""
import base64
import csv
import hashlib
import importlib.metadata
import io
import platform

if platform.machine() == 'aarch64':
    dist = importlib.metadata.distribution('nvidia-cusparselt-cu13')
    wheel_file, = [file for file in dist.files if str(file).endswith('.dist-info/WHEEL')]
    wheel = dist.locate_file(wheel_file)
    text = wheel.read_text()
    if 'manylinux2014_sbsa' in text:
        binaries = [dist.locate_file(file) for file in dist.files if '.so' in file.name]
        if not binaries:
            raise RuntimeError('No cuSPARSELt shared library to validate')
        for binary in binaries:
            with binary.open('rb') as handle:
                header = handle.read(20)
            if header[:6] != b'\x7fELF\x02\x01' or int.from_bytes(header[18:20], 'little') != 183:
                raise RuntimeError(f'Not an ARM64 ELF binary: {binary}')
        data = text.replace('manylinux2014_sbsa', 'manylinux2014_aarch64').encode()
        wheel.write_bytes(data)
        record_file, = [file for file in dist.files if str(file).endswith('.dist-info/RECORD')]
        record = dist.locate_file(record_file)
        rows = list(csv.reader(io.StringIO(record.read_text())))
        for row in rows:
            if row[0] == str(wheel_file):
                row[1] = 'sha256=' + base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode().rstrip('=')
                row[2] = str(len(data))
        with record.open('w', newline='') as handle:
            csv.writer(handle).writerows(rows)
        print('Corrected cuSPARSELt WHEEL tag; verified ARM64 ELF binaries')
