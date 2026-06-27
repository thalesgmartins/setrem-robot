"""Roteamento puro de comandos do app -> tópicos de domínio.

Este módulo NÃO conhece MQTT: ele só transforma um comando (dict já
desserializado) numa lista de publicações (tópico, payload). Isso o torna
trivial de testar e mantém a lógica de decisão separada da infraestrutura.

Contrato de entrada (o que o app envia, via Bluetooth -> ESP32 -> serial_ingestor):

    {"tipo": "motor",  "acao": "frente", "velocidade": 80}
    {"tipo": "voz",    "texto": "olá, tudo bem?"}
    {"tipo": "parada_emergencia"}

Veja docs/contrato-mqtt.md para a especificação completa.
"""

from __future__ import annotations

import logging
from typing import Any

from robo_common import topics

logger = logging.getLogger(__name__)

# Uma publicação resultante do roteamento: para onde e o quê.
Publicacao = tuple[str, dict[str, Any]]

# Ações de motor que aceitamos do app. Mantém o robô previsível: qualquer
# outra ação é rejeitada antes de chegar ao grupo de Movimento.
ACOES_MOTOR_VALIDAS = {"frente", "tras", "esquerda", "direita", "parar"}

# Velocidade padrão quando o app manda uma direção sem informar intensidade.
VELOCIDADE_PADRAO = 60


def _limitar_velocidade(valor: Any) -> int:
    """Converte e satura a velocidade em [0, 100].

    O app é não-confiável: pode mandar string, número fora da faixa ou nada.
    """
    try:
        v = int(valor)
    except (TypeError, ValueError):
        return VELOCIDADE_PADRAO
    return max(0, min(100, v))


def _rotear_motor(cmd: dict[str, Any]) -> list[Publicacao]:
    acao = cmd.get("acao")
    if acao not in ACOES_MOTOR_VALIDAS:
        logger.warning("Comando de motor com ação inválida: %r", acao)
        return []

    velocidade = 0 if acao == "parar" else _limitar_velocidade(cmd.get("velocidade"))
    return [(topics.MOTORES_COMANDO, {"acao": acao, "velocidade": velocidade})]


def _rotear_voz(cmd: dict[str, Any]) -> list[Publicacao]:
    texto = cmd.get("texto")
    if not isinstance(texto, str) or not texto.strip():
        logger.warning("Comando de voz sem texto válido: %r", cmd)
        return []
    return [(topics.VOZ_FALAR, {"texto": texto.strip()})]


def _rotear_parada_emergencia(_cmd: dict[str, Any]) -> list[Publicacao]:
    # Segurança em primeiro lugar: zera os motores imediatamente.
    return [(topics.MOTORES_COMANDO, {"acao": "parar", "velocidade": 0})]


def _rotear_wifi(cmd: dict[str, Any]) -> list[Publicacao]:
    # Repassa o comando de Wi-Fi ao serviço wifi, que valida e aplica via
    # nmcli. A credencial chegou pelo mesmo caminho dos comandos (app -> ESP32
    # -> serial), pois o Pi não fala Bluetooth.
    payload: dict[str, Any] = {"acao": cmd.get("acao", "conectar")}
    for campo in ("ssid", "senha", "password"):
        if campo in cmd:
            payload[campo] = cmd[campo]
    return [(topics.WIFI_COMANDO, payload)]


# Tabela de despacho: "tipo" do comando -> função que o traduz em publicações.
# Adicionar um novo tipo de comando é só registrar mais uma entrada aqui.
_ROTAS = {
    "motor": _rotear_motor,
    "voz": _rotear_voz,
    "parada_emergencia": _rotear_parada_emergencia,
    "wifi": _rotear_wifi,
}


def rotear(comando: dict[str, Any]) -> list[Publicacao]:
    """Traduz um comando do app numa lista de publicações (tópico, payload).

    Retorna lista vazia para comandos desconhecidos ou malformados — nunca
    levanta exceção, porque a entrada vem de um cliente externo não-confiável.
    """
    if not isinstance(comando, dict):
        logger.warning("Comando ignorado (não é objeto JSON): %r", comando)
        return []

    tipo = comando.get("tipo")
    rota = _ROTAS.get(tipo)
    if rota is None:
        logger.warning("Comando de tipo desconhecido: %r", tipo)
        return []

    return rota(comando)
