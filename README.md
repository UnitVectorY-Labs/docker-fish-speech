# Fish Speech S2-Pro CUDA runtime

**Built with Fish Audio.**

Purpose-built Fish Speech inference image for NVIDIA GB10 (ARM64, sm_121),
also built natively for AMD64. Replaces the heavyweight sglang base with
Google **Distroless `python3-debian13:nonroot`**, Python 3.13 and matching
**PyTorch/Torchaudio 2.11.0+cu130** wheels. Builder and runtime base indexes
are digest-pinned, and the builder uses the same Debian 13 / Python 3.13 ABI.
CUDA runtime libraries come from the wheels; the host needs a compatible
NVIDIA driver and NVIDIA Container Toolkit. No CUDA compiler, sglang, vLLM,
web UI, model weights or credentials are included.
The final image contains no shell, apt or pip. Only ffmpeg/ffprobe, tini,
their curated shared-library closure and Python inference dependencies are
added to the real Google Distroless base. Subprocess launch, signal handling
and NumPy/Torch imports are tested in that final runtime. Compilation stays
disabled: a compiler/toolkit is not needed for the SDPA math inference path.
The CUDA13 wheels include `sm_120`, which PyTorch's compatibility table
accepts for GB10 `sm_121`; build tests check that table without accessing a GPU.
An exact `sm_121` cubin is not required, nor claimed.

Upstream is fixed at
[`bdd39477922a89b904c6f2c7397f2a9bbcc60a0c`](https://github.com/fishaudio/fish-speech/tree/bdd39477922a89b904c6f2c7397f2a9bbcc60a0c).
Transformers remains 4.57.3. The inference code uses SDPA math, without
FlashAttention or compilation. Lightning and TensorBoard remain because
upstream utilities and the DAC audiotools dependency import them eagerly.
Datasets, wandb, gradio, pyaudio, ModelScope and other unused training/UI
dependencies are omitted. Build tests import the complete serving path.

Audiotools' obsolete Protobuf `<3.20` wheel metadata is explicitly repacked to
`>=3.20,<6`, matching Fish upstream's `uv.override-dependencies`; Python source
is unchanged. Protobuf 5.29.6 is installed and `pip check` must pass.
Transformers 4.57.3 and Torch 2.11 still have known advisories: keep the API
private, use only trusted locally provisioned checkpoints/configuration, and
review Dependabot alerts before deployment. Compatibility pins are not a
claim that the image is vulnerability-free.

## Run

Prepare the complete `fishaudio/s2-pro` checkpoint directory **outside the
image**, including `codec.pth`, model shards, tokenizer and configuration.
Builds never download weights. The mounted files must be readable by UID 1000.

```sh
docker run --rm --gpus all --name fish-speech \
  --user 1000:1000 -p 127.0.0.1:8080:8080 \
  -v /home/jared/.cache/tts-models/s2-pro:/app/checkpoints/s2-pro:ro \
  -v fish-speech-cache:/home/llama/.cache \
  ghcr.io/unitvectory-labs/docker-fish-speech:current
```

The default checkpoint path can be changed with `FISH_CHECKPOINT`.
HOME and caches are writable for the default UID/GID 1000. Bind-mounted
cache directories must be owned by that user. No authentication is provided;
publish only on trusted networks or behind an authenticated proxy.

The gateway binds `0.0.0.0:8080` and manages the official upstream child on
**loopback-only `127.0.0.1:8081`**. `/v1/health` returns 503 while the child is
loading or dead and otherwise proxies upstream readiness. Shutdown terminates
and reaps the child, killing it after a 30-second grace period; tini reaps
orphan descendants.

```sh
curl http://localhost:8080/v1/health
curl -f -F 'input=Hello from Fish Speech.' -F response_format=wav \
  -F voice=default http://localhost:8080/v1/audio/speech -o fish.wav
```

The request is **multipart form data**, not the OpenAI JSON schema:
`input` is required, `response_format` defaults to `wav`, and `voice` is
accepted but **ignored**. No voice selection, cloning/reference uploads,
streaming or upstream management routes are exposed. An extra `model` field
from llama-swap is ignored. The upstream schema accepts WAV, MP3 and FLAC;
WAV is the recommended format. Errors are forwarded, with gateway 502 on
upstream transport failure. This adapter is not a complete OpenAI API.

## Builds and validation

Actions builds on native `ubuntu-24.04-arm` and `ubuntu-24.04` runners;
each image must pass CPU Torch/Torchaudio version, serving-import and mocked
multipart/health/lifecycle tests before publication. Tests run offline and
do not load weights or use a GPU. Production images exclude test-only httpx.

Builds run on relevant runtime/dependency pushes, `workflow_dispatch`, and
Saturday **02:00 UTC**. Dependabot checks Docker, pip and Actions weekly.
Actions are SHA-pinned. Both platform digests must succeed before updating
`current`, `current-arm64` and `current-amd64`; fixed-build tags are
`sha-<full-source-sha>-run-<run-id>-<attempt>` and are not overwritten by
scheduled rebuilds. Dependencies and base tags can evolve, so use a published
image digest when exact reproducibility is required.

All initial Dependabot PRs were reviewed; see [DEPENDENCY_REVIEW.md](DEPENDENCY_REVIEW.md)
for incorporated bumps and the genuine Python 3.14/Torch 2.14 compatibility blocks.

**GB10 validation:** on 2026-10-13 UTC, final ARM64 manifest
`sha256:619352611ec9e77091700d04a5631eb140e9fd581699e977543e9b04fac9e56e`
(source `ab38b6aff02deea12d780d6a1cfd3a507f7d9cd8`,
[build 38484302967](https://github.com/UnitVectorY-Labs/docker-fish-speech/actions/runs/38484302967))
passed isolated GPU startup and synthesis with read-only external checkpoints,
a fresh writable cache and Hugging Face offline mode. Health/speech returned
200; the output was valid, non-silent mono PCM16 WAV at 44.1 kHz, 4.32 seconds.
Missing input returned 422. Shutdown returned normal SIGTERM exit 143, with no
OOM, no remaining container and physical memory recovery.

Observed standalone host-memory demand was approximately **40 GiB**, including
GPU/unified-memory allocations that Docker's accounting does not see. A 32g
cgroup limit is not proof that this backend fits beside another large model.
On 2026-10-14 UTC this same image also passed llama-swap synthesis, missing-input
checks, sequential Breeze → Fish → Step switching, graceful SIGTERM exit 143,
and host memory recovery. Actual container image IDs matched standalone tests.
AMD64 GPU synthesis and TTS/LLM co-loading remain untested. Retest updated
images; successful CPU builds alone are not proof of GPU synthesis.

**Publication verified:** the final Distroless build passed on both native
architectures, including 12 CPU tests each, and anonymous GHCR requests for
`current`, both platform tags and the immutable tag returned HTTP 200.
See [BUILD_VALIDATION.md](BUILD_VALIDATION.md) for the exact tested build,
digests and pinned run command. Untagged OCI attestation children are normal;
the final image manifests have actual named tags.

## License

The wrapper/container automation is MIT (see [LICENSE](LICENSE)). Fish Speech
source and **S2-Pro weights** are governed by the
[Fish Audio Research License](https://github.com/fishaudio/fish-speech/blob/bdd39477922a89b904c6f2c7397f2a9bbcc60a0c/LICENSE)
and the [model card](https://huggingface.co/fishaudio/s2-pro).
This is not an MIT license grant for the model or upstream code; review their
research/non-commercial and redistribution terms before use. No weights are
redistributed by this repository or image.
