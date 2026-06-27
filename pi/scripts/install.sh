#!/usr/bin/env bash
#
# Instala o serviço serial_ingestor num virtualenv DEDICADO.
#
# A ordem importa: o robo-common (lib compartilhada) é instalado em modo
# editável PRIMEIRO; assim, quando instalamos o serviço, o pip já encontra
# a dependência satisfeita e não tenta baixá-la do PyPI.
#
# USO (no Raspberry Pi, a partir da raiz do repo):
#   ./pi/scripts/install.sh
#
# Rode novamente sempre que mudar dependências.

set -euo pipefail

# Raiz de "pi/" (duas pastas acima deste script).
PI_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMMON_DIR="$PI_ROOT/services/_common"
SERVICE_DIR="$PI_ROOT/services/serial_ingestor"
VENV="$SERVICE_DIR/.venv"

echo ">> Criando virtualenv em $VENV"
python3 -m venv "$VENV"

echo ">> Atualizando pip"
"$VENV/bin/pip" install --upgrade pip >/dev/null

echo ">> Instalando robo-common (editável)"
"$VENV/bin/pip" install -e "$COMMON_DIR"

echo ">> Instalando serial_ingestor (editável)"
"$VENV/bin/pip" install -e "$SERVICE_DIR"

echo ""
echo "Pronto. Para rodar manualmente:"
echo "   SERIAL_PORT=/dev/ttyUSB0 $VENV/bin/serial-ingestor"
echo ""
echo "Lembre-se: o usuário precisa estar no grupo 'dialout' para acessar a serial:"
echo "   sudo usermod -aG dialout \$USER   (e reabrir a sessão)"
