# Hostinger 원격 모니터링 운영

접속 주소: **https://srv1934103.hstgr.cloud:8443/**

## 구성

Mac의 기존 `127.0.0.1:8095` 서비스를 SSH 역방향 터널로 VPS의
`127.0.0.1:18095`에 연결한다. VPS의 Docker nginx 게이트웨이가 HTTPS와
Basic 인증을 제공한다. DB와 원천 파일은 Mac에 유지한다.
Mac이 잠자거나 꺼지면 원격 화면을 사용할 수 없다. 다시 연결되면 SSH가 재접속한다.

- VPS 프로젝트: `/docker/multi-ai-agent-platform`
- Compose 서비스: `gateway`; 외부 포트 `8443`, 내부 상태 점검 `127.0.0.1:18096`
- Mac 서비스: `gui/501/local.agentdash.hostinger-tunnel`
- Mac 접속 정보: 저장소의 `data/hostinger/access.txt` (권한 600, Git 제외)
- Mac 전용 키: `~/.ssh/agentdash_hostinger_ed25519` (권한 600)
- Mac 터널 로그: `data/hostinger/tunnel.{stdout,stderr}.log`

전용 SSH 계정 `agentdash-tunnel`은 셸 실행을 허용하지 않으며,
키의 `permitlisten`으로 VPS loopback 18095 포트만 허용한다.
게이트웨이는 GET/HEAD만 허용하고 `/hooks/` 및 `/agents/<key>/raw`를 차단한다.
원본 보기 기능은 로컬 대시보드에서 사용한다.

## 배포 설정과 점검

`compose.yaml`, `nginx.conf`를 VPS 프로젝트에 배치하고 `.htpasswd`와
다음 `.env`를 별도로 준비한다. 실제 암호·키를 커밋하지 않는다.

```dotenv
NGINX_IMAGE=nginx@sha256:970364228b1e4f932abc22d321932816782cca8a20b85a77552a7cfe9acfb3b5
TLS_DIRECTORY=/var/lib/docker/volumes/rodem-mes_caddy_data/_data/caddy/certificates/acme-v02.api.letsencrypt.org-directory/srv1934103.hstgr.cloud
```

TLS 인증서는 기존 Caddy가 갱신하며 nginx는 6시간마다 무중단으로 다시 읽는다.
이 인증서 경로가 바뀌면 `.env`를 수정하고 게이트웨이를 재생성한다.
기존 Caddy 프로젝트나 다른 컨테이너는 재시작하지 않는다.

```sh
# VPS 프로젝트 폴더에서 실행
docker compose config --quiet
docker compose up -d
docker compose ps
docker compose logs --tail 30
```

`healthy`는 nginx와 Mac 연결을 함께 확인한다. 외부 비인증 요청은 HTTP 401,
로그인 후 `/`와 `/api/v1/summary`는 200이어야 한다.
`/api/v1/stream`은 `Accept: text/event-stream`에서 `hello`와 15초 간격 ping을 보낸다.

```sh
# Mac에서 상태 확인 / 연결 재시작 / 원격 접속 중지
launchctl print gui/501/local.agentdash.hostinger-tunnel
launchctl kickstart -k gui/501/local.agentdash.hostinger-tunnel
launchctl bootout gui/501/local.agentdash.hostinger-tunnel
```

중지 후 재등록은 `launchctl bootstrap gui/501 ~/Library/LaunchAgents/local.agentdash.hostinger-tunnel.plist`.
VPS에서 `docker compose down`은 이 게이트웨이만 중지한다. Mac의 기존 대시보드는 유지된다.
