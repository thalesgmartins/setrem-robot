#!/usr/bin/env bash
#
# Instala TODOS os serviços do Pi num único virtualenv compartilhado.
#
# Um venv só para todos os serviços faz sentido aqui: eles compartilham a lib
# robo-common e rodam na mesma máquina. A ordem importa: o robo-common (lib
# compartilhada) é instalado em modo editável PRIMEIRO; assim, quando
# instalamos cada serviço, o pip já encontra a dependência satisfeita e não
# tenta baixá-la do PyPI.
#
# USO (no Raspberry Pi, a partir da raiz do repo):
#   ./pi/scripts/install.sh
#
# Rode novamente sempre que mudar dependências ou adicionar um serviço.

set -euo pipefail

# Raiz de "pi/" (uma pasta acima deste script).
PI_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMMON_DIR="$PI_ROOT/services/_common"
VENV="$PI_ROOT/.venv"

# Serviços a instalar (pastas em pi/services/). Acrescente novos serviços aqui.
SERVICOS=(serial_ingestor orquestrador gps wifi)

echo ">> Criando virtualenv compartilhado em $VENV"
python3 -m venv "$VENV"

echo ">> Atualizando pip"
"$VENV/bin/pip" install --upgrade pip >/dev/null

echo ">> Instalando robo-common (editável)"
"$VENV/bin/pip" install -e "$COMMON_DIR"

for servico in "${SERVICOS[@]}"; do
  echo ">> Instalando $servico (editável)"
  "$VENV/bin/pip" install -e "$PI_ROOT/services/$servico"
done

echo ""
echo "Pronto. Entrypoints disponíveis em $VENV/bin/ :"
for servico in "${SERVICOS[@]}"; do
  # O entrypoint usa hífen no lugar do underscore (ver pyproject de cada um).
  echo "   ${servico//_/-}"
done
echo ""
echo "Lembre-se: para acessar a serial (ESP32 e GPS) o usuário precisa estar"
echo "no grupo 'dialout':"
echo "   sudo usermod -aG dialout \$USER   (e reabrir a sessão)"
