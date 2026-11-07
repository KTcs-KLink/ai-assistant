# K:LINK 최신 인사 서버 UI 연결

기준일: 2026-11-07. 브랜치: `feat/uiux-alternative-20261107`.

대안 포털을 원래 인사 개발 채팅의 최신 8842 API에 연결했다. BGE와 단어를 결합한 검색 결과를 표시하고, 앱이 선택된 원문 구간에서 복원한 인용임을 구분한다. 기존 조건·예외 원문과 검토 필요 상태도 유지한다.

연결 계약은 전달받은 `feat/hr-quality-closeout-20261107`의 커밋 `558b600b98ab982910699c9f77453a944dae82cd`와 비교했다. 백엔드 변경을 이 clone에 병합하지 않았으며, 이전 로컬 벡터 구현과 8824 시안도 보존했다.

## 연결과 실행

| 주소 | 역할 |
| --- | --- |
| `http://127.0.0.1:8825/hr/assistant` | 최신 API를 사용하는 대안 포털 |
| `http://127.0.0.1:8842/hr-check` | 원래 채팅이 관리하는 최신 인사 서버 |
| `http://127.0.0.1:8824/workspace` | 보존된 디자인 시안 |

`start_hr_portal.cmd`는 먼저 8842의 `quality_version=hr-quality-closeout-20261107`, `retrieval_mode=hybrid`를 확인한 뒤 UI를 시작한다. 이 실행기는 공유 백엔드를 새로 시작하거나 교체하지 않는다. 해당 서버가 꺼져 있으면 원래 인사 개발 실행기로 시작하도록 안내한다.

개발 프록시는 `/api/benefits`만 8842로 전달한다. 브라우저에는 제공자 키·JWT·Authorization 헤더를 만들지 않으며 `/config`의 클라우드 저장소 점검도 요청하지 않는다.

## 원문 인용과 검색 표시

`quote_method=APPLICATION_RECONSTRUCTED_ORIGINAL_SPANS_NO_GENERATED_QUOTES`인 응답에는 ‘인용문은 선택된 원문 구간에서 그대로 복원했습니다’라고 표시한다. 생성 본문의 인용 ID와 원문의 연속 문자열, 조건 원문의 코드 포인트 위치와 UTF-8 SHA를 확인하고, 조회된 한전 원문 전체의 회사·본문 해시도 대조한다. 최신 hybrid 응답에서 알 수 없는 인용 방식이나 변조된 본문은 표시하지 않는다.

`retrieval.method=hr_bge_m3_hybrid`는 서버가 반환한 실제 조문 목록과 함께 표시한다. 최신 응답에 개별 임베딩 검색 창 ID·점수·질문 벡터 재사용 여부가 없으므로 해당 값을 UI에서 만들지 않는다. 연결 안내도 모델의 순간 준비 완료로 승격하지 않고 ‘서버에 설정된 검색 경로’로 표현한다. 실제 조문 전체를 펼쳐 읽고 답변의 인용과 조건·예외 원문을 함께 확인할 수 있다.

본문을 전부 보류한 응답은 생성문을 숨기고 검토 항목과 원문 열기를 제공한다. 부분 답변 플래그가 있으면 서버의 상태 값이 `answered`여도 클라이언트에서 `needs_review`를 유지한다. 기존 로컬 dense 응답 형식의 검사는 호환을 위해 보존했다.

현재 자료는 한국전력 공개 대체자료 10문서·449개 조문이며 사람 승인 0개다. KTcs 적용·현행성·실직원 자격은 확인 전이고, 공식 양식·SSO·실제 신청/결재도 기존 상태를 유지한다. 혜택의 가상 카탈로그 전환은 이번 UI 연결 범위에 포함하지 않았다. Supabase 연결 재검증·적재·SQL 적용은 계속 HOLD다.

## 이번 UI 검사

결과와 화면은 [검증 자료](hr-closeout-ui-20261107/README.md)에 보존했다.

- 최신 API로 실제 질문 1건을 전송해 HTTP 200, 답변 1문단·조회 원문 5개·조건 원문 3개를 확인했다. 지정 모델의 초안/원문 대조 생성은 2회였다. 원문 구간 복원 표시와 반환 인용/조건의 원문 일치도 확인했다.
- 실제 응답을 1440/768/390/360px에서 확인했다. 가로 넘침·브라우저 오류·브라우저 Authorization 헤더·직원 필드 자동 첨부·클라우드 상태 요청은 없었다.
- 보존 응답 재생과 변조 검사 6개가 통과했다. 실제 새 응답 재생, 원래 백엔드 최종 `03-041` 보류 응답, 합성 부분 답변 플래그, 인용 방식·인용문·원문 SHA 변조를 구분했다. 새 모델 생성은 0회다.
- 기존 UI 검사 13개와 42개 화면/폭 조합이 통과했다. 그중 3개 실패/보류 상태는 응답 가로채기로 확인했다. TypeScript를 포함한 프론트 빌드도 통과했다.
- 백엔드·Supabase 파일 및 기존 시안 소스가 이 단계의 시작 커밋 `0bdf5a0`와 동일함을 Git으로 대조했다. 원래 체크아웃과 기존 서비스는 수정·종료하지 않았다.

이 결과는 UI·전송·출처 표시 검사다. 원래 채팅의 126개 검사나 검색/답변 평가를 이 작업에서 다시 실행한 것으로 합산하지 않았다. 같은 모델의 원문 대조도 독립 사람 승인이나 전체 답변 정확도 보증이 아니다.

Codex는 계약 비교·UI 연결·클라이언트 검사·브라우저 확인을 담당했다. 기존 백엔드 코드는 한전 자료 범위·검색·원문 복원·토큰/인용 검사를 수행했고, 지정 GPT는 실제 질문의 초안과 원문 대조를 수행했다.

## 재현

```powershell
python scripts/check_hr_closeout_service.py
npm.cmd run dev:hr --prefix web
python scripts/prepare_hr_closeout_ui_replay.py
npx.cmd --yes --package @playwright/cli playwright-cli --session klink-hr-closeout-regression run-code --filename=output/playwright/verify_hr_closeout_ui_replay.generated.js
```

재생 준비에는 이 작업의 보존된 실제 응답과 부모 KTCS 작업 폴더의 최종 보류 응답이 필요하다. 기존 파일은 읽기만 하고 별도 무시된 `output/playwright` 파일을 만든다. `scripts/verify_hr_closeout_portal.js`는 실제 질문을 전송하므로 유료 생성이 발생한다.

백엔드 기준: [답변 개선 기록](https://github.com/KTcs-KLink/ai-assistant/blob/558b600b98ab982910699c9f77453a944dae82cd/docs/hr-quality-closeout-20261107.md), [한전 데이터 구성](https://github.com/KTcs-KLink/ai-assistant/blob/558b600b98ab982910699c9f77453a944dae82cd/docs/hr-data-map-20261107.md).
