# Orquestrador Robo Setrem - PIE V

Esse projeto surgiu a partir de uma demanda do **Projeto Interdisciplinar 5**, onde o objetivo foi o desenvolvimento de um robô automatizado, tendo como seu cérebro um Raspberry Pi usando Python.

Este repositório conta com a Conectividade e Orquestração do Robô, responsável pelo **controle via Bluetooth, leitura de GPS, configuração de Wi-Fi dinâmico e envio de telemetria para a nuvem**.

> [!NOTE]
> Este repositório é dividido em três frentes principais (`esp32`, `pi` e `cloud`). Como o robô possui componentes físicos e remotos, cada pasta contém um ambiente de desenvolvimento isolado, com suas próprias tecnologias e responsabilidades.

## Como executar?

Como o projeto abrange três acossistemas diferentes, o passo a passo de instalação e execução está documentado separadamente.

Você pode encontrar as instruções correspondentes para cada um deles aqui:

- [**Raspberry Pi**](./docs/setup-pi.md): Como instalar as dependências, rodar os serviços em Python e gerenciar o broker local.
- [**Cloud**](./docs/setup-cloud.md): Como subir o Mosquitto remoto, o banco TimescaleDB e o ingestor via Docker.
- [**ESP32**](./docs/setup-esp32.md): Como compilar e gravar o firmware da ponte bluetooth no microcontrolador.