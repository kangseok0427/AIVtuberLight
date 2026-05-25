# tts/tts.py
import os
import re
import tempfile
import edge_tts
import soundfile as sf
import numpy as np
import sounddevice as sd
from dotenv import load_dotenv

load_dotenv()

VOICE      = os.getenv("TTS_VOICE", "ko-KR-SunHiNeural")
PITCH      = os.getenv("TTS_PITCH", "+20Hz")
RATE       = os.getenv("TTS_RATE", "+5%")
TTS_OUTPUT = os.path.join(tempfile.gettempdir(), "tts_output.mp3")
DEVICE_INDEX = 1  # VB-Cable 고정 1 or 3 (환경에 따라 다름, 확인 필요)

def clean_text(text: str) -> str:
    text = re.sub(r'[^\uAC00-\uD7A3\u3131-\u318Ea-zA-Z0-9\s,.!?~]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def play_audio(path: str):
    data, samplerate = sf.read(path, dtype='float32')
    if data.ndim == 1:
        data = np.stack([data, data], axis=1)
    silence = np.zeros((int(samplerate * 0.8), 2), dtype=np.float32)
    data = np.concatenate([data, silence], axis=0)
    sd.play(data, samplerate, device=DEVICE_INDEX)
    sd.wait()

async def text_to_speech(text: str):
    clean = clean_text(text)
    if not clean:
        return
    communicate = edge_tts.Communicate(clean, VOICE, pitch=PITCH, rate=RATE)
    await communicate.save(TTS_OUTPUT)
    play_audio(TTS_OUTPUT)