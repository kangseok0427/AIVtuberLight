# voice/listener.py
import os
import io
import asyncio
import pyaudio
import wave
import tempfile
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

CHUNK     = 1024
FORMAT    = pyaudio.paInt16
CHANNELS  = 1
RATE      = 16000
SILENCE_THRESHOLD = 500    # 무음 감지 임계값
SILENCE_DURATION  = 1.5    # 이 초 동안 무음이면 발화 종료로 판단
MAX_DURATION      = 30     # 최대 녹음 시간 (초)

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def _is_silent(data: bytes) -> bool:
    import struct
    samples = struct.unpack(f'{len(data)//2}h', data)
    volume  = sum(abs(s) for s in samples) / len(samples)
    return volume < SILENCE_THRESHOLD

def _record() -> bytes | None:
    """말하는 동안 녹음, 무음 감지되면 종료"""
    pa      = pyaudio.PyAudio()
    stream  = pa.open(format=FORMAT, channels=CHANNELS, rate=RATE,
                      input=True, frames_per_buffer=CHUNK)
    frames  = []
    silent_chunks  = 0
    speaking       = False
    max_chunks     = int(RATE / CHUNK * MAX_DURATION)
    silence_chunks = int(RATE / CHUNK * SILENCE_DURATION)

    print("[음성] 대기 중... (말하면 시작)")

    for _ in range(max_chunks):
        data = stream.read(CHUNK, exception_on_overflow=False)
        frames.append(data)

        if _is_silent(data):
            silent_chunks += 1
            if speaking and silent_chunks >= silence_chunks:
                break
        else:
            silent_chunks = 0
            speaking      = True

    stream.stop_stream()
    stream.close()
    pa.terminate()

    if not speaking:
        return None

    # WAV 바이트로 변환
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(pa.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))
    return buf.getvalue()

def _transcribe(audio_bytes: bytes) -> str:
    """Groq Whisper로 STT"""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(audio_bytes)
        tmp_path = f.name

    try:
        with open(tmp_path, "rb") as f:
            result = client.audio.transcriptions.create(
                model="whisper-large-v3-turbo",
                file=("audio.wav", f),
                language="ko",
                response_format="text"
            )
        return result.strip()
    finally:
        os.unlink(tmp_path)

async def voice_loop(callback, name: str = "개발자"):
    """메인 음성 루프 — main.py에서 asyncio.create_task로 실행"""
    print("[음성] 음성 모드 시작!")
    loop = asyncio.get_event_loop()

    while True:
        try:
            audio = await loop.run_in_executor(None, _record)
            if not audio:
                continue

            text = await loop.run_in_executor(None, _transcribe, audio)
            if not text:
                continue

            print(f"[음성] {name}: {text}")
            await callback(name, text)

        except Exception as e:
            print(f"[음성] 오류: {e}")
            await asyncio.sleep(1)