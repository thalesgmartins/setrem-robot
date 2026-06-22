#!/usr/bin/env bash
#
# Gera/atualiza o arquivo de senhas (passwd) do broker REMOTO.
#
# USO:
#   ./scripts/gen-passwd.sh <USUARIO> <SENHA>
#
# Exemplo:
#   ./scripts/gen-passwd.sh robo_pie 'umaSenhaForteAqui'
#
# O MESMO usuário/senha deve ir no bridge.conf do lado local
# (remote_username / remote_password).

set -euo pipefail

USUARIO="${1:?Informe o usuario. Ex: ./scripts/gen-passwd.sh robo_pie5 senha}"
SENHA="${2:?Informe a senha.}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CFG_DIR="$ROOT/cloud/mosquitto/config"
mkdir -p "$CFG_DIR"

# -c cria/zera o arquivo; -b recebe a senha por argumento (batch).
docker run --rm \
  -v "$CFG_DIR:/cfg" \
  eclipse-mosquitto:2 \
  mosquitto_passwd -c -b /cfg/passwd "$USUARIO" "$SENHA"

chmod 644 "$CFG_DIR/passwd"

echo ""
echo "Arquivo de senha gerado em: $CFG_DIR/passwd"
echo "Use o MESMO par usuario/senha no bridge.conf local:"
echo "   remote_username $USUARIO"
echo "   remote_password <a senha que você definiu>"