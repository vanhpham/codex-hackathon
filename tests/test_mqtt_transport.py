from __future__ import annotations

import io
import subprocess
import unittest
from unittest.mock import patch

from swarmforge.mqtt_transport import MosquittoDockerTransport, RuntimeTransportUnavailable


class _FakeCompletedProcess:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class _FakePopenProcess:
    def __init__(self) -> None:
        self.stdout = io.StringIO("")
        self.terminated = False
        self.wait_called = 0

    def wait(self, timeout: float | None = None) -> int:
        self.wait_called += 1
        return 0

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.terminated = True


def _fake_which(_: str) -> str:
    return "/usr/bin/docker"


class MqttTransportTest(unittest.TestCase):
    def test_coerce_payload(self) -> None:
        transport = MosquittoDockerTransport()
        self.assertEqual(transport._coerce_payload('{"a":1}'), {"a": 1})
        self.assertEqual(transport._coerce_payload("hello"), {"_raw": "hello"})

    def test_publish_raises_on_unavailable_binary(self) -> None:
        with patch("shutil.which", lambda _: None):
            with self.assertRaises(RuntimeTransportUnavailable):
                MosquittoDockerTransport()

    def test_publish_calls_docker_cli(self) -> None:
        calls: list[list[str]] = []

        def fake_run(cmd: list[str], capture_output: bool = True, text: bool = True) -> _FakeCompletedProcess:
            calls.append(cmd)
            return _FakeCompletedProcess()

        with patch("shutil.which", side_effect=_fake_which), patch("subprocess.run", side_effect=fake_run):
            transport = MosquittoDockerTransport(docker_cmd="docker")
            transport.publish("swarm/node/01/ota", {"k": 1})
            self.assertTrue(calls)
            self.assertIn("mosquitto_pub", calls[0])

    def test_subscribe_and_unsubscribe(self) -> None:
        with patch("shutil.which", side_effect=_fake_which), patch("subprocess.Popen") as popen_mock:
            fake_process = _FakePopenProcess()
            popen_mock.return_value = fake_process
            transport = MosquittoDockerTransport(docker_cmd="docker")
            token = transport.subscribe("swarm/telemetry/01", lambda *_args: None)
            self.assertTrue(token.startswith("sub-"))
            transport.unsubscribe("swarm/telemetry/01", token)
            self.assertTrue(fake_process.terminated)


if __name__ == "__main__":
    unittest.main()
