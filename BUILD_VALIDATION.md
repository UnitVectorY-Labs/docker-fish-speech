# Published Distroless build

- Build/source commit: `ab38b6aff02deea12d780d6a1cfd3a507f7d9cd8`
- Successful run: https://github.com/UnitVectorY-Labs/docker-fish-speech/actions/runs/38484302967
- Image: `ghcr.io/unitvectory-labs/docker-fish-speech`
- Immutable tag: `sha-ab38b6aff02deea12d780d6a1cfd3a507f7d9cd8-run-38484302967-1`
- Multi-architecture digest: `sha256:619352611ec9e77091700d04a5631eb140e9fd581699e977543e9b04fac9e56e`
- `current` resolves to that multi-architecture digest.
- `current-arm64` index: `sha256:cf7889d02e8b7569b85a09d24019f71430fba3942ae380accce705133129f71f`
- ARM64 image manifest: `sha256:f8d8edf6f693a50050568ed1573e2b121a6cfbdae0385e5d00967201920240ea`
- `current-amd64` index: `sha256:daf99ecd70536b128dd78efb0dd137e9a1d056c55a1614b0913dbb8cd54b89c7`
- AMD64 image manifest: `sha256:cbf1b568309ceee7205150293e0a8db7933779187c4c09a74665b0fb359c4016`
- Corresponding immutable `-arm64` / `-amd64` tags also exist.

Anonymous registry requests (no GitHub or Docker credentials) returned HTTP
200 for all three current tags and the immutable multi-architecture tag.
There is no current GHCR visibility blocker. OCI provenance attestations have
`unknown/unknown` platform and may be shown as untagged children; they are not
missing final image tags.

## Actual validation

Both native runners passed all **12 CPU tests** in the actual Google Distroless
runtime: complete Fish serving imports, Torch/Torchaudio version agreement,
upstream tiny-model active-KV/SDPA tests, multipart input/default/ignored voice,
health/error propagation, SIGTERM/timeout kill/reap behavior, UID 1000 writable
HOME, ffmpeg/ffprobe execution, and absent shell/apt/pip. `pip check` passed.
ARM64 compiled CUDA architectures were `sm_80 sm_90 sm_100 sm_110 sm_120`;
PyTorch's own table accepts sm_120 code for GB10 sm_121.

Final base is the real `gcr.io/distroless/python3-debian13:nonroot` index pinned
to `sha256:83aa8d4f74a4d7f7cf2d472054139bef71a927b76c680c0f2e1021d6b1d6d732`.
The matching builder is Python 3.13 / Debian 13 (`python:3.13-slim-trixie`).
Torch and Torchaudio are 2.11.0+cu130; Transformers is deliberately 4.57.3;
NumPy is 2.5.2. Other declared runtime requirements remain in the pip manifests.
Reviewed dependency blocks and metadata-only fixes are documented in
[DEPENDENCY_REVIEW.md](DEPENDENCY_REVIEW.md).

**This final digest has not been GPU-tested by the repository build.** The
parent deployment session must validate this exact digest on GB10 before
switching configuration. A previous bookworm image passed standalone GB10
synthesis, but that is not validation of this Distroless/updated-NumPy image.
No co-load or concurrent-model memory safety claim is made. Docker cgroup
memory limits do not bound all GPU unified-memory physical consumption.

## Exact standalone command for final GPU validation

Do not run until the GPU is available and the checkpoint directory is complete.

```sh
docker run --rm --gpus all --name fish-speech-final \
  --user 1000:1000 -p 127.0.0.1:8080:8080 \
  -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 \
  -v /home/jared/.cache/tts-models/s2-pro:/app/checkpoints/s2-pro:ro \
  -v fish-speech-final-cache:/home/llama/.cache \
  ghcr.io/unitvectory-labs/docker-fish-speech:sha-ab38b6aff02deea12d780d6a1cfd3a507f7d9cd8-run-38484302967-1@sha256:619352611ec9e77091700d04a5631eb140e9fd581699e977543e9b04fac9e56e
```

The image defaults to offline mode. Mount the complete externally provisioned
S2-Pro directory, including `codec.pth`, model/config/tokenizer files. Nothing
downloads model weights during build or default runtime. Bind-mounted caches
must be writable by UID/GID 1000; a fresh named volume inherits image ownership.
Port 8080 exposes `/v1/health` and multipart `/v1/audio/speech`; only the child
uses loopback port 8081. `input` is required, `response_format` defaults to WAV,
and `voice` is ignored. No cloning or streaming route is exposed.

All five initial Dependabot PRs are accounted for: #2, #4 and #5 merged; #1
closed with the absent matching Torchaudio CUDA wheel explanation; #3 closed
as superseded by the ABI-matched Distroless migration. No PR remained open at
publication verification. Earlier failed builds are historical, not the final run.
