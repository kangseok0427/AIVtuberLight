# tts/tts.py
import asyncio
import os
import re
import tempfile
import pyaudio
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

def clean_text(text: str) -> str:
    text = re.sub(r'[^\uAC00-\uD7A3\u3131-\u318Ea-zA-Z0-9\s,.!?~]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def find_device(name: str) -> int | None:
    p = pyaudio.PyAudio()
    for i in range(p.get_device_count()):
        d = p.get_device_info_by_index(i)
        if name in d['name'] and d['maxOutputChannels'] > 0:
            p.terminate()
            return i
    p.terminate()
    return None

def play_audio(path: str):
    device_index = find_device("CABLE Input")
    if device_index is None:
        print("[TTS] VB-Cable 디바이스 없음!")
        # 기본 출력으로 fallback
        data, samplerate = sf.read(path, dtype='float32')
        if data.ndim == 1:
            data = np.stack([data, data], axis=1)
        silence = np.zeros((int(samplerate * 0.8), 2), dtype=np.float32)
        data = np.concatenate([data, silence], axis=0)
        sd.play(data, samplerate)
        sd.wait()
        return

    data, samplerate = sf.read(path, dtype='float32')
    if data.ndim == 1:
        data = np.stack([data, data], axis=1)
    silence = np.zeros((int(samplerate * 0.8), 2), dtype=np.float32)
    data = np.concatenate([data, silence], axis=0)
    sd.play(data, samplerate, device=device_index)
    sd.wait()

async def text_to_speech(text: str):
    clean = clean_text(text)
    if not clean:
        return

    communicate = edge_tts.Communicate(clean, VOICE, pitch=PITCH, rate=RATE)
    await communicate.save(TTS_OUTPUT)
    play_audio(TTS_OUTPUT)