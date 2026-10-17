"""로봇 장비 HTTP API (파이1 — 레일 위에서 같이 움직이는 쪽).

클라우드의 에이전트는 USB에 손을 뻗을 수 없으므로, 실험대 쪽 컴퓨터가 하드웨어를
물고 API로 노출한다. 엔드포인트는 에이전트 도구와 1:1로 대응한다.

이 파이가 맡는 것은 레일 위에서 같이 움직이는 핸디캠이다.

    핸디캠 (USB x2)

로봇 팔도 레일 위에 타지만, 제어는 중앙 서버가 맡는다. 이 파이는 팔을 다루지
않는다.

레일 자체와 센서(pH/전도도/열화상)는 고정된 파이2가 맡는다. 그쪽은 별도
저장소(PiSensorServer)다. 레일 구동은 스텝모터 드라이버에 GPIO로 직결돼야 해서,
움직이는 이 파이가 아니라 고정된 파이2에 있다.

실행:
    python -m server.run

uvicorn 을 직접 부르지 않는 이유는 server/run.py 참고 (IPv4/IPv6 동시 바인드).
"""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response
from fastapi.responses import StreamingResponse

from . import config
from .hardware.camera import camera


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    camera.close()


def require_api_key(
    x_api_key: str = Header(default=None),
    api_key: str = Query(default=None),
):
    """API_KEY 환경변수가 설정된 경우에만 검사한다.

    브라우저의 <img src=...> 는 헤더를 붙일 수 없어서 쿼리스트링도 받아준다.
    다만 쿼리스트링은 접근 로그와 브라우저 기록에 남으므로, 외부로 노출한
    환경이라면 헤더 쪽을 쓰는 게 낫다.
    """
    if config.API_KEY and config.API_KEY not in (x_api_key, api_key):
        raise HTTPException(status_code=401, detail="유효하지 않은 API 키")


app = FastAPI(
    title="Lab Robot Control API",
    version="0.1.0",
    lifespan=lifespan,
    dependencies=[Depends(require_api_key)],
)


# --- 상태 ------------------------------------------------------------------


@app.get("/health")
def health():
    """각 하드웨어의 연결 상태. 어떤 것이 빠져 있어도 200을 돌려준다."""
    return {"camera": camera.status()}


# --- 핸디캠 ----------------------------------------------------------------


@app.get(
    "/camera/capture",
    responses={200: {"content": {"image/jpeg": {}}}},
    response_class=Response,
)
def capture():
    """현재 프레임을 JPEG로 반환한다."""
    try:
        jpeg, shape = camera.capture_jpeg()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return Response(
        content=jpeg,
        media_type="image/jpeg",
        headers={"X-Frame-Shape": "x".join(str(n) for n in shape)},
    )


BOUNDARY = "frame"


@app.get("/camera/stream")
def stream(fps: int = Query(default=10, ge=1, le=30)):
    """MJPEG 실시간 스트림. 브라우저 주소창에 그대로 열면 영상이 보인다.

    카메라를 못 열면 첫 프레임에서 예외가 나지만, 스트리밍 응답은 헤더가 이미
    나간 뒤라 상태 코드를 바꿀 수 없다. 그래서 먼저 한 장 찍어보고 실패하면
    503으로 돌려준다.
    """
    try:
        camera.capture_jpeg()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    def frames():
        try:
            for jpeg in camera.stream_jpeg(fps=fps):
                yield (
                    f"--{BOUNDARY}\r\n"
                    f"Content-Type: image/jpeg\r\n"
                    f"Content-Length: {len(jpeg)}\r\n\r\n"
                ).encode() + jpeg + b"\r\n"
        except (GeneratorExit, RuntimeError):
            return  # 클라이언트가 창을 닫았거나 카메라가 빠졌다

    return StreamingResponse(
        frames(),
        media_type=f"multipart/x-mixed-replace; boundary={BOUNDARY}",
    )
