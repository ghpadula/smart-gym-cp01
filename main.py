"""
Smart Gym - Sistema de Monitoramento Inteligente
CP01 - Physical Computing (IoT & IoB) - FIAP

Descrição:
    Lê o UID do aluno via porta serial (Arduino + MFRC522),
    autentica o acesso e, após login, ativa a câmera com
    MediaPipe Pose para extração de landmarks em tempo real.

Dependências:
    pip install pyserial opencv-python mediapipe numpy
"""

import cv2
import mediapipe as mp
import serial
import serial.tools.list_ports
import threading
import time
import numpy as np
import sys

# ─── Configurações ───────────────────────────────────────────────
SERIAL_BAUD   = 9600
SERIAL_TIMEOUT = 2          # segundos
CAMERA_INDEX  = 0           # índice da webcam

# Banco de alunos cadastrados  {UID -> dados}
ALUNOS = {
    "A1:B2:C3:D4": {"nome": "João Silva",  "plano": "Musculação Avançado"},
    "11:22:33:44": {"nome": "Maria Souza", "plano": "Hiit + Funcional"},
    "DE:AD:BE:EF": {"nome": "Carlos Lima", "plano": "Iniciante Completo"},
}

# Cores (BGR)
COR_VERDE   = (0, 255, 0)
COR_VERMELHO= (0, 0, 255)
COR_AMARELO = (0, 255, 255)
COR_BRANCO  = (255, 255, 255)
COR_PRETO   = (0, 0, 0)
COR_ROSA    = (180, 0, 200)

# ─── Estado global ───────────────────────────────────────────────
estado = {
    "logado"    : False,
    "aluno"     : None,
    "uid"       : None,
    "mensagem"  : "Aguardando cartão RFID...",
    "cor_msg"   : COR_AMARELO,
    "serial_ok" : False,
}

# ─── Funções de detecção de pose ─────────────────────────────────

def calcular_angulo(a, b, c):
    """Calcula o ângulo (graus) entre três pontos (articulações)."""
    a = np.array(a)
    b = np.array(b)
    c = np.array(c)

    ba = a - b
    bc = c - b

    cos_ang = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-6)
    angulo  = np.degrees(np.arccos(np.clip(cos_ang, -1.0, 1.0)))
    return angulo


def obter_coords(landmarks, idx, w, h):
    """Retorna coordenadas pixel de um landmark."""
    lm = landmarks[idx]
    return int(lm.x * w), int(lm.y * h)


def analisar_postura(landmarks, w, h):
    """
    Analisa a postura do usuário com base nos landmarks do MediaPipe.
    Retorna lista de feedbacks.
    """
    mp_pose = mp.solutions.pose.PoseLandmark
    feedbacks = []

    try:
        # --- Cotovelo direito (ombro-cotovelo-pulso) ---
        ombro_d  = obter_coords(landmarks, mp_pose.RIGHT_SHOULDER.value, w, h)
        cotovelo_d = obter_coords(landmarks, mp_pose.RIGHT_ELBOW.value, w, h)
        pulso_d  = obter_coords(landmarks, mp_pose.RIGHT_WRIST.value, w, h)
        ang_cotovelo_d = calcular_angulo(ombro_d, cotovelo_d, pulso_d)

        # --- Joelho direito (quadril-joelho-tornozelo) ---
        quadril_d  = obter_coords(landmarks, mp_pose.RIGHT_HIP.value, w, h)
        joelho_d   = obter_coords(landmarks, mp_pose.RIGHT_KNEE.value, w, h)
        tornozelo_d= obter_coords(landmarks, mp_pose.RIGHT_ANKLE.value, w, h)
        ang_joelho_d = calcular_angulo(quadril_d, joelho_d, tornozelo_d)

        # --- Feedback cotovelo ---
        if ang_cotovelo_d < 30:
            feedbacks.append(("Cotovelo: Flexão completa!", COR_VERDE))
        elif ang_cotovelo_d > 160:
            feedbacks.append(("Cotovelo: Extensão completa!", COR_VERDE))
        else:
            feedbacks.append((f"Cotovelo: {int(ang_cotovelo_d)}°", COR_BRANCO))

        # --- Feedback joelho ---
        if ang_joelho_d < 100:
            feedbacks.append(("Joelho: Agachamento profundo!", COR_VERDE))
        elif ang_joelho_d > 170:
            feedbacks.append(("Joelho: Em pé / estendido", COR_BRANCO))
        else:
            feedbacks.append((f"Joelho: {int(ang_joelho_d)}°", COR_AMARELO))

        # --- Alinhamento do quadril ---
        quadril_e = obter_coords(landmarks, mp_pose.LEFT_HIP.value, w, h)
        desnivel  = abs(quadril_d[1] - quadril_e[1])
        if desnivel > 30:
            feedbacks.append(("⚠ Quadril desnivelado!", COR_VERMELHO))
        else:
            feedbacks.append(("Quadril alinhado ✓", COR_VERDE))

    except Exception:
        feedbacks.append(("Posição não detectada", COR_AMARELO))

    return feedbacks


def desenhar_hud(frame, aluno, feedbacks):
    """Desenha o HUD (cabeçalho + feedbacks) sobre o frame."""
    h, w = frame.shape[:2]

    # Fundo semi-transparente no topo
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 90), COR_PRETO, -1)
    cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

    # Nome do aluno e plano
    cv2.putText(frame, f"Smart Gym | {aluno['nome']}",
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, COR_ROSA, 2)
    cv2.putText(frame, f"Plano: {aluno['plano']}",
                (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, COR_BRANCO, 1)
    cv2.putText(frame, time.strftime("%H:%M:%S"),
                (w - 120, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, COR_AMARELO, 2)

    # Feedbacks de postura
    y_offset = 120
    for texto, cor in feedbacks:
        cv2.putText(frame, texto, (10, y_offset),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, cor, 2)
        y_offset += 35

    # Rodapé
    cv2.putText(frame, "Pressione 'Q' para sair | 'R' para novo login",
                (10, h - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, COR_BRANCO, 1)


# ─── Leitura Serial ──────────────────────────────────────────────

def detectar_porta_serial():
    """Tenta encontrar automaticamente a porta do Arduino."""
    portas = serial.tools.list_ports.comports()
    for p in portas:
        if "Arduino" in p.description or "CH340" in p.description \
                or "USB Serial" in p.description or "ttyUSB" in p.device \
                or "ttyACM" in p.device or "COM" in p.device:
            return p.device
    # Fallback: retorna a primeira disponível
    if portas:
        return portas[0].device
    return None


def thread_serial(porta):
    """Thread que escuta a porta serial e atualiza o estado global."""
    global estado
    try:
        ser = serial.Serial(porta, SERIAL_BAUD, timeout=SERIAL_TIMEOUT)
        estado["serial_ok"] = True
        print(f"[Serial] Conectado em {porta}")

        while True:
            if ser.in_waiting > 0:
                linha = ser.readline().decode("utf-8", errors="ignore").strip()
                print(f"[Serial] {linha}")

                if linha.startswith("ACESSO_LIBERADO:"):
                    uid = linha.split(":")[1].strip() if ":" in linha else ""
                    aluno = ALUNOS.get(uid)
                    if aluno:
                        estado["logado"]  = True
                        estado["aluno"]   = aluno
                        estado["uid"]     = uid
                        estado["mensagem"]= f"Bem-vindo, {aluno['nome']}!"
                        estado["cor_msg"] = COR_VERDE
                        print(f"[Login] {aluno['nome']} autenticado (UID: {uid})")
                    else:
                        estado["mensagem"] = f"UID não cadastrado: {uid}"
                        estado["cor_msg"]  = COR_VERMELHO

                elif linha.startswith("ACESSO_NEGADO:"):
                    uid = linha.split(":")[1].strip() if ":" in linha else ""
                    estado["mensagem"] = f"Acesso negado! UID: {uid}"
                    estado["cor_msg"]  = COR_VERMELHO
                    estado["logado"]   = False
                    estado["aluno"]    = None

            time.sleep(0.05)

    except serial.SerialException as e:
        print(f"[Serial] Erro: {e}")
        estado["serial_ok"] = False
        estado["mensagem"]  = "Arduino não encontrado (modo demo)"
        estado["cor_msg"]   = COR_AMARELO


# ─── Loop Principal de Visão ─────────────────────────────────────

def iniciar_visao():
    """Abre a câmera e processa pose com MediaPipe."""
    global estado

    mp_pose    = mp.solutions.pose
    mp_drawing = mp.solutions.drawing_utils
    mp_styles  = mp.solutions.drawing_styles

    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        print("[Câmera] Erro: não foi possível abrir a câmera.")
        sys.exit(1)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    with mp_pose.Pose(
        min_detection_confidence=0.6,
        min_tracking_confidence=0.6,
        model_complexity=1
    ) as pose:

        print("[Câmera] Iniciada. Aguardando login via RFID...")

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            frame = cv2.flip(frame, 1)
            h, w  = frame.shape[:2]

            # ── Tela de login (aguardando RFID) ──
            if not estado["logado"]:
                overlay = frame.copy()
                cv2.rectangle(overlay, (0, 0), (w, h), COR_PRETO, -1)
                cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

                cv2.putText(frame, "SMART GYM",
                            (w//2 - 150, h//2 - 80),
                            cv2.FONT_HERSHEY_SIMPLEX, 2, COR_ROSA, 3)
                cv2.putText(frame, estado["mensagem"],
                            (w//2 - 250, h//2),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                            estado["cor_msg"], 2)

                if not estado["serial_ok"]:
                    cv2.putText(frame,
                                "Pressione 'D' para modo demo (sem Arduino)",
                                (w//2 - 250, h//2 + 60),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, COR_AMARELO, 1)

                cv2.imshow("Smart Gym - Physical Computing", frame)
                tecla = cv2.waitKey(1) & 0xFF
                if tecla == ord('q'):
                    break
                # Modo demo sem Arduino
                if tecla == ord('d') and not estado["serial_ok"]:
                    estado["logado"]  = True
                    estado["aluno"]   = {"nome": "Demo User", "plano": "Treino Demo"}
                    estado["mensagem"]= "Modo Demo ativo"
                    estado["cor_msg"] = COR_VERDE
                continue

            # ── Processamento de pose (usuário logado) ──
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            rgb.flags.writeable = False
            results = pose.process(rgb)
            rgb.flags.writeable = True

            feedbacks = []

            if results.pose_landmarks:
                # Desenha esqueleto
                mp_drawing.draw_landmarks(
                    frame,
                    results.pose_landmarks,
                    mp_pose.POSE_CONNECTIONS,
                    landmark_drawing_spec=mp_styles.get_default_pose_landmarks_style()
                )
                # Analisa postura
                feedbacks = analisar_postura(
                    results.pose_landmarks.landmark, w, h
                )
            else:
                feedbacks = [("Posicione-se em frente à câmera", COR_AMARELO)]

            # Desenha HUD
            desenhar_hud(frame, estado["aluno"], feedbacks)

            cv2.imshow("Smart Gym - Physical Computing", frame)

            tecla = cv2.waitKey(1) & 0xFF
            if tecla == ord('q'):
                break
            if tecla == ord('r'):
                # Reset para novo login
                estado["logado"]  = False
                estado["aluno"]   = None
                estado["mensagem"]= "Aguardando cartão RFID..."
                estado["cor_msg"] = COR_AMARELO
                print("[Login] Sessão encerrada.")

    cap.release()
    cv2.destroyAllWindows()
    print("[Sistema] Encerrado.")


# ─── Entry Point ─────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print(" Smart Gym - Physical Computing | FIAP CP01")
    print("=" * 50)

    # Detecta porta serial
    porta = detectar_porta_serial()

    if porta:
        print(f"[Serial] Arduino detectado em: {porta}")
        t = threading.Thread(target=thread_serial, args=(porta,), daemon=True)
        t.start()
        time.sleep(1)
    else:
        print("[Serial] Arduino não detectado. Use 'D' para modo demo.")

    # Inicia loop de visão (bloqueia até fechar)
    iniciar_visao()
