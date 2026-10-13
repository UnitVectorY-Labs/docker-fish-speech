# Fish Speech S2-Pro CUDA runtime

**Built with Fish Audio.**

Purpose-built Fish Speech inference image for NVIDIA GB10 (ARM64, sm_121),
also built natively for AMD64. Replaces the heavyweight sglang base with
Python 3.12 slim and matching **PyTorch/Torchaudio 2.11.0+cu130** wheels.
CUDA runtime libraries come from the wheels; the host needs a compatible
NVIDIA driver and NVIDIA Container Toolkit. No CUDA compiler, sglang, vLLM,
web UI, model weights or credentials are included.

Upstream is fixed at
[`bdd39477922a89b904c6f2c7397f2a9bbcc60a0c`](https://github.com/fishaudio/fish-speech/tree/bdd39477922a89b904c6f2c7397f2a9bbcc60a0c).
Transformers remains 4.57.3. The inference code uses SDPA math, without
FlashAttention or compilation. Lightning and TensorBoard remain because
upstream utilities and the DAC audiotools dependency import them eagerly.
Datasets, wandb, gradio, pyaudio, ModelScope and other unused training/UI
dependencies are omitted. Build tests import the complete serving path.

## Run

Prepare the complete `fishaudio/s2-pro` checkpoint directory **outside the
image**, including `codec.pth`, model shards, tokenizer and configuration.
Builds never download weights. The mounted files must be readable by UID 1000.

```sh
docker run --rm --gpus all --name fish-speech \
  --user 1000:1000 -p 8080:8080 \
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
`current`; fixed-build tags are
`sha-<full-source-sha>-run-<run-id>-<attempt>` and are not overwritten by
scheduled rebuilds. Dependencies and base tags can evolve, so use a published
image digest when exact reproducibility is required.

**Validation boundary:** the previous sglang-based image worked on GB10 with
this upstream revision. This replacement has no claimed GPU/audio validation;
matching CUDA wheels and successful CPU builds are not proof of synthesis.
GB10 GPU synthesis and output WAV quality must be verified before deployment.
AMD64 GPU synthesis is likewise untested. No deployment configuration is changed.

First GHCR publication defaults to **private**. A package administrator must
make the package public in GitHub package settings before anonymous pulls;
the publishing token and local CLI token do not change package visibility.

## License

The wrapper/container automation is MIT (see [LICENSE](LICENSE)). Fish Speech
source and **S2-Pro weights** are governed by the
[Fish Audio Research License](https://github.com/fishaudio/fish-speech/blob/bdd39477922a89b904c6f2c7397f2a9bbcc60a0c/LICENSE)
and the [model card](https://huggingface.co/fishaudio/s2-pro).
This is not an MIT license grant for the model or upstream code; review their
research/non-commercial and redistribution terms before use. No weights are
redistributed by this repository or image.
