# Dependency update review (2026-10-13)

Every initial Dependabot PR was reviewed; compatible changes are incorporated:

| PR | Update | Decision |
|---|---|---|
| #1 | Torch 2.11 CUDA13 -> 2.14.1 CUDA13 | Blocked: no matching Torchaudio 2.14.1 CUDA13 wheel exists on the official index. Updating Torch alone recreates the old ABI mismatch. Retain matching 2.11.0 CUDA13 wheels; revisit when both release together. |
| #2 | NumPy 1.26.4 -> 2.5.2 | Merged; validated by final native runtime builds. |
| #3 | Python 3.12 -> 3.14 bookworm | Superseded by Google Distroless Python 3.13 / Debian 13, paired with python:3.13-slim-trixie builder. Distroless's supported interpreter is 3.13; installing a 3.14 venv into it is an ABI mismatch. This is not a relabeled slim final image. |
| #4 | CodeQL SARIF action 4.38.2 -> 4.38.3 | Merged with full SHA pin. |
| #5 | setup-uv 10.2.0 -> 10.3.0 | Merged with full SHA pin. |

Hydra 1.3.7, Lightning 2.6.6, Requests 2.34.2, python-multipart 0.0.32 and
Protobuf 5.29.6 replace initially vulnerable legacy pins. Transformers 4.57.3
is intentionally retained for this fixed Fish revision; major-version changes
must be tested separately. Existing Torch/Transformers advisories are not
silenced. Only trusted external model files/configurations should be used.

The server uses SDPA math with compilation disabled. No shell, package manager,
C++ compiler, CUDA toolkit or runtime TorchInductor compilation is needed.
Enabling upstream `--compile` would require a separate image and validation.
Python subprocesses launch by their executable path; ffmpeg/ffprobe and their
curated Debian 13 shared-library closure are retained for audio operations.
