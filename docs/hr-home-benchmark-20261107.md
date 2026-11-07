# 직원 포털 홈 벤치마킹 적용

기준일: 2026-11-07. 브랜치: `feat/hr-home-benchmark-20261107`. 시작 커밋: `4abd6f634cc9955b2db7b8aa64b1def616919e5a`.

홈의 첫 행동을 AI 질문과 준비 중인 업무로 정했다. 기존의 예시 혜택 중심 배치를 바꾸고, 실제 연결된 한전 참고 원문과 계정의 준비 목록으로 진입하게 했다. K:LINK의 네이비·살구색과 PC/모바일 내비게이션은 유지했다.

## 참고한 공개 자료와 적용 판단

공개 제품 문서와 화면의 정보 구조를 참고한 설계 판단이다. 사용 시간 단축이나 만족도 개선을 측정한 결과는 아니다.

| 참고 사례 | 확인한 구조 | K:LINK에 적용한 내용 |
| --- | --- | --- |
| [Workday Home Page Workspace](https://stage.doc.workday.com/admin-guide/en-us/manage-workday/user-experience/people-experience/home-page/vqj1631827139545.html) | 홈의 My Tasks, Top Apps, Quick Tasks 및 추천 카드 구성 | 상단에 내 준비 목록, 그 아래 업무 바로가기 배치. 준비 목록은 서버의 실제 개수·진행 상태를 사용 |
| [Microsoft SharePoint app in Teams — 기존 Viva Connections](https://learn.microsoft.com/en-us/viva/connections/viva-connections-overview) | 대시보드, 자료 링크, 공지와 뉴스의 구분, PC·모바일 접근 | 업무 바로가기와 원문 찾기를 분리하고 모바일에서는 한 열로 정렬. 연결된 공지 데이터가 없어 공지·뉴스는 생성하지 않음 |
| [ServiceNow HR Service Delivery 공개 웨비나](https://www.servicenow.com/community/s/cgfwn76974/attachments/cgfwn76974/hr-service-delivery-events/180/1/LiveonServiceNow_Webinar_GetStartedHRSD_FINAL.pdf#page=23) | Employee Center의 통합 서비스 진입, 주제별 탐색, 작업·정보 접근 통합 | 첫 화면의 질문 작성, 휴가·급여·증빙 주제 진입, 준비 목록을 한 화면에 연결 |

## 바뀐 홈 구성

1. 오늘 날짜와 업무 시작 안내. 날짜는 한국 시간으로 표시한다.
2. AI 질문 작성과 내 준비 목록. 직접 입력한 질문은 AI 도우미 작성창으로 전달하며, 사용자가 전송하기 전에는 답변 요청을 보내지 않는다.
3. 휴가·근태, 급여·수당, 양식·증빙, 내 조건·동의의 네 가지 바로가기.
4. 업무별 질문 세 가지와 원문 직접 찾기. 이용 통계가 없어 ‘인기 질문’이나 순위로 표현하지 않았다.
5. 한전 원문 수와 연결 범위. 조문·문서 수는 서버 응답을 사용하고 KTcs 적용·현행성, 공식 양식, SSO의 한계를 함께 표시한다.
6. 예시 맞춤 혜택과 변경·마감 설정. 예시 금액·조건 충족 건수를 홈의 주요 성과 지표로 표시하지 않는다. 기존 화면 내 알림 동의 설정은 유지했다.

준비 목록은 현재 계정의 서버 값으로 표시한다. 목록 조회에 실패하면 ‘—’와 조회 실패 안내를 보여주며 0건으로 바꾸지 않는다. 목록의 진행 항목과 조건 재확인이 필요한 항목도 구분한다. 혜택 조회 실패가 독립적인 AI 질문 진입을 막지 않도록 했다.

질문 이어쓰기는 URL에 질문을 넣지 않고 화면 이동 상태로 전달한 후 그 상태를 지운다. 자동 전송·저장이나 GPT 호출을 추가하지 않았다. 입력 한도는 기존 도우미와 같은 500자다.

## 보존과 연결 범위

| 주소 | 내용 |
| --- | --- |
| `http://127.0.0.1:8825/hr` | 새 홈 |
| `http://127.0.0.1:8825/hr/home-previous` | 이전 연결 홈, 기존 `HrDashboard` 구현 보존 |
| `http://127.0.0.1:8825/hr/assistant` | 기존 실제 원문 기반 AI 도우미 |
| `http://127.0.0.1:8824/workspace` | 보존된 디자인 시안 |

원래 백엔드와 다른 체크아웃, 데이터·임베딩 색인, Supabase, 기존 `HrPages.tsx`·`portal`·`workspace` 시안은 수정하지 않았다. Supabase 연결 재검증·적재·SQL 적용은 HOLD다. 이 작업은 홈과 질문 이어쓰기 연결을 담당하며 KTcs 규정 승인·실직원 인증·공식 신청 연결을 추가한 것은 아니다.

## 확인 결과

[검증 자료](hr-home-benchmark-20261107/verification.json), [PC 화면](hr-home-benchmark-20261107/home-1440.png), [모바일 화면](hr-home-benchmark-20261107/home-390.png), [이전 홈 화면](hr-home-benchmark-20261107/previous-home-1440.png)을 보존했다.

브라우저 검사 8개가 통과했다. 실제 로컬 서버의 원문/준비 목록 수, 질문 이어쓰기, 세 가지 질문 진입, 원문/양식 바로가기, 합성 준비 목록·조회 실패 상태, 여섯 화면 폭, 이전 홈 접근을 구분해 기록했다. 1920/1440/1024/768/390/360px에서 가로 넘침과 브라우저 오류가 없었다. 준비 항목과 503 실패 상태는 별도로 표시한 합성 응답 검사다. 홈 검사에서는 답변 전송을 차단했으며 의도하지 않은 모델 요청은 0건이었다. 전체 RAG 성능이나 답변 의미 평가를 다시 수행하지 않았다.

TypeScript를 포함한 프론트 빌드를 확인했다. Codex가 화면 구현·자료 대조·브라우저 검사를 맡았고, 앱 코드는 기존 API 값을 표시하며 질문을 전달한다. 기존 GPT 답변 경로와 지정 모델은 변경하지 않았다.

재현: `npm.cmd run build --prefix web`, 실행 중인 로컬 서비스에서 `scripts/verify_hr_home.js`를 Playwright CLI의 `run-code --filename`으로 실행한다. 이 검사는 새 답변 모델 호출을 하지 않는다.
