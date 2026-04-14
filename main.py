"""
Smart Gym - Sistema de Monitoramento Inteligente
CP01 - Physical Computing (IoT & IoB) - FIAP
 
Dependências:
    pip install pyserial opencv-python mediapipe numpy requests
"""
 
import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision
from mediapipe.tasks.python.components import containers as mp_containers
import serial
import serial.tools.list_ports
import threading
import time
import numpy as np
import sys
import urllib.request
import os
 
# ─── Configurações ───────────────────────────────────────────────
SERIAL_BAUD    = 9600
SERIAL_TIMEOUT = 2
CAMERA_INDEX   = 0
 
MODEL_URL  = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task%22
MODEL_PATH = "pose_landmarker_lite.task"
 
# Banco de alunos cadastrados  {UID -> dados}
ALUNOS = {
    "A1:B2:C3:D4": {"nome": "João Silva",  "plano": "Musculação Avançado"},
    "11:22:33:44": {"nome": "Maria Souza", "plano": "Hiit + Funcional"},
    "DE:AD:BE:EF": {"nome": "Carlos Lima", "plano": "Iniciante Completo"},
}
 
# Cores (BGR)
COR_VERDE    = (0, 255, 0)
COR_VERMELHO = (0, 0, 255)
COR_AMARELO  = (0, 255, 255)
COR_BRANCO   = (255, 255, 255)
COR_PRETO    = (0, 0, 0)
COR_ROSA     = (180, 0, 200)
 
# Índices dos landmarks (PoseLandmarker usa índices numéricos)
LM = {
    "RIGHT_SHOULDER": 12, "LEFT_SHOULDER": 11,
    "RIGHT_ELBOW": 14,    "LEFT_ELBOW": 13,
    "RIGHT_WRIST": 16,    "LEFT_WRIST": 15,
    "RIGHT_HIP": 24,      "LEFT_HIP": 23,
    "RIGHT_KNEE": 26,     "LEFT_KNEE": 25,
    "RIGHT_ANKLE": 28,    "LEFT_ANKLE": 27,
}
 
# ─── Estado global ───────────────────────────────────────────────
estado = {
    "logado"    : False,
    "aluno"     : None,
    "uid"       : None,
    "mensagem"  : "Aguardando cartão RFID...",
    "cor_msg"   : COR_AMARELO,
    "serial_ok" : False,
}
 
# ─── Download do modelo ──────────────────────────────────────────
 
def baixar_modelo():
    if os.path.exists(MODEL_PATH):
        print(f"[Modelo] Arquivo já existe: {MODEL_PATH}")
        return True
    print("[Modelo] Baixando pose_landmarker_lite.task ...")
    try:
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        print("[Modelo] Download concluído.")
        return True
    except Exception as e:
        print(f"[Modelo] Erro ao baixar: {e}")
        return False
 
# ─── Funções de detecção de pose ─────────────────────────────────
 
def calcular_angulo(a, b, c):
    a, b, c = np.array(a), np.array(b), np.array(c)
    ba = a - b
    bc = c - b
    cos_ang = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-6)
    return np.degrees(np.arccos(np.clip(cos_ang, -1.0, 1.0)))
 
 
def obter_coords(landmarks, idx, w, h):
    lm = landmarks[idx]
    return int(lm.x * w), int(lm.y * h)
 
 
def analisar_postura(landmarks, w, h):
    feedbacks = []
    try:
        ombro_d    = obter_coords(landmarks, LM["RIGHT_SHOULDER"], w, h)
        cotovelo_d = obter_coords(landmarks, LM["RIGHT_ELBOW"],    w, h)
        pulso_d    = obter_coords(landmarks, LM["RIGHT_WRIST"],    w, h)
        ang_cotovelo_d = calcular_angulo(ombro_d, cotovelo_d, pulso_d)
 
        quadril_d  = obter_coords(landmarks, LM["RIGHT_HIP"],    w, h)
        joelho_d   = obter_coords(landmarks, LM["RIGHT_KNEE"],   w, h)
        tornozelo_d= obter_coords(landmarks, LM["RIGHT_ANKLE"],  w, h)
        ang_joelho_d = calcular_angulo(quadril_d, joelho_d, tornozelo_d)
 
        if ang_cotovelo_d < 30:
            feedbacks.append(("Cotovelo: Flexão completa!", COR_VERDE))
        elif ang_cotovelo_d > 160:
            feedbacks.append(("Cotovelo: Extensão completa!", COR_VERDE))
        else:
            feedbacks.append((f"Cotovelo: {int(ang_cotovelo_d)}°", COR_BRANCO))
 
        if ang_joelho_d < 100:
            feedbacks.append(("Joelho: Agachamento profundo!", COR_VERDE))
        elif ang_joelho_d > 170:
            feedbacks.append(("Joelho: Em pé / estendido", COR_BRANCO))
        else:
            feedbacks.append((f"Joelho: {int(ang_joelho_d)}°", COR_AMARELO))
 
        quadril_e = obter_coords(landmarks, LM["LEFT_HIP"], w, h)
        desnivel  = abs(quadril_d[1] - quadril_e[1])
        if desnivel > 30:
            feedbacks.append(("! Quadril desnivelado!", COR_VERMELHO))
        else:
            feedbacks.append(("Quadril alinhado OK", COR_VERDE))
 
    except Exception:
        feedbacks.append(("Posição não detectada", COR_AMARELO))
 
    return feedbacks
 
 
def desenhar_esqueleto(frame, landmarks, w, h):
    """Desenha o esqueleto manualmente com as conexões principais."""
    conexoes = [
        ("RIGHT_SHOULDER", "LEFT_SHOULDER"),
        ("RIGHT_SHOULDER", "RIGHT_ELBOW"),
        ("RIGHT_ELBOW",    "RIGHT_WRIST"),
        ("LEFT_SHOULDER",  "LEFT_ELBOW"),
        ("LEFT_ELBOW",     "LEFT_WRIST"),
        ("RIGHT_SHOULDER", "RIGHT_HIP"),
        ("LEFT_SHOULDER",  "LEFT_HIP"),
        ("RIGHT_HIP",      "LEFT_HIP"),
        ("RIGHT_HIP",      "RIGHT_KNEE"),
        ("RIGHT_KNEE",     "RIGHT_ANKLE"),
        ("LEFT_HIP",       "LEFT_KNEE"),
        ("LEFT_KNEE",      "LEFT_ANKLE"),
    ]
    for a, b in conexoes:
        try:
            pt1 = obter_coords(landmarks, LM[a], w, h)
            pt2 = obter_coords(landmarks, LM[b], w, h)
            cv2.line(frame, pt1, pt2, COR_VERDE, 2)
        except Exception:
            pass
 
    for nome, idx in LM.items():
        try:
            pt = obter_coords(landmarks, idx, w, h)
            cv2.circle(frame, pt, 4, COR_ROSA, -1)
        except Exception:
            pass
 
 
def desenhar_hud(frame, aluno, feedbacks):
    h, w = frame.shape[:2]
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 90), COR_PRETO, -1)
    cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)
 
    cv2.putText(frame, f"Smart Gym | {aluno['nome']}",
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, COR_ROSA, 2)
    cv2.putText(frame, f"Plano: {aluno['plano']}",
                (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, COR_BRANCO, 1)
    cv2.putText(frame, time.strftime("%H:%M:%S"),
                (w - 120, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, COR_AMARELO, 2)
 
    y_offset = 120
    for texto, cor in feedbacks:
        cv2.putText(frame, texto, (10, y_offset),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, cor, 2)
        y_offset += 35
 
    cv2.putText(frame, "Pressione 'Q' para sair | 'R' para novo login",
                (10, h - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, COR_BRANCO, 1)
 
 
# ─── Leitura Serial ──────────────────────────────────────────────
 
def detectar_porta_serial():
    return "COM5"
 
 
def thread_serial(porta):
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
                    uid   = linha.replace("ACESSO_LIBERADO:", "").strip()
                    print(f"[Debug] UID recebido: '{uid}'")
                    aluno = ALUNOS.get(uid)
                    if not aluno:
                        # Aceita qualquer cartão não cadastrado como usuário genérico
                        aluno = {"nome": f"Aluno {uid}", "plano": "Plano Padrão"}
                    estado.update(logado=True, aluno=aluno, uid=uid,
                                  mensagem=f"Bem-vindo, {aluno['nome']}!",
                                  cor_msg=COR_VERDE)
                    print(f"[Login] {aluno['nome']} autenticado (UID: {uid})")
 
                elif linha.startswith("ACESSO_NEGADO:"):
                    uid = linha.split(":", 1)[1].strip()
                    estado.update(mensagem=f"Acesso negado! UID: {uid}",
                                  cor_msg=COR_VERMELHO, logado=False, aluno=None)
 
            time.sleep(0.05)
 
    except serial.SerialException as e:
        print(f"[Serial] Erro: {e}")
        estado["serial_ok"]  = False
        estado["mensagem"]   = "Arduino não encontrado (modo demo)"
        estado["cor_msg"]    = COR_AMARELO
 
 
# ─── Loop Principal de Visão ─────────────────────────────────────
 
def iniciar_visao():
    global estado
 
    # Cria o detector com a nova API Tasks
    base_options    = mp_python.BaseOptions(model_asset_path=MODEL_PATH)
    options         = mp_vision.PoseLandmarkerOptions(
        base_options=base_options,
        running_mode=mp_vision.RunningMode.VIDEO,
        num_poses=1,
        min_pose_detection_confidence=0.6,
        min_pose_presence_confidence=0.6,
        min_tracking_confidence=0.6,
    )
    landmarker = mp_vision.PoseLandmarker.create_from_options(options)
 
    # Tenta índices 0, 1, 2 até encontrar uma câmera funcional
    cap = None
    for idx in range(3):
        print(f"[Câmera] Tentando índice {idx}...")
        c = cv2.VideoCapture(idx, cv2.CAP_DSHOW)  # CAP_DSHOW resolve maioria dos problemas no Windows
        if c.isOpened():
            # Tenta ler um frame para confirmar que funciona
            ok, _ = c.read()
            if ok:
                cap = c
                print(f"[Câmera] Câmera encontrada no índice {idx}.")
                break
            c.release()
 
    if cap is None:
        print("[Câmera] Erro: nenhuma câmera funcional encontrada nos índices 0, 1 e 2.")
        sys.exit(1)
 
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
 
    # Descarta os primeiros frames (câmera ainda aquecendo)
    for _ in range(5):
        cap.read()
 
    print("[Câmera] Iniciada. Aguardando login via RFID...")
    frame_ts = 0  # timestamp em ms para o modo VIDEO
 
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
 
        frame = cv2.flip(frame, 1)
        h, w  = frame.shape[:2]
 
        # ── Tela de login ──
        if not estado["logado"]:
            overlay = frame.copy()
            cv2.rectangle(overlay, (0, 0), (w, h), COR_PRETO, -1)
            cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)
 
            cv2.putText(frame, "SMART GYM",
                        (w//2 - 150, h//2 - 80),
                        cv2.FONT_HERSHEY_SIMPLEX, 2, COR_ROSA, 3)
            cv2.putText(frame, estado["mensagem"],
                        (w//2 - 250, h//2),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, estado["cor_msg"], 2)
 
            if not estado["serial_ok"]:
                cv2.putText(frame,
                            "Pressione 'D' para modo demo (sem Arduino)",
                            (w//2 - 250, h//2 + 60),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, COR_AMARELO, 1)
 
            cv2.imshow("Smart Gym - Physical Computing", frame)
            tecla = cv2.waitKey(1) & 0xFF
            if tecla == ord('q'):
                break
            if tecla == ord('d') and not estado["serial_ok"]:
                estado.update(logado=True,
                              aluno={"nome": "Demo User", "plano": "Treino Demo"},
                              mensagem="Modo Demo ativo", cor_msg=COR_VERDE)
            continue
 
        # ── Processamento de pose ──
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image  = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
 
        frame_ts += 33   # ~30 fps em ms
        result = landmarker.detect_for_video(mp_image, frame_ts)
 
        feedbacks = []
        if result.pose_landmarks:
            landmarks = result.pose_landmarks[0]   # primeira pessoa detectada
            desenhar_esqueleto(frame, landmarks, w, h)
            feedbacks = analisar_postura(landmarks, w, h)
        else:
            feedbacks = [("Posicione-se em frente à câmera", COR_AMARELO)]
 
        desenhar_hud(frame, estado["aluno"], feedbacks)
 
        cv2.imshow("Smart Gym - Physical Computing", frame)
 
        tecla = cv2.waitKey(1) & 0xFF
        if tecla == ord('q'):
            break
        if tecla == ord('r'):
            estado.update(logado=False, aluno=None,
                          mensagem="Aguardando cartão RFID...",
                          cor_msg=COR_AMARELO)
            print("[Login] Sessão encerrada.")
 
    cap.release()
    cv2.destroyAllWindows()
    landmarker.close()
    print("[Sistema] Encerrado.")
 
 
# ─── Entry Point ─────────────────────────────────────────────────
 
if __name__ == "__main__":
    print("=" * 50)
    print(" Smart Gym - Physical Computing | FIAP CP01")
    print("=" * 50)
 
    if not baixar_modelo():
        print("[ERRO] Modelo não disponível. Verifique a conexão e tente novamente.")
        sys.exit(1)
 
    porta = detectar_porta_serial()
    if porta:
        print(f"[Serial] Arduino detectado em: {porta}")
        t = threading.Thread(target=thread_serial, args=(porta,), daemon=True)
        t.start()
        time.sleep(1)
    else:
        print("[Serial] Arduino não detectado. Use 'D' para modo demo.")
 
    iniciar_visao()
