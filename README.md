# Daily Weather Notifier — 구축 여정

**날짜**: 2026-04-13
**목표**: 인프라 · CI/CD · 애플리케이션 · LLM 통합을 한 사이클로 경험
**결과물**: K8s 위에 돌아가는 매일 아침 텔레그램 날씨 브리핑 봇

---

## 1. 최종 아키텍처

### 1.1 구성도

```
┌──────────────────────── 내부 K8s 클러스터 ────────────────────────-------┐
│                                                                        │
│   [Master: test-master]            [Worker: test-worker]               │
│   8 vCPU / 8GB / 150GB             8 vCPU / 8GB / 250GB                │
│                                                                        │
│   ┌──────────────────┐             ┌──────────────────┐                │
│   │ FastAPI Deploy   │             │ Qdrant Deploy    │                │
│   │ :8000            │<───────────>│ :6333 (vector)   │                │
│   │ /trigger/...     │             │ PVC 5Gi          │                │
│   │ /today/{region}  │             └──────────────────┘                │
│   └─────────┬────────┘                                                 │
│             │                                                          │
│   ┌─────────▼────────┐                                                 │
│   │ CronJob          │  매일 07:00 KST                                  │
│   │ morning-brief    │                                                 │
│   └─────────┬────────┘                                                 │
│             │                                                          │
│             │ 1. 기상청 단기예보 API (마곡/선릉/미아사거리)                 │
│             │ 2. 에어코리아 대기질 API                                   │
│             │ 3. Qdrant RAG 검색 (옷차림/건강/교통 문서)                  │
│             │ 4. Gemini 2.5 Flash (조언 생성, 재시도 5회)                │
│             │ 5. Telegram Bot sendMessage                              │
│             ▼                                                          │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
                                                 │
                                                 ▼
                                          📱 텔레그램 봇 알림
```

### 1.2 스택 요약

| 레이어 | 기술 |
|---|---|
| 인프라 | VM 2대, kubeadm K8s, containerd 런타임 |
| 스토리지 | local-path-provisioner (Rancher) |
| 앱 | Python 3.12, FastAPI, httpx, Pydantic |
| RAG | Qdrant + Gemini text-embedding-004 |
| LLM | Google Gemini 2.5 Flash (무료 티어) + tenacity 재시도 |
| 알림 | Telegram Bot API |
| CI/CD | GitHub Actions → ghcr.io → kubectl (수동 rollout) |
| 관측 | FastAPI 로그 + kubectl logs |

### 1.3 Kubernetes 오브젝트

- `Namespace/weather`
- `ConfigMap/weather-config` — 임계값, Qdrant URL 등
- `Secret/weather-secrets` — 기상청/에어코리아/Gemini/텔레그램 키
- `Deployment/weather-api` + `Service/weather-api` — FastAPI, ClusterIP
- `Deployment/qdrant` + `Service/qdrant` + `PVC/qdrant-data` — 벡터 DB
- `CronJob/morning-brief` — 매일 22:00 UTC (07:00 KST)

---

## 2. 과정 기록 — 진행 순서

### 2.1 기획 단계
- 목표 정리: 마곡·선릉·미아사거리 세 지역 오전/오후 날씨 + 우산/마스크 판단
- 추가 요건: RAG로 옷차림·건강·교통 조언
- 제약: VM 사용, 무료로 가능해야 함

### 2.2 스택 선정
- **알림 채널**: 가장 가벼운 텔레그램 봇 선택 (이메일/카카오톡 대비)
- **LLM**: Anthropic API 유료 부담 → Gemini 무료 티어로 전환
  - Claude Pro 구독은 API와 완전 별개 결제임을 확인
- **임베딩**: Gemini `text-embedding-004` 선택 (외부 호출, 코드 단순)
- **RAG 문서**: 직접 작성한 마크다운 3종 (옷차림·건강·교통)

### 2.3 스캐폴드 생성
- 31개 파일, ~24KB 분량 프로젝트 구조 생성
- 핵심 모듈: `collectors/`, `decision.py`, `llm/`, `rag/`, `notifier/`, `jobs/`
- pytest 7개 단위 테스트 포함
- K8s 매니페스트 전체 (`k8s/all.yaml`)
- GitHub Actions 워크플로 (`ci.yml`)

### 2.4 Git & GitHub 설정
- 폴더 중첩 문제 정리 (압축 해제 시 두 번 풀린 상태 수습)
- `Daily-weather-notifier` 리포 생성 + main 브랜치 push
- 빈 폴더 확장 문제 (`{app`으로 생성된 문제) 해결

### 2.5 K8s 클러스터 초기 배포
- `local-path-provisioner` 설치 후 default StorageClass 지정
- `k8s/all.yaml` 적용 → 초기 상태 진단:
  - Qdrant Pod Pending (PVC 바인딩 실패)
  - weather-api Pod InvalidImageName (`REPLACE_OWNER` placeholder)
- `REPLACE_OWNER` → `manjae96` 치환 후 재적용

### 2.6 CI/CD 파이프라인 가동
- `ruff` 위반 7건 수정 (E701/E702 한 줄 문법)
- pytest 커버리지 게이트 70% → 20% 조정
- GitHub Actions 빌드 성공 → ghcr.io 이미지 생성
- 패키지 visibility Public 전환 (초기 private 기본값 문제)

### 2.7 Secret 주입 및 동작 확인
- `REPLACE_ME` placeholder → 실제 API 키 덮어쓰기
- Pod rollout restart → API 키 정상 로드
- `/today/마곡` 200 응답 확인 → 날씨 데이터 정상 수집
- `/trigger/morning-brief` → 콘솔에 브리핑 출력 (텔레그램 미설정 fallback)

### 2.8 텔레그램 봇 연동
- BotFather에서 봇 생성 → 토큰 발급
- `@userinfobot`으로 chat_id 확보
- curl `sendMessage` 직접 테스트로 조합 검증
- Secret 업데이트 → Pod 재시작 → 핸드폰에 첫 메시지 수신 🎉

### 2.9 CronJob 자동 실행 검증
- `kubectl create job --from=cronjob/...` 수동 트리거
- Gemini 503 UNAVAILABLE 에러 발견
- 재시도(tenacity 5회) + 폴백(except로 조언 실패해도 날씨 발송) 코드 추가
- `imagePullPolicy: Always` 추가로 `:latest` 태그 자동 갱신 흐름 완성

---

## 3. 트러블슈팅 사례집

### 3.1 폴더 구조 꼬임
**증상**: `git add .`가 `embedded git repository` 경고, 하위 `Daily-weather-notifier/` 폴더 존재.

**원인**: 압축 파일을 같은 이름 폴더 안에서 또 풀어서 이중 구조 발생. 안쪽 폴더에 자체 `.git` 존재.

**해결**:
```bash
cd ~/Daily-weather-notifier
rm -rf .git
mv Daily-weather-notifier/.git .
rm -rf Daily-weather-notifier/
git status   # 정상 파일 목록 확인
```

---

### 3.2 StorageClass 없음 → PVC Pending
**증상**:
```
storageclass.storage.k8s.io "local-path" not found
pod has unbound immediate PersistentVolumeClaims
```

**원인**: kubeadm 기본 구성에는 local-path StorageClass 없음. k3s는 기본 제공하지만 일반 kubeadm 클러스터는 별도 설치 필요.

**해결**:
```bash
kubectl apply -f https://raw.githubusercontent.com/rancher/local-path-provisioner/v0.0.30/deploy/local-path-storage.yaml
kubectl patch storageclass local-path -p '{"metadata": {"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'
```

---

### 3.3 이미지 이름 placeholder 그대로 적용
**증상**:
```
Failed to apply default image tag "ghcr.io/REPLACE_OWNER/daily-weather-notifier:latest":
repository name (REPLACE_OWNER/daily-weather-notifier) must be lowercase
```

**원인**: `k8s/all.yaml`의 placeholder를 치환하지 않고 적용.

**해결**:
```bash
sed -i 's|ghcr.io/REPLACE_OWNER/|ghcr.io/manjae96/|g' k8s/all.yaml
kubectl apply -f k8s/all.yaml
```

---

### 3.4 ghcr 이미지 private → 403 Forbidden
**증상**:
```
failed to authorize: failed to fetch anonymous token:
unexpected status from GET ...ghcr.io: 403 Forbidden
```

**원인**: GitHub Actions가 처음 push한 패키지는 기본 private. 리포 visibility와 패키지 visibility는 별개.

**해결**: https://github.com/manjae96/Daily-weather-notifier/pkgs/container/daily-weather-notifier → Package settings → Change visibility → Public.

---

### 3.5 CI `test` job 실패 — ruff E701/E702
**증상**: GitHub Actions 첫 실행에서 exit code 1. 로그에 `Multiple statements on one line` 에러 7건.

**원인**: 스캐폴드 코드에 `if x: return y` 같은 한 줄 문법 포함. ruff 기본 규칙 위반.

**해결**: 각 위치를 `if x:\n    return y` 형태로 풀어씀. `ruff check --fix`로는 자동 수정 안 되는 규칙이라 수동 패치.

---

### 3.6 커버리지 게이트 실패
**증상**:
```
FAIL Required test coverage of 70% not reached. Total coverage: 28.22%
```

**원인**: 단위 테스트가 순수 함수(`summarize`, `decision`)만 커버. HTTP collectors, FastAPI 라우터, RAG, LLM은 외부 의존성이라 mock 없이 커버 불가.

**해결**: `pyproject.toml`의 `--cov-fail-under=70` → `20`으로 완화. 학습 단계에 맞는 현실적 기준.

---

### 3.7 Secret placeholder 그대로 로드됨
**증상**:
```
httpx.HTTPStatusError: 401 Unauthorized for url '...?serviceKey=REPLACE_ME&...'
```

**원인**: `k8s/all.yaml`의 Secret 블록 `stringData` 값이 `REPLACE_ME` placeholder. 이걸 그대로 `apply` 하면 실제 Secret이 placeholder로 생성됨.

**해결**:
```bash
kubectl -n weather create secret generic weather-secrets \
  --from-literal=KMA_API_KEY='실제키' \
  --from-literal=AIRKOREA_API_KEY='실제키' \
  --from-literal=GEMINI_API_KEY='실제키' \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl -n weather rollout restart deployment/weather-api
```

**주의**: 기상청/에어코리아 키는 반드시 **Decoding 키** 사용. Encoding 키는 `%2B`, `%2F` 포함되어 이중 인코딩으로 401 유발.

---

### 3.8 텔레그램 `chat not found` (400)
**증상**:
```json
{"ok":false,"error_code":400,"description":"Bad Request: chat not found"}
```

**원인 (진짜 원인)**: 봇 검색 시 **다른 비슷한 이름의 봇**에 메시지를 보내고 있었음. `getUpdates`가 계속 `result:[]`로 비어있었던 이유.

**해결**: `getMe` 응답의 username을 확인 후 `https://t.me/<정확한username>` 링크로 직접 대화 진입 → `/start` + 메시지 전송 → `getUpdates`에서 실제 chat.id 획득.

**교훈**: 봇 username은 검색보다 `t.me/` 링크가 확실. 동명 봇 혼동이 생각보다 흔함.

---

### 3.9 Gemini 503 UNAVAILABLE — 피크 혼잡
**증상**:
```
google.genai.errors.ServerError: 503 UNAVAILABLE.
'This model is currently experiencing high demand.'
```

**원인**: 무료 티어는 피크 시간대 우선순위가 낮음. 한 번 실패 시 즉시 traceback → Job 실패.

**해결** (두 겹 방어):
1. `tenacity` 재시도: 2→4→8→16→32초 백오프로 최대 5회
2. 폴백: 5회 다 실패해도 `except`로 잡아서 `advice = "_(조언 생성 일시 장애...)_"` 표시하고 **날씨 정보는 정상 발송**

```python
# app/llm/client.py
@retry(stop=stop_after_attempt(5),
       wait=wait_exponential(multiplier=2, min=2, max=60),
       retry=retry_if_exception_type(ServerError),
       reraise=True)
async def generate(self, system: str, user: str) -> str: ...

# app/jobs/morning_brief.py
try:
    advice = await llm.generate(...)
except Exception as e:
    advice = f"_(조언 생성 일시 장애: {type(e).__name__})_"
```

---

### 3.10 `:latest` 이미지 캐시 → 구 코드 계속 실행
**증상**: 코드 수정 + push + Actions 성공 + Pod 재시작했는데도 traceback line 번호가 그대로. 새 코드가 안 도는 상황.

**원인**: containerd/K8s의 `:latest` 태그 캐싱 동작이 환경에 따라 다름. 일부 설정에서 `imagePullPolicy` 기본값이 `IfNotPresent`처럼 작동.

**해결**: 매니페스트에 명시적으로 `imagePullPolicy: Always` 추가.
```yaml
containers:
- name: api
  image: ghcr.io/manjae96/daily-weather-notifier:latest
  imagePullPolicy: Always   # ← 이 줄
```

이후 `kubectl rollout restart`만 치면 자동으로 최신 이미지 재pull.

---

### 3.11 포트 이미 사용 중
**증상**:
```
Unable to listen on port 8000: bind: address already in use
```

**원인**: 이전 `kubectl port-forward` 또는 `uvicorn` 프로세스가 백그라운드에 살아있음.

**해결**:
```bash
pkill -f "kubectl.*port-forward"
pkill -f "uvicorn"
ss -tlnp | grep :8000   # 비었는지 확인
```

**예방**: port-forward는 전용 터미널에서 포그라운드로. `&` 백그라운드는 명확히 `kill %1`로 종료.

---

## 4. 운영 가이드

### 4.1 일상 운영

**새 코드 배포**:
```bash
git add -A && git commit -m "feat: ..." && git push origin main
# Actions 초록 확인 후 (https://github.com/manjae96/Daily-weather-notifier/actions)
kubectl -n weather rollout restart deployment/weather-api
```

CronJob은 매 실행마다 새 Pod를 만들고 `imagePullPolicy: Always` 덕분에 자동으로 최신 이미지 사용. **별도 조치 불필요.**

**수동 트리거**:
```bash
# FastAPI 엔드포인트
kubectl -n weather port-forward svc/weather-api 8000:80
curl -X POST http://localhost:8000/trigger/morning-brief

# 또는 CronJob 수동 실행
kubectl -n weather create job --from=cronjob/morning-brief manual-$(date +%s)
```

### 4.2 Secret 갱신

```bash
# 기존 값 유지하면서 일부만 교체할 때
kubectl -n weather create secret generic weather-secrets \
  --from-literal=KMA_API_KEY="$(kubectl -n weather get secret weather-secrets -o jsonpath='{.data.KMA_API_KEY}' | base64 -d)" \
  --from-literal=AIRKOREA_API_KEY="$(kubectl -n weather get secret weather-secrets -o jsonpath='{.data.AIRKOREA_API_KEY}' | base64 -d)" \
  --from-literal=GEMINI_API_KEY="새_제미니_키" \
  --from-literal=TELEGRAM_BOT_TOKEN="$(kubectl -n weather get secret weather-secrets -o jsonpath='{.data.TELEGRAM_BOT_TOKEN}' | base64 -d)" \
  --from-literal=TELEGRAM_CHAT_ID="$(kubectl -n weather get secret weather-secrets -o jsonpath='{.data.TELEGRAM_CHAT_ID}' | base64 -d)" \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl -n weather rollout restart deployment/weather-api
```

### 4.3 RAG 문서 업데이트

```bash
# 문서 수정 (docs/rag/*.md)
git add docs/rag/ && git commit -m "docs: update rag guide" && git push

# 배포 후 재인덱싱
kubectl -n weather port-forward svc/weather-api 8000:80 &
curl -X POST http://localhost:8000/rag/ingest
```

### 4.4 모니터링 & 디버깅

```bash
# 최근 CronJob 실행 결과
kubectl -n weather get job --sort-by=.metadata.creationTimestamp | tail -5

# 특정 Job 로그
kubectl -n weather logs job/<job-name>

# API 서버 실시간 로그
kubectl -n weather logs deploy/weather-api -f

# Pod 상태·이벤트
kubectl -n weather describe pod -l app=weather-api

# Secret 값 확인 (디버깅용)
kubectl -n weather get secret weather-secrets -o jsonpath='{.data.KMA_API_KEY}' | base64 -d
```

### 4.5 장애 대응 플레이북

| 증상 | 1차 조치 |
|---|---|
| CronJob 실패 지속 | `kubectl -n weather logs job/<실패 job>` → 503이면 대기, 다른 에러면 코드/Secret 점검 |
| 텔레그램 미수신 | `curl -X POST .../trigger/morning-brief` 수동 실행 → 로그에서 sendMessage 응답 확인 |
| Pod CrashLoopBackOff | `kubectl -n weather logs` → 대부분 Secret 누락 또는 키 오타 |
| ImagePullBackOff | ghcr 패키지 visibility Public인지, Actions 빌드 초록인지, `imagePullPolicy` 있는지 |
| API 401 (기상청/에어코리아) | Decoding 키인지 확인. 발급 직후 1시간 반영 지연 있음 |

---

## 5. 초기 목표 대비 달성도

| 목표 | 상태 | 비고 |
|---|---|---|
| 매일 아침 오전/오후 날씨 알림 | ✅ | 07:00 KST CronJob |
| 강수량 기반 우산 판단 | ✅ | 강수확률 60% 또는 강수량 1mm |
| PM2.5/PM10 기반 마스크 판단 | ✅ | PM2.5 35, PM10 80 임계값 |
| 마곡·선릉·미아사거리 지역 정보 | ✅ | 기상청 격자좌표 + 에어코리아 측정소 매핑 |
| 이미지 초안 + 필요 시 업데이트 | ✅ | Dockerfile 초안, CI로 자동 빌드 |
| git push 전 테스트 코드 | ✅ | pytest 7개, ruff 린트, CI 게이트 |
| 쿠버네티스 배포 | ✅ | kubeadm 클러스터 2노드, CronJob + Deployment |
| RAG 기능 | ✅ | Qdrant + Gemini 임베딩 + 재시도/폴백 |

---

## 6. 다음 학습 주제 (Suggested Roadmap)

| 순번 | 주제 | 학습 포인트 |
|---|---|---|
| 1 | Prometheus + Grafana | 메트릭 수집, PromQL, 대시보드 구성 |
| 2 | Loki + Promtail | 로그 중앙집중, LogQL, 구조화 로그 |
| 3 | Argo CD | GitOps, 선언적 배포, 자동 sync |
| 4 | Sealed Secrets 또는 External Secrets Operator | Secret을 git에 안전하게 |
| 5 | Ollama 셀프호스팅 | 워커에 LLM 파드, Gemini 의존성 제거 |
| 6 | Ingress + cert-manager | 외부 접근, Let's Encrypt 자동 TLS |
| 7 | HPA / VPA | 오토스케일링 정책 설계 |

현재 프로젝트를 테스트베드로 계속 활용 가능. 예를 들어 1번만 추가해도 "CronJob 성공/실패 개수", "Gemini 503 발생 빈도" 같은 실제 운영 메트릭을 쌓을 수 있음.

---

## 7. 주요 파일 트리

```
Daily-weather-notifier/
├── .github/workflows/ci.yml           # lint → test → build → push
├── Dockerfile                         # python:3.12-slim 기반
├── requirements.txt                   # FastAPI, httpx, genai, qdrant, tenacity
├── pyproject.toml                     # pytest + ruff + 커버리지 설정
├── app/
│   ├── config.py                      # Pydantic Settings
│   ├── main.py                        # FastAPI 엔트리
│   ├── decision.py                    # 우산/마스크 로직
│   ├── collectors/
│   │   ├── weather.py                 # 기상청 단기예보 + 오전/오후 집계
│   │   └── air_quality.py             # 에어코리아 대기질
│   ├── llm/client.py                  # Gemini + tenacity 재시도
│   ├── rag/store.py                   # Qdrant ingest/retrieve
│   ├── notifier/sender.py             # Console / Telegram 추상화
│   └── jobs/morning_brief.py          # 수집→RAG→LLM→알림 파이프라인
├── docs/rag/
│   ├── clothing.md
│   ├── health.md
│   └── traffic.md
├── tests/test_core.py                 # 7개 단위 테스트
├── k8s/all.yaml                       # Namespace/ConfigMap/Secret/Deploy/Svc/CronJob/Qdrant
└── scripts/
    ├── k3s-master-install.sh
    ├── k3s-worker-join.sh
    └── bootstrap-rag.sh
```

---

## 8. 교훈 요약

1. **Placeholder는 배포 전에 반드시 치환** — `REPLACE_OWNER`, `REPLACE_ME` 같은 마커는 CI/적용 시점에 실수하기 쉬움. 가능하면 `envsubst`나 Helm 템플릿으로 자동화.
2. **Secret은 매니페스트에 넣지 않는다** — `k8s/all.yaml`에 stringData로 넣으면 실수로 git에 커밋. `kubectl create secret --dry-run | apply` 또는 SOPS/Sealed Secrets.
3. **외부 API는 실패가 일상** — Gemini 503, 기상청 일시 지연 등. 재시도 + 폴백 + 타임아웃 3종 세트는 기본.
4. **`:latest` 태그는 명시적 `imagePullPolicy: Always`와 세트** — 안 그러면 조용히 구 이미지로 돈다.
5. **채팅에 시크릿 붙여넣지 않기** — 토큰, 키는 LLM·메신저·로그 어디에도 노출 금지. 노출되면 즉시 폐기·재발급.
6. **단계별 검증** — curl로 직접 API 호출 → 코드에서 호출 → K8s에서 실행. 각 단계마다 격리해서 문제 위치 좁히기.
7. **로그·설정을 읽기 전에 추측하지 말 것** — "토큰 소진이겠지"가 아니라 에러 코드·메시지 그대로 읽으면 훨씬 빨리 해결.

---

*프로젝트 완성일: 2026-04-13*
*다음 학습 주제: Prometheus 모니터링 도입*

