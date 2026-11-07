# 인사 조건·예외 UI 검증 자료

이 폴더는 대안 포털의 후속 UI 연결 결과다. 이전 시안·연결 검사와 원래 채팅의 QA 파일은 덮어쓰지 않았다.

| 자료 | 의미 |
| --- | --- |
| [condition-cards-replay.json](condition-cards-replay.json) | 실제로 보존된 응답 3건/원문 카드 15개 재생, 변조 차단 3개, 합성 유니코드 TEST 1개. 총 7개 검사. 새 모델 생성 0회 |
| [ui-regression.json](ui-regression.json) | 기존 13개 검사와 42개 화면/폭 조합. 실제 BFF와 응답 가로채기 3개를 구분. 유료 모델 생성 0회 |
| [live-model-connection.json](live-model-connection.json) | 새 실제 질문 1건, 서버의 지정 모델 생성 2회, HTTP 200. 답변 1문단·출처 5개·조건 원문 2개. 독립 의미 검증 아님 |
| [live-interrupted-attempt.json](live-interrupted-attempt.json) | 앞선 개발 중 화면 자동 갱신으로 관측이 끊긴 시도. 시간초과 보존. 제공자 실행/완료 횟수 미확정 |
| [replay-screenshots.json](replay-screenshots.json) | 부분 답변의 기존 실제 응답 표시. 새 생성 0회 |

새 실제 응답의 [PC 전체 화면](hr-quality-portal-live-desktop.png)과 [모바일 전체 화면](hr-quality-portal-live-mobile.png)을 보존했다. 부분 답변의 조건 원문은 [PC](hr-condition-cards-inline-1440.png)·[390px 모바일](hr-condition-cards-inline-390.png) 화면에서 볼 수 있다. 뒤의 두 화면은 기존 응답 재생이며 새 실제 생성으로 집계하지 않는다.

새 실제 응답의 조건 원문만 읽기 쉽게 맞춘 [PC 화면](hr-quality-portal-live-viewport-1440.png)·[390px 모바일 화면](hr-quality-portal-live-viewport-390.png)도 있다. 이는 위 응답을 스크롤한 화면이며 추가 생성은 없다.

원래 QA 응답은 상위 KTCS 작업 폴더의 `outputs/klink_hr_answer_quality_20261107/final-display-replay/answers`에서 읽기만 했다. API 원문 복사본 전체나 테스트용 합성 응답을 이 폴더에 회사 승인 자료처럼 게시하지 않았다.

실제 자료는 한국전력 공개 대체자료다. 이 검증은 전체 인사 답변 의미 평가·KTcs 적용/현행성·사람 승인·실제 SSO·정식 양식·신청/결재·운영 준비 완료를 뜻하지 않는다. 클라우드 적재/연결 재검사는 보류했다.

구현·실행·한계는 [후속 연결 기록](../hr-condition-ui-20261107.md)을 참조한다.
