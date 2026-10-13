import importlib
import platform
import signal
import subprocess
import unittest
from unittest.mock import Mock, patch

import torch
import torchaudio
from fastapi.testclient import TestClient

import gateway


class RuntimeTests(unittest.TestCase):
    def test_cpu_imports(self):
        self.assertEqual(torch.__version__, torchaudio.__version__)
        self.assertEqual(torch.version.cuda, "13.0")
        if platform.machine() == "aarch64":
            self.assertTrue(any(arch.startswith("sm_121") for arch in
                                torch._C._cuda_getArchFlags().split()))
        self.assertEqual((torch.ones(2) + 1).tolist(), [2, 2])
        for name in (
            "tools.api_server", "tools.server.model_manager", "tools.server.views",
            "fish_speech.models.dac.modded_dac", "fish_speech.models.text2semantic.inference",
        ):
            importlib.import_module(name)

    def test_gateway_without_child(self):
        with patch.object(gateway, "child", None):
            client = TestClient(gateway.app)
            self.assertEqual(client.get("/v1/health").status_code, 503)
            self.assertEqual(client.post("/v1/audio/speech", data={"input": "Hello"}).status_code, 503)

    def test_gateway_api_and_lifecycle(self):
        process = Mock()
        process.poll.return_value = None
        upstream = Mock(ok=True, content=b"RIFF-test", status_code=200,
                        headers={"content-type": "audio/wav"})
        # Mock the child: no model files, CUDA access or network is needed.
        with patch.object(gateway.subprocess, "Popen", return_value=process) as spawn:
            with TestClient(gateway.app) as client:
                self.assertIn("127.0.0.1:8081", spawn.call_args.args[0])
                self.assertIn("/app/checkpoints/s2-pro/codec.pth", spawn.call_args.args[0])
                with patch.object(gateway.requests, "get", return_value=upstream):
                    self.assertEqual(client.get("/v1/health").status_code, 200)
                with patch.object(gateway.requests, "post", return_value=upstream) as post:
                    response = client.post("/v1/audio/speech", files={
                        "input": (None, "Hello"), "response_format": (None, "wav"),
                        "voice": (None, "ignored"),
                    })
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.content, b"RIFF-test")
                    self.assertEqual(post.call_args.kwargs["json"],
                                     {"text": "Hello", "format": "wav", "streaming": False})
                self.assertEqual(client.post("/v1/audio/speech").status_code, 422)
                process.poll.return_value = 1
                self.assertEqual(client.get("/v1/health").status_code, 503)
                process.poll.return_value = None
            process.send_signal.assert_called_once_with(signal.SIGTERM)
            process.wait.assert_called_once_with(timeout=30)

    def test_gateway_errors_and_kill_timeout(self):
        process = Mock()
        process.poll.return_value = None
        process.wait.side_effect = [subprocess.TimeoutExpired("fish", 30), None]
        with patch.object(gateway.subprocess, "Popen", return_value=process):
            with TestClient(gateway.app) as client:
                with patch.object(gateway.requests, "get", side_effect=gateway.requests.ConnectionError):
                    self.assertEqual(client.get("/v1/health").status_code, 503)
                with patch.object(gateway.requests, "post", side_effect=gateway.requests.Timeout):
                    self.assertEqual(client.post("/v1/audio/speech", data={"input": "Hello"}).status_code, 502)
                upstream = Mock(ok=False, status_code=400, text="bad format")
                with patch.object(gateway.requests, "post", return_value=upstream):
                    self.assertEqual(client.post("/v1/audio/speech", data={"input": "Hello"}).status_code, 400)
            process.kill.assert_called_once()
            self.assertEqual(process.wait.call_count, 2)


if __name__ == "__main__":
    unittest.main()
