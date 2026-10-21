# 로컬 운영 안내

## 운영 기준

- 운영 DB: `data/agentdash.db`. 삭제된 원천의 보관 기록도 포함한다.
- 운영 주소: `http://127.0.0.1:8095/`. 다른 주소로 바인드하지 않는다.
- 검증 DB: `data/agentdash-review-20261021.db`. 운영 DB로 교체하지 않는다.
- 개발/검증 포트: 8096 또는 8097. 기존 서버를 포트로 찾아 종료하지 않는다.
- Python 3.12와 `uv`를 사용한다. 아래 명령은 저장소 루트에서 실행한다.

## 수동 실행

현재는 아래 자동 실행 서비스가 8095번을 사용한다. 서비스를 중지한 경우에만 수동 명령을 실행한다.

```sh
AGENTDASH_DB=data/agentdash.db AGENTDASH_PORT=8095 \
  uv run --frozen --offline python -m agentdash.app
```

화면에서 「실시간: 연결됨」을 확인한다. 실행 터미널에서 `Ctrl+C`로 종료한다.
기동 시 감시기가 기존 DB의 읽은 위치부터 증분 수집하므로 매번 새 DB를 만들 필요가 없다.
`--offline`은 설치된 환경으로 실행하며, 초기 설치/의존성 변경은 별도로 `make setup`을 사용한다.

## 데이터 유지보수

```sh
AGENTDASH_DB=data/agentdash.db make backfill
AGENTDASH_DB=data/agentdash.db make reestimate
```

`backfill`은 기존 오프셋 이후 기록을 수집하고 관계·상태·일 집계를 갱신한다. 오래된 보관 행을 지우지 않는다.
`reestimate`는 현재 원천을 재처리해 기록값이 일치하는 요청의 추정값만 보완하며, 변경 전 자동 백업을 만든다.
원천이 사라진 행의 추정값은 복원하지 못한다. `output_est=NULL`은 비의심 요청에도 정상이다.
보관 행의 `output_est`가 NULL이고 추정 비용만 비어 있으면 `make reprice`로 기록 비용을 추정 비용 칸에도 적용한다.
이는 출력 토큰 보정의 복원이 아니라 기록값 기준 비용이다. 단가표 변경 후 실행하면 기록 비용도 재계산되므로 먼저 백업하고 변경 건수를 확인한다.
새 검증 DB로 운영 DB를 덮어쓰거나, 실행 중인 SQLite 파일을 `cp`로 백업하지 않는다. 백업은 SQLite backup API를 사용한다.

## 로그인 시 자동 실행

2026-10-21 사용자 승인 후 설치·기동 완료: 서비스 `gui/501/local.agentdash.dashboard`.
설치 파일은 `~/Library/LaunchAgents/local.agentdash.dashboard.plist`, 원본은 `data/local.agentdash.dashboard.plist`다.
`launchctl print`의 running, HTTP 200, 브라우저 「실시간: 연결됨」을 확인했다.
재설치 전에는 `plutil -lint data/local.agentdash.dashboard.plist`로 검사하고 내용을 확인한다.
이 파일은 로컬 준비물이므로 Git에 포함하지 않는다. 저장소를 옮기거나 `uv` 경로가 바뀌면 수정이 필요하다.

설정은 운영 DB와 8095번 포트를 지정하고, 로그인 시 시작하며, 프로세스가 종료되면 다시 실행한다.
로그는 `data/agentdash-server.stdout.log`와 `data/agentdash-server.stderr.log`에 남는다.
아래 설치 절차는 미등록 상태에서만 사용한다. 이미 실행 중이면 상태 조회·중지·재시작 절차를 사용한다.

```sh
mkdir -p "$HOME/Library/LaunchAgents"
cp -i data/local.agentdash.dashboard.plist "$HOME/Library/LaunchAgents/local.agentdash.dashboard.plist"
launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/local.agentdash.dashboard.plist"
launchctl print "gui/$(id -u)/local.agentdash.dashboard"
```

기존 수동 서버가 8095번에서 실행 중이면 먼저 그 실행 터미널에서 종료한다. 같은 서비스를 중복 등록하지 않는다.

```sh
# 자동 재시작도 멈추기
launchctl bootout "gui/$(id -u)/local.agentdash.dashboard"
# 설치된 서비스를 다시 시작하기
launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/local.agentdash.dashboard.plist"
# 실행 중인 서비스 재시작
launchctl kickstart -k "gui/$(id -u)/local.agentdash.dashboard"
```

## 점검

```sh
curl --max-time 3 -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8095/
uv run python src/agentdash/tools/check_counts.py
uv run python src/agentdash/tools/check_no_payload.py
```

HTTP 200, 원천 수집 검사 PASS, 본문 미저장 검사 PASS를 확인한다.
35개 수용 게이트는 검증 DB로 `AGENTDASH_DB=data/agentdash-review-20261021.db make gate`를 사용한다.
운영 서버가 켜져 있으면 G-15의 서버 꺼짐 시험은 미검증이 될 수 있다. 서버를 임의로 종료해 통과시키지 않는다.
실제 훅 설치와 예산 금액 입력은 별도 사람 작업이다.
