# Debian 13 / CPython 3.13 ABI matches Google's python3-debian13 runtime.
FROM python:3.13-slim-trixie@sha256:70729b46c69b4f1e97c4822c1af3df53a1476cf5ddc6c087c0c10bc3a5678c2f AS builder
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    git build-essential libsndfile1 ffmpeg libgomp1 tini \
    && rm -rf /var/lib/apt/lists/*
RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
COPY requirements*.txt /tmp/requirements/
COPY patch_audiotools.py collect_runtime.py /tmp/
RUN pip install -r /tmp/requirements/requirements-build.txt \
    && pip download --no-deps -r /tmp/requirements/requirements-audiotools.txt -d /tmp/audiotools-original \
    && wheel unpack /tmp/audiotools-original/*.whl -d /tmp/audiotools-unpacked \
    && python /tmp/patch_audiotools.py \
    && mkdir -p /tmp/audiotools-patched \
    && wheel pack /tmp/audiotools-unpacked/* -d /tmp/audiotools-patched
RUN pip install -r /tmp/requirements/requirements-torch.txt \
    && pip install /tmp/audiotools-patched/*.whl -r /tmp/requirements/requirements.txt \
    && pip check \
    && pip install --target /testdeps -r /tmp/requirements/requirements-test.txt
ARG FISH_REF=bdd39477922a89b904c6f2c7397f2a9bbcc60a0c
RUN git init /app/fish-speech \
    && git -C /app/fish-speech remote add origin https://github.com/fishaudio/fish-speech.git \
    && git -C /app/fish-speech fetch --depth 1 origin "$FISH_REF" \
    && git -C /app/fish-speech checkout --detach FETCH_HEAD \
    && rm -rf /app/fish-speech/.git
RUN python /tmp/collect_runtime.py \
    && rm /opt/venv/bin/python /opt/venv/bin/python3 /opt/venv/bin/python3.13 \
    && ln -s /usr/bin/python3 /opt/venv/bin/python \
    && ln -s python /opt/venv/bin/python3 \
    && printf 'home = /usr/bin\ninclude-system-site-packages = false\nversion = 3.13\nexecutable = /usr/bin/python3\n' > /opt/venv/pyvenv.cfg \
    && rm -rf /opt/venv/lib/python3.13/site-packages/pip* /opt/venv/bin/pip* \
    && mkdir -p /runtime-root/home/llama/.cache /runtime-root/app/checkpoints/s2-pro \
    && chown -R 1000:1000 /runtime-root/home/llama

FROM gcr.io/distroless/python3-debian13:nonroot@sha256:83aa8d4f74a4d7f7cf2d472054139bef71a927b76c680c0f2e1021d6b1d6d732 AS runtime
ARG FISH_REF=bdd39477922a89b904c6f2c7397f2a9bbcc60a0c
LABEL org.opencontainers.image.source="https://github.com/UnitVectorY-Labs/docker-fish-speech" \
      org.opencontainers.image.title="Fish Speech S2-Pro Distroless CUDA inference runtime" \
      org.opencontainers.image.licenses="MIT AND LicenseRef-Fish-Audio-Research-License" \
      ai.fish-speech.upstream.revision="$FISH_REF"
COPY --from=builder /runtime-root/ /
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app/fish-speech /app/fish-speech
COPY gateway.py /app/fish-speech/gateway.py
COPY LICENSE FISH_AUDIO_LICENSE Notice /usr/local/share/licenses/fish-speech/
ENV PATH=/opt/venv/bin:/usr/bin PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    HOME=/home/llama XDG_CACHE_HOME=/home/llama/.cache HF_HOME=/home/llama/.cache/huggingface \
    TORCH_HOME=/home/llama/.cache/torch NUMBA_CACHE_DIR=/home/llama/.cache/numba \
    TOKENIZERS_PARALLELISM=false HF_HUB_DISABLE_TELEMETRY=1 \
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
    NVIDIA_VISIBLE_DEVICES=all NVIDIA_DRIVER_CAPABILITIES=compute,utility
WORKDIR /app/fish-speech
USER 1000:1000
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10m --retries=3 \
    CMD ["/opt/venv/bin/python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/v1/health', timeout=2)"]
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/opt/venv/bin/python", "gateway.py"]

# Execute tests in the actual shell-less runtime, not just the build image.
FROM runtime AS test
COPY --from=builder /testdeps /testdeps
COPY tests /app/fish-speech/tests
ENV PYTHONPATH=/testdeps:/app/fish-speech
RUN ["/opt/venv/bin/python", "-m", "unittest", "discover", "-s", "tests", "-v"]
RUN ["/opt/venv/bin/python", "-c", "from pathlib import Path; Path('/tmp/tests-passed').touch()"]

FROM runtime AS final
COPY --from=test /tmp/tests-passed /usr/local/share/fish-cpu-tests-passed
