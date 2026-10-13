# PyTorch's CUDA wheels supply runtime libraries; no toolkit/sglang is needed.
FROM python:3.12-slim-bookworm AS builder
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update && apt-get install -y --no-install-recommends git build-essential \
    && rm -rf /var/lib/apt/lists/*
RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
COPY requirements*.txt /tmp/requirements/
COPY patch_audiotools.py /tmp/patch_audiotools.py
RUN pip install -r /tmp/requirements/requirements-build.txt \
    && pip download --no-deps -r /tmp/requirements/requirements-audiotools.txt -d /tmp/audiotools-original \
    && wheel unpack /tmp/audiotools-original/*.whl -d /tmp/audiotools-unpacked \
    && python /tmp/patch_audiotools.py \
    && wheel pack /tmp/audiotools-unpacked/* -d /tmp/audiotools-patched \
    && pip install -r /tmp/requirements/requirements-torch.txt \
    && pip install /tmp/audiotools-patched/*.whl -r /tmp/requirements/requirements.txt \
    && pip check
ARG FISH_REF=bdd39477922a89b904c6f2c7397f2a9bbcc60a0c
RUN git init /app/fish-speech \
    && git -C /app/fish-speech remote add origin https://github.com/fishaudio/fish-speech.git \
    && git -C /app/fish-speech fetch --depth 1 origin "$FISH_REF" \
    && git -C /app/fish-speech checkout --detach FETCH_HEAD \
    && rm -rf /app/fish-speech/.git

FROM python:3.12-slim-bookworm AS runtime
ARG FISH_REF=bdd39477922a89b904c6f2c7397f2a9bbcc60a0c
LABEL org.opencontainers.image.source="https://github.com/UnitVectorY-Labs/docker-fish-speech" \
      org.opencontainers.image.title="Fish Speech S2-Pro CUDA inference runtime" \
      org.opencontainers.image.licenses="MIT AND LicenseRef-Fish-Audio-Research-License" \
      ai.fish-speech.upstream.revision="$FISH_REF"
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 ffmpeg libgomp1 ca-certificates tini \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 1000 llama && useradd --uid 1000 --gid 1000 --create-home llama \
    && mkdir -p /app/checkpoints/s2-pro /home/llama/.cache \
    && chown -R 1000:1000 /home/llama
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app/fish-speech /app/fish-speech
COPY gateway.py /app/fish-speech/gateway.py
COPY LICENSE FISH_AUDIO_LICENSE Notice /usr/local/share/licenses/fish-speech/
ENV PATH=/opt/venv/bin:$PATH PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    HOME=/home/llama XDG_CACHE_HOME=/home/llama/.cache HF_HOME=/home/llama/.cache/huggingface \
    TORCH_HOME=/home/llama/.cache/torch NUMBA_CACHE_DIR=/home/llama/.cache/numba \
    TOKENIZERS_PARALLELISM=false HF_HUB_DISABLE_TELEMETRY=1 \
    NVIDIA_VISIBLE_DEVICES=all NVIDIA_DRIVER_CAPABILITIES=compute,utility
WORKDIR /app/fish-speech
USER 1000:1000
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10m --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/v1/health', timeout=2)"]
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "gateway.py"]

# Build mandatory CPU-only checks before exporting the production image.
FROM runtime AS test
USER root
COPY requirements-test.txt /tmp/requirements-test.txt
RUN pip install --no-cache-dir -r /tmp/requirements-test.txt
COPY tests /app/fish-speech/tests
USER 1000:1000
RUN HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 python -m unittest discover -s tests -v \
    && touch /tmp/tests-passed

FROM runtime AS final
COPY --from=test /tmp/tests-passed /usr/local/share/fish-cpu-tests-passed
