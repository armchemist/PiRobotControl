"""환경변수 기반 설정.

하드웨어 구성이 자주 바뀌므로 코드를 고치지 않고 환경변수로 조정한다.
"""

import os


def _int(name, default):
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


# --- 핸디캠 ---
# TODO: 지금은 1대만 연다. 이 파이에는 핸디캠이 2대 붙으므로 다중 카메라 지원이
# 필요하다. 그때는 인덱스 대신 /dev/v4l/by-id/ 경로를 쓸 것 — USB 카메라의
# /dev/videoN 번호는 재부팅마다 뒤바뀐다.
CAMERA_INDEX = _int("CAMERA_INDEX", 0)
CAMERA_WIDTH = _int("CAMERA_WIDTH", 1280)
CAMERA_HEIGHT = _int("CAMERA_HEIGHT", 720)

# --- 인증 ---
# 설정하면 모든 요청에 X-API-Key 헤더가 필요하다.
# 외부(Tailscale/터널)로 노출하기 전에 반드시 설정할 것.
API_KEY = os.environ.get("API_KEY") or None
