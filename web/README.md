# K-LINK 웹 (프론트엔드)

사내 AI 어시스턴트 K-LINK의 React 구현. 

- Vite + React 19 + TypeScript, Tailwind CSS v4, TanStack Query v5, React Router v7, lucide-react

## 실행

```bash
npm install
npm run dev        # http://localhost:5173
npm run build      # 타입 검사 + 프로덕션 빌드
```

실제 RAG API(`http://localhost:8000`)가 **기본 동작**입니다. `server/README.md`에 따라 FastAPI를 먼저 실행하고 `web/.env.example`을 복사하세요. **예시 데이터 모드**는 `VITE_USE_MOCK=true`를 명시했을 때에만 활성화됩니다.
**목 모드에서만 사용할 수 있는 가상 계정:** 관리자 `klink123`(김지현, 경영지원팀), 일반 사용자 `klink`(박서준, 영업1팀). 비밀번호는 둘 다 `VITE_MOCK_PASSWORD`(기본값 `klink1234`)입니다. `.env.example`을 참고하세요.

## 라우트

| 경로 | 화면 |
|---|---|
| `/login` | 4a 로그인 (아이디/비밀번호) |
| `/` | 5a 새 대화 |
| `/c/:id` | 3a 채팅 + 출처 패널 / 6a 첨부 파일 요약 |
| `/admin` | 4b 개요 |
| `/admin/documents` | 5b 문서 관리 |
| `/admin/users` | 5c 사용자·권한 |
| `/admin/feedback` | 6b 답변 피드백 |
| `/admin/settings` | 7a 설정 |

`/admin/*`과 사이드바의 "관리자" 링크는 `role: 'admin'`인 사용자에게만 보입니다.

## 구조

```
src/
  api/
    types.ts       도메인 타입 (Message, Citation, StreamEvent …)
    client.ts      실제 FastAPI 호출 + SSE 파서. VITE_USE_MOCK=true면 목 사용
    mock.ts        인메모리 목 API
    answers.ts     목 모드에서 쓰는 질문별 답변
  auth/            AuthContext (/api/auth/me, /api/auth/login)
  chat/
    ChatProvider   답변 스트리밍 상태 (보내기 / 중지 / 다시 생성)
    Composer       입력창 (첨부 칩, 음성 입력 모드, 보내기·중지)
    MessageContent 본문 렌더링 (**굵게**, [[인용]] 마커 → <sup>)
    SourcePanel    출처 패널 (사내 문서 카드 / 첨부 파일 쪽 보기)
    useVoiceInput  음성 입력 (경과 시간, 실시간 받아쓰기)
  admin/           관리자 화면
  components/ui    Button, Toggle, Checkbox, Badge, Chip …
  index.css        디자인 토큰 (@theme)
```

## 백엔드 연동 메모 (FastAPI)

`src/api/client.ts`의 엔드포인트와 아래 SSE 규격은 `server/app.py`에 실제로 구현되어 있습니다. 백엔드를 다른 서비스로 교체하면 규격과 자동 테스트를 함께 갱신하세요.

- 인증: 쿠키 세션 기준(`credentials: 'include'`). `GET /api/auth/me`가 401을 주면 로그인 화면으로 보내고,
  로그인 폼은 `POST /api/auth/login` (`{"username","password"}`)을 보내 시연용 HTTPOnly 세션 쿠키와 `User`를 받습니다. 틀리면 401.
- 답변 스트리밍: `POST /api/conversations/{id}/messages`가 `text/event-stream`으로 아래 이벤트를 보낸다고 구현되어 있습니다.
  ```
  data: {"type":"meta","searchNote":"문서 3건에서 검색함","citations":[...]}
  data: {"type":"delta","text":"네, 미사용"}
  data: {"type":"done","messageId":"..."}
  ```
  POST 본문을 보내야 하므로 `EventSource`는 쓰지 않고 `fetch` 스트림으로 직접 파싱합니다. [■ 중지]를 누르면 요청이 취소(abort)됩니다.
- 본문 형식: `**굵게**`, 인용 위치는 `[[citationId]]`, 문단은 빈 줄로 구분합니다.
  사내 문서 인용문 `quote`에서 강조할 부분은 `[ ]`로 감쌉니다. 첨부 파일 인용은 `context`(해당 쪽 문단) 안에서 `quote`와 같은 부분을 강조합니다.
- 첨부 파일은 `POST /api/attachments`로 PDF만 업로드하고 id만 메시지에 실어 보냅니다. 일반 사내지식 컬렉션으로 저장하지 않으며, 단일 시연계정 전용 파일로 로컬 서버에 임시 보관됩니다.

## 남은 일

- **음성 입력**: Chrome의 Web Speech API는 음성을 Google 서버로 보냅니다. "외부로 전송되지 않습니다"라는 안내와 맞지 않으므로,
  운영 전에 사내 STT로 바꿔야 합니다(`useVoiceInput.ts`의 TODO 참고). 목 모드에서는 받아쓰기를 흉내만 냅니다.
- 로고는 자리표시(틸 네모)입니다. `components/ui.tsx`의 `Logo`를 교체하세요.
- 사용자 목록 / 관리자 탭의 역할 변경, 문서 삭제·권한 수정 UI는 시안에 없어서 만들지 않았습니다.
