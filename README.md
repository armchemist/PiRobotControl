# PiRobotControl

실험실 장비 중 **움직이는 것들**을 맡는 라즈베리파이(파이1)의 코드.
로봇 팔과 핸디캠을 HTTP API로 노출한다.

이 파이는 **리니어 스테이지(레일) 위에 올라가서 같이 움직인다.** 팔과 캠으로
가는 USB 케이블이 레일 이동 중에 늘어졌다 당겨지지 않게 하기 위해서다.

## 두 개의 파이

실험대는 파이 두 대로 나뉜다. 기준은 *센서/구동* 이 아니라 **움직이는 것 /
고정된 것** 이다.

| | 파이1 (이 저장소) | 파이2 ([PiSensorServer](https://github.com/armchemist/PiSensorServer)) |
| --- | --- | --- |
| 위치 | **레일 위 — 같이 움직인다** | 고정 |
| 하드웨어 | 로봇 팔 USB×2, 핸디캠 USB×2 | 열화상 USB, 우노(pH·전도도), **레일 구동** |
| 저장소 | `PiRobotControl` | `PiSensorServer` |

레일을 **구동하는 쪽**이 파이2인 게 헷갈리기 쉬운데, 스텝모터 드라이버에 GPIO로
직결돼야 하기 때문이다. 움직이는 파이에서 고정된 드라이버로 배선을 끌면 이동할
때마다 굽혀진다. 그래서 레일 위에 **타는** 것은 파이1, 레일을 **미는** 것은
파이2다.

두 파이는 서로를 모른다. 클라우드 에이전트가 양쪽 주소를 각각 호출한다.

```
        클라우드 (LLM 에이전트)
          │              │
     HTTP │              │ HTTP
  ┌───────┴──────┐  ┌────┴─────────┐
  │ 파이1 (동적)  │  │ 파이2 (정적)  │
  │ 레일 위에 탑승 │  │              │
  └──┬────────┬──┘  └─┬───┬────┬───┘
     │        │       │   │    │
    USB×2   USB×2   GPIO USB  USB
    로봇팔   핸디캠   레일  열화상 우노
                                │
                          pH / 전도도
```

## 구조

| 디렉토리 | 내용 |
| --- | --- |
| [`arm/`](arm/) | 로봇 팔 (OpenManipulator, ROS 2 Jazzy) |
| [`server/`](server/) | 위 하드웨어를 HTTP API로 노출 |

## 설치

파이1에서. 하드웨어를 직접 다루는 패키지는 apt로, 나머지는 venv에 받는다.

```bash
sudo apt update
sudo apt install -y python3-venv python3-opencv

git clone https://github.com/armchemist/PiRobotControl.git
cd PiRobotControl
python3 -m venv --system-site-packages .venv
.venv/bin/pip install fastapi "uvicorn[standard]"
```

`--system-site-packages` 가 있어야 venv 안에서 apt로 설치한 `cv2` 를 볼 수 있다.
빼먹으면 카메라가 동작하지 않는다.

ARM에서 opencv를 pip로 설치하면 빌드에 아주 오래 걸리거나 실패하므로 apt를 쓴다.

## 실행

```bash
.venv/bin/python -m server.run
```

포트를 바꾸려면 `PORT=9000 .venv/bin/python -m server.run`.

SSH 창을 닫아도 유지하려면 `setsid` 를 붙인다.

```bash
setsid .venv/bin/python -m server.run > /tmp/server.log 2>&1 &
```

재부팅까지 살리려면 systemd에 등록한다.

```bash
sudo cp server/pi-robot-control.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now pi-robot-control
```

`journalctl -u pi-robot-control -f` 로 로그를 본다.

### uvicorn 을 직접 부르지 않는 이유

`uvicorn --host` 로는 IPv4와 IPv6 중 한쪽만 열린다.

| 명령 | 결과 |
| --- | --- |
| `--host 0.0.0.0` | IPv4만. IPv6 전용 네트워크(아이폰 핫스팟 등)에서 접속 불가 |
| `--host ::` | IPv6만. 일반 공유기(IPv4)에서 접속 불가 |

커널 기본값은 듀얼 스택이지만, 파이썬 `asyncio` 의 `create_server()` 가 IPv6
주소로 바인드할 때 `IPV6_V6ONLY` 소켓 옵션을 명시적으로 켜기 때문이다.
`server/run.py` 는 소켓을 직접 만들어 그 옵션을 끈 뒤 uvicorn 에 넘긴다.

## 엔드포인트

| 메서드 | 경로 | 설명 |
| --- | --- | --- |
| `GET` | `/health` | 하드웨어 연결 상태 |
| `GET` | `/camera/capture` | 현재 프레임 (JPEG) |
| `GET` | `/camera/stream` | MJPEG 실시간 스트림. `?fps=10` (1~30) |
| `POST` | `/arm/pose` | 미구현 (ROS 2 설치 필요) |

문서는 `http://pi1.local:8000/docs` (Swagger UI).

### 상태 코드

| 코드 | 의미 |
| --- | --- |
| `422` | 입력값 검증 실패 |
| `501` | 아직 구현되지 않은 기능 |
| `503` | 하드웨어가 연결되지 않았거나 초기화 실패 |

`503` 은 하드웨어를 꽂으면 해결되고, `422` 는 명령을 바꿔야 해결된다.

## ⚠️ 아직 안 된 것

**핸디캠이 2대인데 코드는 1대만 연다.** `server/hardware/camera.py` 는
`cv2.VideoCapture(CAMERA_INDEX)` 로 하나만 잡는다. 2대를 쓰려면 다중 카메라
지원이 필요하다.

그때 **인덱스를 쓰면 안 된다.** USB 카메라의 `/dev/videoN` 번호는 재부팅마다,
그리고 꽂는 순서에 따라 뒤바뀐다. 캠이 2대면 어느 날 갑자기 좌우가 바뀐다.
`/dev/v4l/by-id/` 의 안정적인 경로로 잡아야 한다.

```bash
ls -l /dev/v4l/by-id/
```

**로봇 팔은 `/arm/pose` 가 501 이다.** 파이에 ROS 2 Jazzy 설치가 먼저 필요하고,
USB가 2개인 구성(팔 2대인지, 팔+그리퍼인지)이 확정돼야 API 모양을 정할 수 있다.

`arm/ros_launcher.py` 는 파이용이 아니라 **PC에서 도는 tkinter 창**이다.
paramiko로 파이에 SSH 붙어 ROS 명령을 던진다. 서버와는 별개로 동작한다.

## 하드웨어가 없어도 뜬다

카메라나 팔이 빠져 있어도 서버는 정상적으로 시작한다. 없는 것은 `/health` 에
이유와 함께 보고되고, 해당 엔드포인트만 `503` 을 돌려준다. 하나씩 붙여가며
확인할 수 있도록 한 것이다.

## ⚠️ 외부 노출 전에 API 키를 설정할 것

```bash
export API_KEY='충분히 긴 무작위 문자열'
```

설정하면 모든 요청에 `X-API-Key` 헤더가 필요해진다. 설정하지 않으면 인증 없이
누구나 로봇 팔을 움직일 수 있다. **로컬 테스트 중에만 생략할 것.**

브라우저에서 스트림을 볼 때는 `<img>` 에 헤더를 붙일 수 없어서 `?api_key=...`
쿼리스트링도 받는다. 다만 접근 로그에 남으므로 노출된 환경에서는 권하지 않는다.

## 안전

에이전트를 안전장치로 믿으면 안 된다. 프롬프트는 지켜질 수도, 지켜지지 않을 수도
있다. 한계는 서버 코드에 강제되어야 한다.

로봇 팔은 아직 미구현이지만, 구현할 때 반드시 필요한 것:

- 관절 각도·속도의 소프트 리밋 (스키마와 코드 양쪽에서)
- 동시에 두 개의 동작 명령이 실행되지 않도록 잠금
- 물리 비상정지 버튼 (소프트웨어 밖에 있어야 한다)
- 명령 로그 — 무엇을 왜 했는지 추적할 수 있어야 한다

⚠️ 이 파이는 레일 위에 있다. **팔이 뻗은 상태에서 레일이 움직이면 충돌한다.**
레일은 파이2가 제어하므로 두 파이가 서로의 상태를 모른다는 점에 주의할 것.
동시 동작 방지는 현재 어느 쪽에도 구현돼 있지 않다 — 에이전트가 순서를 지켜야
하는데, 그건 안전장치가 아니다.

## 설정 (환경변수)

| 변수 | 기본값 | 설명 |
| --- | --- | --- |
| `PORT` | `8000` | 서버 포트 |
| `CAMERA_INDEX` | `0` | `/dev/video0` |
| `CAMERA_WIDTH` / `CAMERA_HEIGHT` | `1280` / `720` | |
| `API_KEY` | (없음) | 설정 시 인증 필수 |
