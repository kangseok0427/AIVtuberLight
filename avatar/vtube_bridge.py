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
        self.auth_token = os.getenv("VTUBE_TOKEN")

    async def connect(self):
        self.ws = await websockets.connect(VTUBE_WS_URL, ping_interval=None)
        await self._authenticate()
        print("[VTube] 연결 완료!")

    async def _send(self, payload: dict) -> dict:
        await self.ws.send(json.dumps(payload))
        resp = await self.ws.recv()
        return json.loads(resp)

    async def _reconnect(self):
        """연결 끊겼을 때 재연결 시도"""
        print("[VTube] 재연결 시도...")
        try:
            await self.connect()
            print("[VTube] 재연결 성공!")
        except Exception as e:
            print(f"[VTube] 재연결 실패: {e}")
            raise

    async def _authenticate(self):
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

    async def get_expressions(self) -> list:
        resp = await self._send({
            "apiName": "VTubeStudioPublicAPI",
            "apiVersion": "1.0",
            "requestID": "expr_list",
            "messageType": "ExpressionStateRequest",
            "data": {"details": True}
        })
        return resp["data"]["expressions"]

    async def set_expression(self, expression_name: str) -> None:
        print(f"[VTube] 표정 켜기: {expression_name}.exp3.json")
        await self._send({
            "apiName": "VTubeStudioPublicAPI",
            "apiVersion": "1.0",
            "requestID": "expr_on",
            "messageType": "ExpressionActivationRequest",
            "data": {
                "expressionFile": f"{expression_name}.exp3.json",
                "active": True
            }
        })

    async def reset_expression(self, expression_name: str) -> None:
        print(f"[VTube] 표정 끄기: {expression_name}.exp3.json")
        await self._send({
            "apiName": "VTubeStudioPublicAPI",
            "apiVersion": "1.0",
            "requestID": "expr_off",
            "messageType": "ExpressionActivationRequest",
            "data": {
                "expressionFile": f"{expression_name}.exp3.json",
                "active": False
            }
        })

    async def trigger_and_reset(self, expression_name: str | None, duration: float = 3.0) -> None:
        if not expression_name:
            return
        try:
            await self.set_expression(expression_name)
            await asyncio.sleep(duration)
            await self.reset_expression(expression_name)
        except websockets.exceptions.ConnectionClosedError:
            print("[VTube] 연결 끊김 — 재연결 후 재시도...")
            try:
                await self._reconnect()
                await self.set_expression(expression_name)
                await asyncio.sleep(duration)
                await self.reset_expression(expression_name)
            except Exception as e:
                print(f"[VTube] trigger_and_reset 재시도 실패: {e}")

    async def shake(self, duration: float = 2.0, intensity: float = 1.0):
        print(f"[VTube] 흔들기 시작! {duration}초 / intensity: {intensity}")
        end_time = asyncio.get_event_loop().time() + duration
        toggle = 1

        try:
            while asyncio.get_event_loop().time() < end_time:
                await self._send({
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
                })
                toggle *= -1
                await asyncio.sleep(0.08)

            # 흔들기 후 원위치
            await self._send({
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
            })
            print("[VTube] 흔들기 종료")

        except websockets.exceptions.ConnectionClosedError:
            print("[VTube] 흔들기 중 연결 끊김 — 재연결 시도...")
            try:
                await self._reconnect()
            except Exception as e:
                print(f"[VTube] 흔들기 재연결 실패: {e}")

    async def disconnect(self) -> None:
        if self.ws:
            await self.ws.close()
            print("[VTube] 연결 종료")