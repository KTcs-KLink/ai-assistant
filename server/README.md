# K:LINK Live RAG 시연 서버

기존 `web/` 화면에 맞춘 **실제 HTTP/SSE API**입니다. 관리자 계정으로 PDF를 업로드하면 텍스트 추출 → 조항 기반 청킹 → Dense 임베딩 → SQLite 벡터 저장을 진행합니다. 검색 시 코사인(정규화된 벡터 내적) Top 5를 OpenAI 모델에 전달해 응답을 토큰 단위로 SSE 전송하고, 문서명/조항/쪽을 표시합니다. 고정 답변을 반환하지 않습니다.

> **중요:** 단일 관리자용 개발·발표 시연입니다. KTcs SSO, 권한별 필터링, 운영용 멀티테넌시, Supabase pgvector, 완전 자동 변경 감지, OCR, MCP 검색 서버는 아직 연결되지 않았습니다. 조직의 사용 승인 없이 내부 자료를 업로드하거나 외부 LLM API로 전송하지 마세요. 공개 대체 자료는 KTcs의 현행 사규가 아닙니다.

## 실행

Python 3.11+ 환경을 권장합니다.

```bash
cd server
python -m venv .venv
# Windows: .venv\Scripts\activate / macOS·Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # Windows PowerShell: Copy-Item .env.example .env
# .env에 KLINK_DEMO_PASSWORD 및 OPENAI_API_KEY를 기입
uvicorn app:app --reload --port 8000
```

다른 터미널에서:

```bash
cd web
npm ci
cp .env.example .env
npm run dev
```

`http://localhost:5173`에서 `.env`의 시연 계정으로 로그인합니다. `/admin/documents`에서 **텍스트가 포함된 PDF**를 선택하고 해당 도메인으로 업로드합니다. 상태가 `ready`로 바뀌면 질문할 수 있습니다. 채팅에 PDF를 첨부하면 해당 대화용 PDF가 먼저 색인됩니다.

`GET http://localhost:8000/health`는 데이터/LLM 설정 여부를 반환합니다. `OPENAI_API_KEY`가 없으면 문서 색인 또는 생성 기능이 실패하는 것이 정상입니다. 이 상태를 모의 답변으로 숨기지 않습니다.

## 기존 knowledge-mcp 파싱 문서 가져오기

`knowledge-mcp/data/manifests/sources.csv`에 있는 문서 18건은 현재 재배포 허용 여부가 `unknown`으로 표시되어 있습니다. 승인된 문서에 대해서만 아래처럼 명시적으로 가져오세요. 미승인 문서는 임베딩/외부 LLM 전송을 하지 마세요.

```bash
cd server
python import_parsed.py --repo ../../knowledge-mcp --source SRC-0004 --collection hr --confirm-authorized
```

원래 파싱된 `parsing.md`에서 장/조 제목을 유지해 청킹하며 PDF 페이지 정보가 없다면 조항 경로만 출처로 표시합니다. `--source`를 반복하거나 허가된 전체 문서만 `--all`로 선택할 수 있습니다.

## 실제 사용 동작

- `POST /api/conversations/{id}/messages` → `text/event-stream`: `meta`(근거) → `delta`(실시간 토큰) → `done`.
- 관리 화면은 등록된 **실제** 문서·질문 수만 집계하며 부정적 답변 피드백은 검토·분류·처리할 수 있습니다. 조직/사용자 디렉터리·권한 제어는 미연동이며 가짜 데이터를 제공하지 않습니다.
- 문서별 400쪽, 20MB, 1,200청크 제한이 있습니다. 스캔 이미지 PDF의 OCR은 미지원입니다.
- 벡터는 SQLite에 저장하고 단일 서버에서 전수 코사인 비교합니다. 대규모 자료는 `knowledge-mcp`와 pgvector 검색 API로 교체해야 합니다.
- `KLINK_EMBED_PROVIDER=local`은 `requirements-local-embeddings.txt` 설치 후 `BAAI/bge-m3`를 사용합니다. OpenAI와 로컬 모델 간 전환 시 기존 문서를 **재색인**해야 합니다.
- `server/.data`에 PDF, 인덱스, 시연 대화가 저장됩니다. Git에 포함되지 않습니다.

## 보안 및 알려진 제약

**인터넷 공개 서버로 그대로 배포하지 마세요.** 시연용 단일 비밀번호·공용 문서 공간이며 운영용 RBAC/SSO, 업로드 악성코드 검사, rate limit, 사용자별 데이터 분리, 암호화/보존기간 정책이 없습니다. 로그인 쿠키는 HTTPOnly이며 HTTPS 배포에서는 `KLINK_SECURE_COOKIE=true`가 필요합니다.

답변 모델을 사용할 경우 관련 질문·근거 텍스트가 OpenAI API로 전달됩니다. '모든 데이터가 회사 서버에만 저장된다'고 안내하지 않습니다. 실제 KTcs 직원의 사용 전 정보보호 승인과 SSO/RLS가 필요합니다.

기존 Supabase 연결은 확인된 프로젝트가 비활성 상태이므로 **쓰기 작업을 하지 않았습니다**. 이 시연 서버는 Supabase를 사용하지 않습니다.


## Semantic Dense 검색 개선 및 실시간 진단 (2026-11-06)

일반 RAG 서버는 \`server/query_strategy.py\`의 보수적인 한국어 질의 정규화를 적용합니다. **원본 질문도 항상 함께 검색**하고, 지원하는 업무 표현은 한 번 더 Dense 임베딩해 각 후보 Top20을 RRF로 합칩니다. 현재 도메인 별칭은 정기 급여 지급일, 연차휴가, 출장비·여비, 사직, 근무시간, 채용의 일부 고신뢰 표현에 적용합니다. 나머지 질문도 원래 Dense 검색을 유지합니다.

- 정기 월급 지급일을 묻는 경우, 허용된 실제 색인 텍스트에 **'매월 NN일'과 급여/보수 지급 근거가 함께 명시**된 후보만 답변 모델에 넘깁니다. “성과연봉은 급여지급일에 준한다”는 문장만 있다면 날짜를 추론하지 않습니다. 지급일이 25일이라는 숫자를 코드에 고정하지 않았습니다.
- 일상적인 다른 질문은 별도 업무 조건을 보존한 짧은 의미 질의로 보완합니다. 임금 계산기간·성과연봉·퇴직금 날짜는 정기 급여일 의도로 자동 치환하지 않습니다.
- 범위가 다르거나 승인되지 않은 문서·없는 조항은 추가하지 않습니다. 검색 보조 재작성은 **답변의 인용 근거가 아닙니다.**
- 전체 의미 동치나 현행 규정 정확도를 보장하지 않으므로, 별도 회귀 테스트와 출처 검증이 필요합니다.

### 진단 API

시연용 로그인에 성공한 상태에서 브라우저 관리자 개요 탭의 **검색 디버그**에서 질문을 입력하세요. \`GET /api/admin/retrieval-debug?question=...\`이 실제 등록 문서/청크 수, 질의 확장 표현, 검색된 문서명/섹션/청크 ID/유사도를 반환합니다.

| 현상 | 먼저 확인할 곳 |
| --- | --- |
| indexedChunks = 0 | 서버에 승인된 문서가 적재되지 않았음 |
| indexedChunks > 0, matches = [] | 원문/승인 범위 누락, 모델 불일치, 검색 실패 |
| matches는 있는데 답변 불가 | LLM 근거 전달·검증 단계 |
| 모든 다른 질문도 급여일로 분류됨 | 질의 정규화 과잉 치환 회귀 테스트 |

**중요:** 이는 이 GitHub 브랜치의 **새 FastAPI 서버**를 수정한 것입니다. 원래 \`KTCS/chat/kepco_hr_demo_20261102/\`의 **8811번 앱**은 별개의 사용자 PC 로컬 코드라 자동 업데이트되지 않습니다. 예전 960문항 실험의 검색 코어(\`work/kepco_hr_contextual_20261102/app_core.py\`)도 이 GitHub 저장소에 없으므로 아직 직접 수정하지 못했습니다.

원본 PC 인덱스 상태를 확인하려면 사용자 PC에서 다음과 같이 읽기 전용 진단을 실행합니다.

\`\`\`powershell
cd "C:\Users\hjy10\OneDrive\문서\ChatGPT\KTCS\klink-demo-ui"
git fetch origin
git switch feat/live-rag-chat-20261106
py server/check_local_rag.py --root "C:\Users\hjy10\OneDrive\문서\ChatGPT\KTCS"
\`\`\`

\`check_local_rag.py\`는 기존 프로젝트 폴더/벡터 후보/8811 서버 응답만 확인하고, **키·원문·개인정보를 출력하거나 데이터/코드를 수정하지 않습니다.** 별도 960문항 로컬 서버의 실제 Top5 검색 추적은 원본 \`app_core.py\`의 API 구조를 확인한 뒤 연결해야 합니다.

회귀 테스트: \`python -m pytest server/tests -q\`. 외부 LLM API 없이 검색·의도 처리·부정확한 지급일 회피 여부를 검증합니다. 실제 BGE 모델과 원본 248개 승인 구간으로 동일한 질문을 재검증해야 운영 시연에 적용할 수 있습니다.
