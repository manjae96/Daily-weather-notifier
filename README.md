# Daily Weather Notifier

마곡·선릉·미아사거리의 오전/오후 날씨·강수·미세먼지를 매일 아침 07:00 KST에 텔레그램으로 발송. RAG로 옷차림·건강·교통 조언 보강.

## 스택
Python 3.12 + FastAPI · Qdrant · Google Gemini (LLM + 임베딩) · k3s · GitHub Actions + ghcr.io

## 구조
```
app/         FastAPI + 수집기 + 판단 + RAG + 알림
docs/rag/    RAG 지식베이스 (옷차림/건강/교통)
tests/       pytest 단위 테스트
k8s/all.yaml K8s 매니페스트 일체
.github/     CI 파이프라인
scripts/     k3s 설치/조인 스크립트
```

## 로컬 개발
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt pytest pytest-cov pytest-asyncio ruff
cp .env.example .env  # 키 입력
pytest
uvicorn app.main:app --reload
```

## 배포 (k3s 기준)
```bash
# 1) 마스터 설치
bash scripts/k3s-master-install.sh

# 2) 워커 조인 (마스터에서 token 확인)
sudo cat /var/lib/rancher/k3s/server/node-token
# 워커에서:
K3S_URL=https://<master-ip>:6443 K3S_TOKEN=<token> bash scripts/k3s-worker-join.sh

# 3) Secret 주입 (절대 git에 커밋 금지)
kubectl create namespace weather
kubectl -n weather create secret generic weather-secrets \
  --from-literal=KMA_API_KEY=xxx \
  --from-literal=AIRKOREA_API_KEY=xxx \
  --from-literal=GEMINI_API_KEY=xxx \
  --from-literal=TELEGRAM_BOT_TOKEN= \
  --from-literal=TELEGRAM_CHAT_ID=

# 4) 매니페스트 적용 (Secret 블록은 미리 제거 또는 placeholder 유지)
# k8s/all.yaml 안의 REPLACE_OWNER → 본인 GitHub 계정명으로 치환
kubectl apply -f k8s/all.yaml

# 5) RAG 문서 인덱싱 (1회)
kubectl -n weather port-forward svc/weather-api 8000:80 &
curl -X POST http://localhost:8000/rag/ingest

# 6) 동작 확인
curl http://localhost:8000/today/마곡
curl -X POST http://localhost:8000/trigger/morning-brief
```

## CronJob 시각
`k8s/all.yaml`의 schedule은 `0 22 * * *` + `timeZone: Asia/Seoul`. K8s 1.27 미만이면 timeZone 라인 제거 (UTC 22:00 = KST 07:00).

## 텔레그램 활성화 (나중에)
`@BotFather` → `/newbot` → 토큰 획득 → 본인이 봇에 `/start` → `https://api.telegram.org/bot<TOKEN>/getUpdates`로 chat_id 확인 → Secret 업데이트 후 `kubectl rollout restart`.

## 향후 Ollama 전환
`app/llm/client.py`에 `OllamaClient` 추가 → `LLM_PROVIDER=ollama` 환경변수만 변경. 코드 변경 0줄.
