from __future__ import annotations

import abc
import json
import uuid
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
class PahoMqttTransport(RuntimeTransportBase):
    """MQTT transport for services running inside Docker Compose."""

    broker_host: str = "localhost"
    broker_port: int = 1883
    client_id: str | None = None
    connect_timeout_seconds: float = 5.0
    next_token: int = 1
    handlers: dict[str, dict[str, PayloadHandler]] = field(default_factory=dict)
    _token_lock: threading.Lock = field(default_factory=threading.Lock)
    _connected: threading.Event = field(default_factory=threading.Event)
    _connect_error: str | None = None
    _client: Any = None

    def __post_init__(self) -> None:
        try:
            from paho.mqtt import client as mqtt
        except ImportError as exc:
            raise RuntimeTransportUnavailable(
                "paho-mqtt is required for MQTT transport inside Docker Compose."
            ) from exc

        self._mqtt = mqtt
        client_id = self.client_id or f"swarmforge-{uuid.uuid4().hex[:10]}"
        self._client = self._make_client(mqtt, client_id)
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message

        try:
            self._client.connect(self.broker_host, self.broker_port, keepalive=30)
        except Exception as exc:
            raise RuntimeTransportUnavailable(f"MQTT connect failed: {exc}") from exc

        self._client.loop_start()
        if not self._connected.wait(self.connect_timeout_seconds):
            self.close()
            raise RuntimeTransportUnavailable(
                f"MQTT connect timed out for {self.broker_host}:{self.broker_port}"
            )
        if self._connect_error:
            self.close()
            raise RuntimeTransportUnavailable(self._connect_error)

    def publish(self, topic: str, payload: dict[str, Any] | str) -> None:
        self._validate_topic(topic)
        body = json.dumps(payload, separators=(",", ":")) if isinstance(payload, dict) else str(payload)
        info = self._client.publish(topic, body)
        info.wait_for_publish(timeout=5.0)
        if info.rc != 0:
            raise RuntimeTransportUnavailable(f"publish failed for topic {topic}: rc={info.rc}")

    def subscribe(self, topic: str, handler: PayloadHandler) -> str:
        self._validate_topic(topic)
        with self._token_lock:
            token = f"sub-{self.next_token}"
            self.next_token += 1
            first_handler = topic not in self.handlers
            self.handlers.setdefault(topic, {})[token] = handler

        if first_handler:
            result, _mid = self._client.subscribe(topic)
            if result != 0:
                with self._token_lock:
                    self.handlers.get(topic, {}).pop(token, None)
                raise RuntimeTransportUnavailable(f"subscribe failed for topic {topic}: rc={result}")
        return token

    def unsubscribe(self, topic: str, token: str) -> None:
        with self._token_lock:
            topic_handlers = self.handlers.get(topic, {})
            topic_handlers.pop(token, None)
            should_unsubscribe = not topic_handlers
            if should_unsubscribe:
                self.handlers.pop(topic, None)

        if should_unsubscribe:
            self._client.unsubscribe(topic)

    def close(self) -> None:
        if self._client is None:
            return
        try:
            self._client.loop_stop()
            self._client.disconnect()
        except Exception:
            pass

    @staticmethod
    def _make_client(mqtt: Any, client_id: str) -> Any:
        try:
            return mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
        except (AttributeError, TypeError):
            return mqtt.Client(client_id=client_id)

    def _on_connect(self, *_args: Any) -> None:
        reason_code = _args[-2] if len(_args) >= 5 else _args[-1]
        try:
            failed = int(reason_code) != 0
        except (TypeError, ValueError):
            failed = bool(getattr(reason_code, "is_failure", False))

        if failed:
            self._connect_error = f"MQTT connect failed: rc={reason_code}"
        self._connected.set()

    def _on_message(self, _client: Any, _userdata: Any, message: Any) -> None:
        topic = str(message.topic)
        raw_payload = message.payload.decode("utf-8", errors="replace")
        payload = self._coerce_payload(raw_payload)
        for handler in list(self.handlers.get(topic, {}).values()):
            handler(topic, payload)

    def _validate_topic(self, topic: str) -> None:
        if not topic:
            raise RuntimeTransportUnavailable("topic cannot be empty")

    @staticmethod
    def _coerce_payload(raw: str) -> dict[str, Any]:
        try:
            return json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return {"_raw": raw}


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
