from __future__ import annotations

import abc
import json
import shutil
import subprocess
import threading
from dataclasses import dataclass, field
from typing import Any, Callable


class RuntimeTransportUnavailable(RuntimeError):
    """Raised when the requested runtime transport can not be started."""


PayloadHandler = Callable[[str, dict[str, Any]], None]


class RuntimeTransportBase(abc.ABC):
    @abc.abstractmethod
    def publish(self, topic: str, payload: dict[str, Any] | str) -> None:
        ...

    @abc.abstractmethod
    def subscribe(self, topic: str, handler: PayloadHandler) -> str:
        ...

    @abc.abstractmethod
    def unsubscribe(self, topic: str, token: str) -> None:
        ...


@dataclass
class MosquittoDockerTransport(RuntimeTransportBase):
    """
    Runtime transport that calls mosquitto_pub/sub via docker.
    This keeps dependencies small in an offline environment while still using
    a real Mosquitto broker.
    """

    broker_host: str = "localhost"
    broker_port: int = 1883
    docker_image: str = "eclipse-mosquitto:2"
    docker_cmd: str = "docker"
    next_token: int = 1
    subscriptions: dict[tuple[str, str], subprocess.Popen[str] | None] = field(
        default_factory=dict
    )
    threads: dict[tuple[str, str], threading.Thread] = field(default_factory=dict)
    _token_lock: threading.Lock = field(default_factory=threading.Lock)

    def __post_init__(self) -> None:
        if shutil.which(self.docker_cmd) is None:
            raise RuntimeTransportUnavailable("docker command not found for MQTT transport.")

    def publish(self, topic: str, payload: dict[str, Any] | str) -> None:
        if isinstance(payload, dict):
            body = json.dumps(payload, separators=(",", ":"))
        else:
            body = str(payload)
        self._validate_topic(topic)
        cmd = [
            self.docker_cmd,
            "run",
            "--rm",
            "--network",
            "host",
            self.docker_image,
            "mosquitto_pub",
            "-h",
            self.broker_host,
            "-p",
            str(self.broker_port),
            "-t",
            topic,
            "-m",
            body,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            stderr = (result.stderr or result.stdout or "").strip()
            raise RuntimeTransportUnavailable(
                f"publish failed for topic {topic}: {stderr or 'unknown error'}"
            )

    def subscribe(self, topic: str, handler: PayloadHandler) -> str:
        self._validate_topic(topic)
        with self._token_lock:
            token = f"sub-{self.next_token}"
            self.next_token += 1

        cmd = [
            self.docker_cmd,
            "run",
            "--rm",
            "--network",
            "host",
            self.docker_image,
            "mosquitto_sub",
            "-h",
            self.broker_host,
            "-p",
            str(self.broker_port),
            "-t",
            topic,
            "--quiet",
        ]
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        key = (topic, token)
        self.subscriptions[key] = process

        def _reader() -> None:
            if process.stdout is None:
                return
            for raw_line in iter(process.stdout.readline, ""):
                line = raw_line.strip()
                if not line:
                    continue
                if " " in line:
                    _topic, value = line.split(" ", 1)
                else:
                    _topic, value = topic, line
                handler(_topic, self._coerce_payload(value))
            process.stdout.close()

        thread = threading.Thread(target=_reader, daemon=True)
        thread.start()
        self.threads[key] = thread
        return token

    def unsubscribe(self, topic: str, token: str) -> None:
        key = (topic, token)
        process = self.subscriptions.pop(key, None)
        if process is None:
            return
        process.terminate()
        try:
            process.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=1.0)
        self.threads.pop(key, None)

    def close(self) -> None:
        for topic, token in list(self.subscriptions.keys()):
            self.unsubscribe(topic, token)

    def _validate_topic(self, topic: str) -> None:
        if not topic:
            raise RuntimeTransportUnavailable("topic cannot be empty")

    @staticmethod
    def _coerce_payload(raw: str) -> dict[str, Any]:
        try:
            return json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return {"_raw": raw}
