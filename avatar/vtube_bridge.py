# avatar/vtube_bridge.py
import asyncio
import websockets
import json
import os
from dotenv import load_dotenv

load_dotenv()

VTUBE_WS_URL = "ws://localhost:8001"
PLUGIN_NAME  = "GaonAI"
PLUGIN_DEV   = "Gaon"

class VTubeBridge:
    def __init__(self):
        self.ws         = None
        self.auth_token = os.getenv("VTUBE_TOKEN")  # ✅ env에서 불러오기

    async def connect(self):
        self.ws = await websockets.connect(VTUBE_WS_URL, ping_interval=None)
        await self._authenticate()
        print("[VTube] 연결 완료!")

    async def _send(self, payload: dict) -> dict:
        await self.ws.send(json.dumps(payload))
        resp = await self.ws.recv()
        return json.loads(resp)

    async def _authenticate(self):
        # 토큰 없으면 새로 발급 후 출력
        if not self.auth_token:
            print("[VTube] 토큰 없음, 새로 발급 중... VTube Studio 팝업 허용해주세요!")
            resp = await self._send({
                "apiName": "VTubeStudioPublicAPI",
                "apiVersion": "1.0",
                "requestID": "auth_req",
                "messageType": "AuthenticationTokenRequest",
                "data": {
                    "pluginName": PLUGIN_NAME,
                    "pluginDeveloper": PLUGIN_DEV,
                    "pluginIcon": None
                }
            })
            self.auth_token = resp["data"]["authenticationToken"]
            print(f"\n✅ 토큰 발급 완료! .env에 아래 줄 추가하세요:")
            print(f"VTUBE_TOKEN={self.auth_token}\n")

        # 토큰으로 인증
        resp2 = await self._send({
            "apiName": "VTubeStudioPublicAPI",
            "apiVersion": "1.0",
            "requestID": "auth",
            "messageType": "AuthenticationRequest",
            "data": {
                "pluginName": PLUGIN_NAME,
                "pluginDeveloper": PLUGIN_DEV,
                "authenticationToken": self.auth_token
            }
        })

        authenticated = resp2["data"].get("authenticated", False)
        print(f"[VTube] 인증 결과: {authenticated}")

        if not authenticated:
            print("[VTube] 토큰 만료! .env에서 VTUBE_TOKEN 삭제 후 재실행하세요.")
            raise Exception("VTube Studio 인증 실패")
        
        # avatar/vtube_bridge.py - 파일 맨 아래에 추가 (class 안에 들여쓰기 맞춰서)

    async def get_expressions(self) -> list:
        resp = await self._send({
            "apiName": "VTubeStudioPublicAPI",
            "apiVersion": "1.0",
            "requestID": "expr_list",
            "messageType": "ExpressionStateRequest",
            "data": {"details": True}
        })
        return resp["data"]["expressions"]

# avatar/vtube_bridge.py - set_expression, reset_expression 교체

    async def set_expression(self, expression_name: str) -> None:
        print(f"[VTube] 표정 시도: {expression_name}.exp3.json")
        # recv() 없이 send만 (VTube Studio 응답 안기다림)
        await self.ws.send(json.dumps({
            "apiName": "VTubeStudioPublicAPI",
            "apiVersion": "1.0",
            "requestID": "expr_on",
            "messageType": "ExpressionActivationRequest",
            "data": {
                "expressionFile": f"{expression_name}.exp3.json",
                "active": True
            }
        }))
        # 응답 버리기
        await self.ws.recv()

    async def reset_expression(self, expression_name: str) -> None:
        await self.ws.send(json.dumps({
            "apiName": "VTubeStudioPublicAPI",
            "apiVersion": "1.0",
            "requestID": "expr_off",
            "messageType": "ExpressionActivationRequest",
            "data": {
                "expressionFile": f"{expression_name}.exp3.json",
                "active": False
            }
        }))
        await self.ws.recv()

    async def trigger_and_reset(self, expression_name: str | None, duration: float = 3.0) -> None:
        if not expression_name:
            return
        try:
            await self.set_expression(expression_name)
            await asyncio.sleep(duration)
            await self.reset_expression(expression_name)
        except websockets.exceptions.ConnectionClosedError:
            print("[VTube] 연결 끊김, 재연결 시도...")
            await self.connect()
            await self.set_expression(expression_name)
            await asyncio.sleep(duration)
            await self.reset_expression(expression_name)
            
    async def shake(self, duration: float = 3.0, intensity: float = 1.0):
        print(f"[VTube] 흔들기 시작! {duration}초")
        end_time = asyncio.get_event_loop().time() + duration
        toggle = 1

        while asyncio.get_event_loop().time() < end_time:
            await self.ws.send(json.dumps({
                "apiName": "VTubeStudioPublicAPI",
                "apiVersion": "1.0",
                "requestID": "shake",
                "messageType": "InjectParameterDataRequest",
                "data": {
                    "faceFound": False,
                    "mode": "set",
                    "parameterValues": [
                        {"id": "FaceAngleX", "value": intensity * 30 * toggle}
                    ]
                }
            }))
            await self.ws.recv()
            toggle *= -1
            await asyncio.sleep(0.08)

        await self.ws.send(json.dumps({
            "apiName": "VTubeStudioPublicAPI",
            "apiVersion": "1.0",
            "requestID": "shake_reset",
            "messageType": "InjectParameterDataRequest",
            "data": {
                "faceFound": False,
                "mode": "set",
                "parameterValues": [
                    {"id": "FaceAngleX", "value": 0}
                ]
            }
        }))
        await self.ws.recv()
        print("[VTube] 흔들기 종료")

    async def disconnect(self) -> None:
        if self.ws:
            await self.ws.close()