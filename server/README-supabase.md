# K:LINK — Supabase pgvector PoC 연결

> **상태:** 연결 코드가 준비된 작업 브랜치. 아직 Supabase 새 프로젝트 생성,
> 실제 DB 적재, 원격 검색과 프론트엔드 통합 테스트가 완료되었다는 뜻이 아닙니다.

## 데이터와 목적

기존 `KTCS_RAG_Lab_2026-11-02.zip`에 있는 한국전력 공개 규정 기반 PoC
18건/1,933청크와 사전 계산된 **BGE-m3-ko 1024차원 정규화 벡터(body/path)**를
재사용합니다. KTcs 현행 인사규정이나 직원 개인정보가 아닙니다.
원본 자료의 재배포·외부 저장·사용조건 및 저장 지역 승인은 운영 전 확인해야 합니다.

원본 모델: `dragonkue/BGE-m3-ko`, revision
`7074d66aa46562342193ca4feb3d89bf9dad71b4`,
CLS / CPU BF16 / normalized FP32 / max 768 tokens.

## 1. 새 Supabase 프로젝트 생성

승인된 조직에서 한국 리전 `ap-northeast-2`(Seoul)으로 프로젝트를 만들고
Database 비밀번호와 연결 URI를 비밀 저장소에 보관합니다.
프로젝트 생성 비용은 Supabase의 비용 확인 단계를 따릅니다.

Supabase SQL Editor 또는 승인된 관리용 SQL 작업에서
`server/sql/pgvector_schema.sql`을 적용합니다.

스키마: `klink_rag_documents`, `klink_rag_chunks`,
`extensions.vector(1024)` 두 개, 출처 메타데이터, RLS 및
`anon`/`authenticated` 접근 차단. **브라우저에서 직접 SQL 조회하지 않습니다.**

> 실제 기업용 서비스는 회사 SSO/권한 매핑/문서별 ACL이 먼저 필요합니다.
> 이 브랜치는 단일 관리자 로컬 PoC이며 인터넷에 그대로 공개하지 않습니다.

## 2. 검증한 데이터를 적재하기

Python 3.12 권장. 프로젝트 저장소 루트에서:

```bash
python -m pip install -r server/requirements-supabase.txt
python server/import_lab_to_supabase.py \
  --zip "/absolute/path/to/KTCS_RAG_Lab_2026-11-02.zip"
```

기본 동작은 **읽기 전용 체크**입니다. SHA-256, source/chunk 개수, 모델
리비전, 정규화된 embedding shape/dtype 검사 후 종료하며 DB를 수정하지 않습니다.

다음은 비밀 연결 URI가 **현재 서버 셸의 환경 변수**에만 안전하게 제공된
상태에서 실행합니다. URI 자체를 Git/로그/사용자 화면에 출력하지 마세요.

```bash
python server/import_lab_to_supabase.py \
  --zip "/absolute/path/to/KTCS_RAG_Lab_2026-11-02.zip" --apply
```

`--apply`는 `KLINK_PG_DSN`이 설정되어야 실행됩니다.
source_id/chunk_id 기준 재실행 안전 upsert를 사용하며, DB에서 1,933개 청크
및 18개 source를 확인한 뒤 성공을 출력합니다. 실패 시 롤백합니다.

SQL Editor에서 점검:

```sql
select count(*) as documents from public.klink_rag_documents;
select count(*) as chunks, count(distinct source_id) as sources
from public.klink_rag_chunks;
select source_id, title, domain from public.klink_rag_documents
order by source_id;
select chunk_id, content from public.klink_rag_chunks
where content like '%매월25일%' limit 5;
```

마지막 SQL은 원본 문장에 단위 공백이 없을 경우에만 일치합니다.
조회 문서의 제목/조항/적용 대상은 출처로 재확인하세요.

## 3. FastAPI 및 React 연결

`server/.env` 로컬 파일에 다음을 설정합니다. 실제 키를 Git에 업로드하면 안 됩니다.

```dotenv
KLINK_RAG_BACKEND=supabase
KLINK_PG_DSN=postgresql://<backend-user>:<password>@<db-or-pooler-host>:5432/postgres?sslmode=require
KLINK_DEMO_USER=klink
KLINK_DEMO_PASSWORD=<strong-local-demo-password>
OPENAI_API_KEY=<optional-model-key>
KLINK_BGE_MODEL_DIR=
```

`KLINK_PG_DSN`은 **서버 전용**입니다. `VITE_` 환경변수,
React 소스, 로컬 스토리지, GitHub Actions 로그에 넣지 않습니다.
모델 디렉터리가 제공되면 고정 리비전/파일 checksum을 별도로 대조하세요.

```bash
cd server
uvicorn app:app --port 8000
```

별도 터미널:

```bash
cd web
# web/.env: VITE_API_BASE_URL=http://localhost:8000, VITE_USE_MOCK=false
npm ci && npm run dev
```

브라우저의 `http://localhost:5173`은 기존 UI와 실제 FastAPI SSE 계약을
그대로 사용합니다. 웹 화면은 Supabase에 직접 접속하지 않습니다.
검색은 Supabase의 path-vector 코사인 Top20 → 보수적 의미 확장/재순위
→ Top5 → 근거 기반 생성/응답입니다. 금액·지급일은 근거 없이 추정하지 않습니다.

## 4. 검증 순서

1. `GET /health`에 `supabaseConnected: true`,
   `indexedDocuments: 18`, `indexedChunks: 1933`인지 확인합니다.
2. 데모 계정으로 로그인하고 `GET /api/admin/retrieval-debug?question=...`에서
   실제 출처 `chunkId/document/section/score`를 확인합니다.
3. 실제 프론트엔드에서 `급여일이 언제야?`,
   `월급 매달 며칠 들어와?`, `보수 지급일 알려줘` 등 의미 동치 질의와
   `성과연봉 지급일`, `퇴직급여 지급일` 같은 대비 질의를 검증합니다.
4. 검색된 출처 문장과 답변의 날짜·조건·적용대상을 원문으로 대조합니다.
5. `python -m pytest server/tests -q`, `npm run build --prefix web`
   결과를 확인한 뒤에만 연결 완료라고 판단합니다.

### 제약

- Supabase DB 접근은 별도 서버 관리 자격증명 방식이라 기업용 세부 ACL
  / KTcs 직원 본인 전용 접근 정책이 구현되지 않았습니다.
- 관리자 PDF 추가 업로드/대화 첨부는 기존 SQLite 인덱스에 저장됩니다.
  **새 PDF의 Supabase 자동 적재/변경 감지/증분 재색인은 후속 작업**입니다.
- ZIP에 포함된 사전 계산 벡터만 재사용합니다. 검색 질의 임베딩에는
  정확히 일치하는 BGE-m3-ko 모델 가중치가 런타임에 필요합니다.
- 예전 8811번 로컬 앱은 별도 프로젝트이므로 이 브랜치가 자동으로
  수정하거나 재시작하지 않습니다.
- 이 PoC의 출처 URL은 자료별 상세 문서 링크가 아닌 공개 규정 게시판이며,
  출처 파일/조항/스냅샷 커밋으로 원문을 추적합니다.
