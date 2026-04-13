#  Smart Gym — Checkpoint 01
**Physical Computing (IoT & IoB) | Engenharia de Software — FIAP**

---

## Equipe

| Nome | RM |

555506 - Arthur Abonizio 

554907 - Gabriel Padula

556417 - Rodrigo Nakata

> **Turma:** 3ESPZ · **Entrega:** 13/04/2026 · **Prof.:** Lucas D. Augusto

---

## Sobre o Projeto

O sistema **Smart Gym** transforma estações de treino comuns em **Smart Stations** capazes de replicar a atenção de um personal trainer presencial. Neste Checkpoint 01, implementamos as duas primeiras camadas:

1. **Identificação por RFID** — leitura de cartão via Arduino/ESP32 + módulo MFRC522 (protocolo SPI), com envio do UID pela porta serial.
2. **Captura Biométrica por Visão** — após autenticação, ativação da câmera com **MediaPipe Pose** para extração em tempo real das coordenadas (*landmarks*) das articulações e análise de postura.

---

## Hardware (Componentes)

| Componente | Quantidade | Descrição |
|------------|-----------|-----------|
| Arduino Uno (ou ESP32) | 1 | Microcontrolador principal |
| Módulo RFID MFRC522 | 1 | Leitura de cartões/tags RFID 13,56 MHz |
| Cartão/Tag RFID (ISO14443A) | 2+ | Identificação dos alunos |
| LED (embutido pino 13) | 1 | Feedback visual de acesso |
| Jumpers | 8 | Conexão SPI |
| Protoboard | 1 | Montagem do circuito |

---

## Bibliotecas Utilizadas

### Arduino / ESP32
| Biblioteca | Versão | Finalidade |
|-----------|--------|-----------|
| `SPI.h` | (built-in) | Comunicação SPI com MFRC522 |
| `MFRC522.h` | ≥ 1.4.10 | Leitura de cartões RFID |

### Python
| Biblioteca | Versão | Finalidade |
|-----------|--------|-----------|
| `pyserial` | ≥ 3.5 | Comunicação com Arduino via serial |
| `opencv-python` | ≥ 4.8 | Captura e exibição da câmera |
| `mediapipe` | ≥ 0.10 | Detecção de pose (landmarks) |
| `numpy` | ≥ 1.24 | Cálculo de ângulos das articulações |

---

## Diagrama de Conexões

```
Arduino Uno        MFRC522
-----------        -------
3.3V       ──────  3.3V
GND        ──────  GND
D10 (SS)   ──────  SDA
D13 (SCK)  ──────  SCK
D11 (MOSI) ──────  MOSI
D12 (MISO) ──────  MISO
D9 (RST)   ──────  RST
```
> **Simulação online:** [Wokwi — Smart Gym RFID](https://wokwi.com) *(adicione o link do seu projeto Wokwi aqui)*

---

## Estrutura do Repositório

```
smart-gym-cp01/
├── arduino/
│   └── rfid_reader/
│       └── rfid_reader.ino      # Sketch Arduino (RFID + Serial)
├── python/
│   ├── main.py                  # Script principal (Serial + MediaPipe)
│   └── requirements.txt         # Dependências Python
└── README.md
```

---

## Setup e Execução

### 1. Clone o repositório
```bash
git clone https://github.com/ghpadula/smart-gym-cp01.git
cd smart-gym-cp01
```

### 2. Upload do sketch no Arduino

1. Abra o Arduino IDE (≥ 2.x)
2. Instale a biblioteca **MFRC522** via *Library Manager*
3. Abra `arduino/rfid_reader/rfid_reader.ino`
4. Selecione a placa **Arduino Uno** (ou ESP32) e a porta COM correta
5. Clique em **Upload**
6. Abra o Serial Monitor (9600 baud) e teste aproximando um cartão

> Para cadastrar novos cartões: aproxime o cartão, copie o UID exibido no Serial Monitor e adicione ao array `CARTOES_AUTORIZADOS` no `.ino`.

### 3. Instale as dependências Python
```bash
cd python
pip install -r requirements.txt
```

### 4. Execute o sistema
```bash
python main.py
```

O script detecta automaticamente a porta serial do Arduino. Caso não encontre, pressione **`D`** na janela da câmera para ativar o **modo demo** (sem hardware).

### Controles durante execução
| Tecla | Ação |
|-------|------|
| `Q` | Encerrar o sistema |
| `R` | Logout / aguardar novo cartão |
| `D` | Modo demo (sem Arduino) |

---

## Arquitetura do Código

```
┌─────────────────────────────────────────────┐
│              Arduino / ESP32                │
│  MFRC522 ──(SPI)──> Sketch ──(Serial)──>   │
│  "ACESSO_LIBERADO:UID" ou "ACESSO_NEGADO"   │
└─────────────────────┬───────────────────────┘
                      │ USB / UART
┌─────────────────────▼───────────────────────┐
│              Python — main.py               │
│                                             │
│  Thread Serial          Thread Principal    │
│  ┌──────────────┐       ┌───────────────┐  │
│  │ pyserial     │──────>│ OpenCV        │  │
│  │ parse UID    │ estado│ MediaPipe     │  │
│  │ lookup aluno │       │ Análise Pose  │  │
│  └──────────────┘       │ HUD overlay   │  │
│                         └───────────────┘  │
└─────────────────────────────────────────────┘
```

**Fluxo de execução:**
1. Arduino lê continuamente o módulo MFRC522 via SPI
2. Ao detectar um cartão, verifica se o UID está autorizado
3. Envia `ACESSO_LIBERADO:<UID>` ou `ACESSO_NEGADO:<UID>` pela serial
4. Thread Python recebe a mensagem e atualiza o estado global
5. Loop principal da câmera exibe tela de login ou ativa a análise de pose
6. MediaPipe extrai 33 landmarks do corpo; o sistema calcula ângulos das articulações (cotovelo, joelho, quadril) e exibe feedback visual em tempo real

---

## Análise de Postura (MediaPipe)

O sistema monitora três métricas principais:

| Métrica | Landmarks utilizados | Feedback |
|---------|---------------------|----------|
| Ângulo do cotovelo | Ombro → Cotovelo → Pulso | Flexão / Extensão completa |
| Ângulo do joelho | Quadril → Joelho → Tornozelo | Agachamento / Em pé |
| Nivelamento do quadril | Quadril D vs Quadril E | Alinhamento postural |

---

## Vídeo Demonstrativo

> **[Assista ao pitch técnico aqui](#)** *(adicione o link do YouTube/Drive)*

**Conteúdo do vídeo (≤ 3 min):**
- Demonstração do login via RFID integrado à visão computacional
- Explicação da arquitetura do código
- Principais desafios técnicos e como foram superados

---

## Desafios Técnicos

- **Detecção da porta serial:** implementamos busca automática por descrição do dispositivo, com fallback para modo demo
- **Sincronização de threads:** uso de dicionário compartilhado (`estado`) com acesso simples, evitando race conditions nas atualizações de estado
- **Ruído de leitura RFID:** adicionamos delay de 1,5s e chamada a `PICC_HaltA()` após cada leitura para evitar leituras duplicadas

---

##  Licença

Projeto acadêmico — FIAP 2026. Uso educacional.
