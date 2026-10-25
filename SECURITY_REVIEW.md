# Local OSV review (2026-10-25)

Scanned with OSV-Scanner 2.7.0. The initial recursive source scan reported
8 distinct critical advisory groups (maximum CVSS >=9), deduplicated across
manifests and aliases:

| Package | Critical advisories | Remediation |
|---|---|---|
| Transformers 4.57.3 | CVE-2026-5241 | Upgrade to 5.10.2; also addresses the other five reported Transformers advisory groups. |
| Pillow 9.5.0 (OSV's audiotools resolution) | CVE-2023-50447, CVE-2026-112393, CVE-2026-112398, CVE-2026-112403, CVE-2026-112900 | Pin 13.0.0. |
| AnyIO 4.9.0 (OSV's httpx resolution) | CVE-2026-63374 | Pin 4.15.1. |
| Certifi 2026.7.22 (OSV's httpx/audiotools resolution) | PYSEC-2026-4320 / GHSA-6q48-6c7w-9gw2 | Pin 2026.10.23. |

The shared pins are installed in the runtime and included by each independently
resolved audiotools/test manifest. The audiotools repacking step selects only
its own wheel, since its download directory now also contains security-pinned
wheels. IDNA 3.20, Starlette 1.10.0 and FastAPI 0.162.0
also address noncritical findings in the resolved dependency graph. Filelock
4.2.4 replaces the CUDA index's 3.32.3 (one high and two low advisories). Setuptools
is pinned to 81.0.0 to fix CVE-2025-47273 while satisfying Torch's `<82` cap.

Transformers 5.10.2 deliberately overrides the fixed Fish source revision's
`<=4.57.3` cap. No Fish source is modified. The regression test creates a local
tokenizer fixture and exercises FishTokenizer loading, encoding/decoding,
special tokens, all 4096 semantic IDs and conversation prompt encoding. The
existing CPU serving-import and gateway lifecycle/error tests remain enabled.
An additional local offline check used the real S2-Pro tokenizer assets from
model revision `1de9996b6be38b745688de084d87a5633f714e4e` (no weights). It
passed English/Chinese round trips, ID parity against the native tokenizer.json
backend, all 4096 semantic IDs and conversation encoding with Transformers
5.10.2. These assets are not included in the image or CI tests.

Local AMD64 validation passed `pip check` and all 13 tests in the actual
Distroless runtime (six wrapper tests and seven upstream attention tests).
The assembled runtime's installed-package inventory exactly matched the
163-package OSV-scanned inventory.

This does not establish GPU synthesis or compatibility with every external
checkpoint; the older GPU validation in BUILD_VALIDATION.md is historical.

## Scan scope and reproduction

```sh
osv-scanner scan source -r . --format json --output-file /tmp/fish-source.json
osv-scanner scan source -r . --no-resolve --format json --output-file /tmp/fish-direct.json
docker build -t fish-security-test .
```

OSV's source resolver cannot resolve `torch==2.11.0+cu130` on its CUDA index,
and the runtime manifest can exceed its resolution iteration limit. Its source
report is therefore partial, even when a JSON report is produced. It resolves
manifests separately, so its old Pillow/Protobuf/Torch selections are not proof
that those versions were installed in the previous container. A fresh combined
resolution already chose patched Pillow/AnyIO/Certifi before these changes;
the explicit pins prevent vulnerable fallback selections and fix the isolated
manifest scans.

For a complete Python dependency resolution, use uv with the same Protobuf
metadata override as the Docker build and the matching Torch constraints:

```sh
sed '/^--/d' requirements-torch.txt > /tmp/fish-torch-constraints.txt
printf 'protobuf==5.29.6\n' > /tmp/fish-protobuf-override.txt
uv pip compile requirements.txt --python-version 3.13 \
  --override /tmp/fish-protobuf-override.txt \
  --constraint /tmp/fish-torch-constraints.txt \
  --index https://download.pytorch.org/whl/cu130 \
  --index-strategy unsafe-best-match --output-file /tmp/requirements.txt
osv-scanner scan source -L /tmp/requirements.txt --no-resolve
```

The updated direct pins and combined resolution have zero critical findings.
OSV also scanned the 163 installed Python distributions (excluding pip, which
the Docker build removes). That installed inventory has zero high or critical
findings and three remaining advisory groups in Torch and Setuptools.
Remaining combined-resolution findings include
`GHSA-rrmf-rvhw-rf47`, memory corruption in `torch.jit.script` (the OSV group
maximum CVSS is 5.3; GitHub labels the advisory low).
Its fix is Torch >=2.13; the official Torchaudio index still has no matching
CUDA release above 2.11. Keep the pair synchronized.

The CUDA Torch 2.11 wheel also requires `setuptools<82`, preventing the
Setuptools >=84.1 fixes for `GHSA-h35f-9h28-mq5c` (moderate) and
`GHSA-xmj3-9gf7-h52w` (low). The Docker build now applies the Torch/Torchaudio
pins as constraints to subsequent runtime installs, preventing pip from
silently replacing Torch to satisfy other dependency updates. No findings
are suppressed.

These Python scans do not audit Debian/CUDA binaries or prove GPU inference
correctness. Retest actual GPU synthesis before deploying the updated image.
