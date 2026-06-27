"""gps — receptor GPS (NMEA via serial) -> MQTT local.

Lê continuamente as sentenças NMEA que um receptor GPS comum despeja na
serial, extrai a posição (latitude/longitude/fix/satélites/velocidade) e
publica em robo/gps/posicao (retained). NÃO escreve em robo/telemetria/*:
quem decide o que persiste é o orquestrador, que espelha gps/posicao para a
nuvem. Assim a regra "o que vai pro histórico" fica num lugar só.

A maioria dos módulos (NEO-6M e similares) fala 9600 baud por padrão e usa
/dev/serial0 (UART do Pi) ou um conversor USB em /dev/ttyUSB*/ttyACM*.

Configuração por variáveis de ambiente (com defaults sensatos):
    GPS_PORT              (default /dev/serial0)
    GPS_BAUD              (default 9600)
    GPS_INTERVALO_S       (default 1; intervalo mínimo entre publicações)
    MQTT_HOST             (default 127.0.0.1)
    MQTT_PORT             (default 1883)
    HEARTBEAT_INTERVALO_S (default 10)
    LOG_LEVEL             (default INFO)
"""

from __future__ import annotations

import logging
import os
import signal
import time

import pynmea2
import serial  # pyserial

from robo_common import topics
from robo_common.mqtt_client import MqttService

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("gps")

# --- Configuração ---
SERVICO = "gps"
GPS_PORT = os.environ.get("GPS_PORT", "/dev/serial0")
GPS_BAUD = int(os.environ.get("GPS_BAUD", "9600"))
GPS_INTERVALO_S = float(os.environ.get("GPS_INTERVALO_S", "1"))
MQTT_HOST = os.environ.get("MQTT_HOST", "127.0.0.1")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
HEARTBEAT_INTERVALO_S = float(os.environ.get("HEARTBEAT_INTERVALO_S", "10"))

_parar = False


def _tratar_sinal(signum, _frame) -> None:
    global _parar
    logger.info("Sinal %s recebido; encerrando com elegância...", signum)
    _parar = True


def abrir_serial() -> serial.Serial:
    """Abre a serial do GPS, reabrindo até conseguir.

    O timeout de 1s faz o readline() retornar periodicamente, mantendo o loop
    responsivo a heartbeat e à flag de parada mesmo sem sinal do GPS.
    """
    while not _parar:
        try:
            ser = serial.Serial(GPS_PORT, GPS_BAUD, timeout=1.0)
            logger.info("Serial do GPS aberta em %s @ %d baud.", GPS_PORT, GPS_BAUD)
            return ser
        except (serial.SerialException, OSError) as exc:
            logger.warning(
                "Não consegui abrir %s (%s). Nova tentativa em 3s.", GPS_PORT, exc
            )
            time.sleep(3)
    raise SystemExit(0)


class Posicao:
    """Acumula os campos de posição vindos de sentenças NMEA diferentes.

    O GPS manda a informação fatiada: a GGA traz qualidade do fix, número de
    satélites e altitude; a RMC traz velocidade, rumo e o status de validade.
    Mantemos o último estado conhecido e o publicamos como um único objeto.
    """

    def __init__(self) -> None:
        self.lat: float | None = None
        self.lon: float | None = None
        self.fix: bool = False
        self.satelites: int | None = None
        self.altitude_m: float | None = None
        self.velocidade_kmh: float | None = None
        self.rumo: float | None = None

    def atualizar(self, msg: pynmea2.NMEASentence) -> None:
        # GGA: posição + qualidade do fix + satélites + altitude.
        if isinstance(msg, pynmea2.types.talker.GGA):
            # gps_qual == 0 significa "sem fix"; >0 é fix válido.
            self.fix = int(msg.gps_qual or 0) > 0
            if msg.num_sats:
                self.satelites = int(msg.num_sats)
            if self.fix and msg.latitude and msg.longitude:
                self.lat = float(msg.latitude)
                self.lon = float(msg.longitude)
                if msg.altitude is not None:
                    self.altitude_m = float(msg.altitude)

        # RMC: status de validade + velocidade (nós) + rumo.
        elif isinstance(msg, pynmea2.types.talker.RMC):
            self.fix = msg.status == "A"  # 'A' = ativo/válido, 'V' = inválido
            if self.fix and msg.latitude and msg.longitude:
                self.lat = float(msg.latitude)
                self.lon = float(msg.longitude)
            if msg.spd_over_grnd is not None:
                # NMEA dá velocidade em nós; convertemos para km/h.
                self.velocidade_kmh = round(float(msg.spd_over_grnd) * 1.852, 2)
            if msg.true_course is not None:
                self.rumo = float(msg.true_course)

    def tem_posicao(self) -> bool:
        return self.fix and self.lat is not None and self.lon is not None

    def como_payload(self) -> dict:
        return {
            "lat": self.lat,
            "lon": self.lon,
            "fix": self.fix,
            "satelites": self.satelites,
            "altitude_m": self.altitude_m,
            "velocidade_kmh": self.velocidade_kmh,
            "rumo": self.rumo,
            "ts": time.time(),
        }


def main() -> None:
    signal.signal(signal.SIGINT, _tratar_sinal)
    signal.signal(signal.SIGTERM, _tratar_sinal)

    mqtt_svc = MqttService(
        client_id=SERVICO,
        host=MQTT_HOST,
        port=MQTT_PORT,
        heartbeat_topic=topics.heartbeat(SERVICO),
    )
    mqtt_svc.start()

    ser = abrir_serial()
    posicao = Posicao()
    proximo_heartbeat = 0.0
    proxima_publicacao = 0.0

    try:
        while not _parar:
            agora = time.monotonic()
            if agora >= proximo_heartbeat:
                mqtt_svc.publish_json(
                    topics.heartbeat(SERVICO),
                    {"servico": SERVICO, "status": "online", "ts": time.time()},
                    qos=0,
                    retain=True,
                )
                proximo_heartbeat = agora + HEARTBEAT_INTERVALO_S

            try:
                raw = ser.readline()  # b"" no timeout (1s)
            except (serial.SerialException, OSError) as exc:
                logger.warning("Erro de leitura na serial do GPS (%s). Reabrindo...", exc)
                try:
                    ser.close()
                except Exception:
                    pass
                ser = abrir_serial()
                continue

            if not raw:
                continue

            try:
                linha = raw.decode("ascii", errors="ignore").strip()
            except Exception:
                continue
            if not linha.startswith("$"):
                continue  # ruído / linha parcial

            try:
                msg = pynmea2.parse(linha)
            except pynmea2.ParseError:
                # Sentença corrompida (ruído na serial); só ignora.
                continue

            posicao.atualizar(msg)

            # Publica no máximo a cada GPS_INTERVALO_S, e só com fix válido.
            agora = time.monotonic()
            if posicao.tem_posicao() and agora >= proxima_publicacao:
                payload = posicao.como_payload()
                mqtt_svc.publish_json(topics.GPS_POSICAO, payload, qos=1, retain=True)
                logger.info(
                    "Posição: lat=%.6f lon=%.6f sats=%s v=%s km/h",
                    payload["lat"], payload["lon"],
                    payload["satelites"], payload["velocidade_kmh"],
                )
                proxima_publicacao = agora + GPS_INTERVALO_S
    finally:
        try:
            ser.close()
        except Exception:
            pass
        mqtt_svc.stop()


if __name__ == "__main__":
    main()
