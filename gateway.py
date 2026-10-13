"""OpenAI audio/speech route adapter for the official Fish Speech API server."""
import os
import signal
import subprocess
import sys
from contextlib import asynccontextmanager

import requests
import uvicorn
from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import Response

UPSTREAM = "http://127.0.0.1:8081"
CHECKPOINT = os.environ.get("FISH_CHECKPOINT", "/app/checkpoints/s2-pro")
child = None


@asynccontextmanager
async def lifespan(_app):
    global child
    child = subprocess.Popen([
        sys.executable, "tools/api_server.py",
        "--listen", "127.0.0.1:8081",
        "--llama-checkpoint-path", CHECKPOINT,
        "--decoder-checkpoint-path", os.path.join(CHECKPOINT, "codec.pth"),
        "--decoder-config-name", "modded_dac_vq",
    ])
    try:
        yield
    finally:
        if child and child.poll() is None:
            child.send_signal(signal.SIGTERM)
            try:
                child.wait(timeout=30)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


app = FastAPI(title="Fish Speech OpenAI Audio Adapter", lifespan=lifespan)


@app.get("/v1/health")
def health():
    if child is None or child.poll() is not None:
        raise HTTPException(status_code=503, detail="Fish Speech process is not running")
    try:
        response = requests.get(f"{UPSTREAM}/v1/health", timeout=2)
    except requests.RequestException as exc:
        raise HTTPException(status_code=503, detail="Fish Speech is loading") from exc
    return Response(response.content, status_code=response.status_code, media_type="application/json")


@app.post("/v1/audio/speech")
def speech(
    input: str = Form(...),
    response_format: str = Form("wav"),
    voice: str = Form("default"),
):
    if child is None or child.poll() is not None:
        raise HTTPException(status_code=503, detail="Fish Speech process is not running")
    try:
        response = requests.post(
            f"{UPSTREAM}/v1/tts",
            json={"text": input, "format": response_format, "streaming": False},
            timeout=(10, 600),
        )
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Fish Speech request failed: {exc}") from exc
    if not response.ok:
        raise HTTPException(status_code=response.status_code, detail=response.text[:1000])
    media_type = response.headers.get("content-type", "audio/wav")
    return Response(response.content, media_type=media_type)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
