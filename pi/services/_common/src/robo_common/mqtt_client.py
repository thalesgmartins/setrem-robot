"""Cliente MQTT padronizado para os serviços do robô.

Encapsula o paho-mqtt (API 2.x) com o que todo serviço precisa:
  - conexão ao broker local com reconexão automática (backoff);
  - Last Will (LWT): se o processo morrer sem avisar, o broker publica "offline";
  - publicação de JSON em uma linha;
  - inscrição em tópicos com handlers, com re-inscrição automática após reconectar;
  - parse seguro do payload (JSON inválido é descartado, não derruba o serviço).

Uso típico:

    from robo_common.mqtt_client import MqttService
    from robo_common import topics

    svc = MqttService(client_id="meu_servico",
                      heartbeat_topic=topics.heartbeat("meu_servico"))
    svc.on(topics.COMANDO_ENTRADA, lambda topico, msg: print(msg))
    svc.start()
    ...
    svc.stop()
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)

# Um handler recebe (topico_de_origem, payload_ja_desserializado).
MessageHandler = Callable[[str, dict[str, Any]], None]


class MqttService:
    def __init__(
        self,
        client_id: str,
        host: str = "127.0.0.1",
        port: int = 1883,
        username: str | None = None,
        password: str | None = None,
        heartbeat_topic: str | None = None,
    ) -> None:
        self._client_id = client_id
        self._host = host
        self._port = port
        self._heartbeat_topic = heartbeat_topic
        self._handlers: dict[str, MessageHandler] = {}

        self._client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id,
            clean_session=True,
        )
        if username:
            self._client.username_pw_set(username, password)

        # Reconexão automática: o loop do paho tenta reconectar sozinho,
        # com espera crescente entre 1s e 30s.
        self._client.reconnect_delay_set(min_delay=1, max_delay=30)

        # Last Will: registrado no broker no momento da conexão. Se este
        # processo cair sem chamar stop(), o broker publica "offline" por ele.
        if heartbeat_topic:
            self._client.will_set(
                heartbeat_topic,
                payload=json.dumps({"servico": client_id, "status": "offline"}),
                qos=1,
                retain=True,
            )

        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.on_disconnect = self._on_disconnect

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------
    def on(self, topic: str, handler: MessageHandler) -> None:
        """Registra um handler para um tópico (aceita filtros com + e #).

        Deve ser chamado ANTES de start(); a inscrição efetiva acontece no
        on_connect, e é refeita a cada reconexão.
        """
        self._handlers[topic] = handler

    def start(self) -> None:
        logger.info("Conectando ao broker MQTT em %s:%s ...", self._host, self._port)
        self._client.connect(self._host, self._port, keepalive=30)
        # loop_start() roda a rede do MQTT numa thread separada, então o
        # serviço fica livre para fazer seu trabalho (ler serial, GPS, etc.).
        self._client.loop_start()

    def stop(self) -> None:
        if self._heartbeat_topic:
            # Aviso "limpo" de saída (substitui o LWT em desligamento normal).
            self.publish_json(
                self._heartbeat_topic,
                {"servico": self._client_id, "status": "offline"},
                qos=1,
                retain=True,
            )
        self._client.loop_stop()
        self._client.disconnect()
        logger.info("Desconectado do broker MQTT.")

    def publish_json(
        self,
        topic: str,
        payload: dict[str, Any],
        qos: int = 0,
        retain: bool = False,
    ) -> None:
        self._client.publish(topic, json.dumps(payload), qos=qos, retain=retain)

    # ------------------------------------------------------------------
    # Callbacks internos (paho 2.x)
    # ------------------------------------------------------------------
    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code != 0:
            logger.error("Falha ao conectar no broker (rc=%s).", reason_code)
            return
        logger.info("Conectado ao broker MQTT.")

        # Re-inscreve em tudo. Isto é ESSENCIAL após uma reconexão: as
        # inscrições anteriores foram perdidas quando a conexão caiu.
        for topic in self._handlers:
            client.subscribe(topic, qos=1)
            logger.debug("Inscrito em %s", topic)

        if self._heartbeat_topic:
            self.publish_json(
                self._heartbeat_topic,
                {"servico": self._client_id, "status": "online"},
                qos=1,
                retain=True,
            )

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        logger.warning(
            "Desconectado do broker (rc=%s). Reconexão automática em andamento...",
            reason_code,
        )

    def _on_message(self, client, userdata, message):
        try:
            payload = json.loads(message.payload.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            logger.warning("Mensagem ignorada (JSON inválido) em %s.", message.topic)
            return

        handler = self._match_handler(message.topic)
        if handler is None:
            return
        try:
            handler(message.topic, payload)
        except Exception:  # um handler com bug não pode derrubar o serviço
            logger.exception("Erro no handler do tópico %s.", message.topic)

    def _match_handler(self, topic: str) -> MessageHandler | None:
        # Match exato primeiro (caso mais comum e mais barato).
        if topic in self._handlers:
            return self._handlers[topic]
        # Depois, match por filtro (tópicos com + ou #).
        for filtro, handler in self._handlers.items():
            if mqtt.topic_matches_sub(filtro, topic):
                return handler
        return None
