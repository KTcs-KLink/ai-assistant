import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  ChevronRight,
  Columns2,
  ListTree,
  Monitor,
  PanelLeft,
  Search,
  ShieldCheck,
  Smartphone,
  Sparkles,
} from "lucide-react";
import "./wireframes.css";

type Role = "employee" | "admin";
type Kind =
  | "home"
  | "chat"
  | "library"
  | "requests"
  | "account"
  | "status"
  | "dashboard"
  | "sources"
  | "jobs"
  | "reviews"
  | "usage"
  | "cases"
  | "settings"
  | "audit";
interface Screen {
  id: string;
  role: Role;
  title: string;
  path: string;
  kind: Kind;
  summary: string;
  regions: { label: string; description: string }[];
}
const SCREENS: Screen[] = [
  {
    id: "E01",
    role: "employee",
    title: "업무 홈",
    path: "/hr",
    kind: "home",
    summary: "질문과 필요한 업무를 바로 시작하는 개인 업무의 진입점",
    regions: [
      {
        label: "빠른 질문",
        description: "질문을 작성하고 AI 도우미에서 확인 후 전송",
      },
      {
        label: "내 문의",
        description: "본인 문의의 처리 상태와 답변 확인",
      },
      {
        label: "자주 찾는 규정",
        description: "규정 원문·공식 양식·문의 등록으로 빠르게 이동",
      },
    ],
  },
  {
    id: "E02",
    role: "employee",
    title: "AI 업무 도우미",
    path: "/hr/assistant",
    kind: "chat",
    summary: "실제 질문·답변·인용 원문을 한 흐름으로 확인",
    regions: [
      {
        label: "질문·답변",
        description: "대화 본문과 인용 번호를 구분해서 표시",
      },
      {
        label: "근거 원문",
        description: "PC는 옆 패널, 좁은 화면은 대화상자로 원문·출처·버전 확인",
      },
      {
        label: "하단 작성창",
        description: "전송·수신 중지·현재 질문 목록·출처 포함 복사",
      },
    ],
  },
  {
    id: "E03",
    role: "employee",
    title: "규정·양식",
    path: "/hr/library",
    kind: "library",
    summary: "답변용 원문·검토 발췌·공식 양식의 상태를 구분",
    regions: [
      {
        label: "검색·탭",
        description: "답변용 검색, 회사 양식, 검토 전용을 분리",
      },
      {
        label: "결과 목록",
        description: "문서명·조문·적용 범위를 확인하고 원문 열기",
      },
      {
        label: "출처 상세",
        description: "본문·버전·사람 승인·KTcs 적용 상태 표시",
      },
    ],
  },
  {
    id: "E04",
    role: "employee",
    title: "내 문의",
    path: "/hr/requests",
    kind: "requests",
    summary: "본인의 일반 문의를 등록하고 처리 안내를 확인",
    regions: [
      { label: "문의 상태", description: "접수·확인 중·추가 확인·완료별 목록" },
      {
        label: "문의 작성",
        description: "분야·제목·내용을 등록하며 민감 정보는 차단",
      },
      {
        label: "처리 내역",
        description: "담당자의 안내·시각·상태와 취소 기능",
      },
    ],
  },
  {
    id: "E05",
    role: "employee",
    title: "내 계정",
    path: "/hr/profile",
    kind: "account",
    summary: "접속 정보와 데이터 보관 범위를 확인",
    regions: [
      {
        label: "접속 정보",
        description: "예시 접속과 실제 회사 계정·SSO를 구분",
      },
      {
        label: "정보 보관",
        description: "대화·문의·사용량 기록의 보관 범위 안내",
      },
      {
        label: "연결 상태",
        description: "추가 개인 조건 입력 없이 회사 연결 상태 확인",
      },
    ],
  },
  {
    id: "E06",
    role: "employee",
    title: "연결·적용 상태",
    path: "/hr/status",
    kind: "status",
    summary: "기능 연결과 회사의 규정 적용·운영 승인을 구분",
    regions: [
      { label: "기능 연결", description: "현재 서비스와 원문 사용 범위" },
      {
        label: "확인 항목",
        description: "조직 인증·공식 양식·실제 신청의 연결 여부",
      },
      {
        label: "자료 범위",
        description: "한전 참고자료와 KTcs 적용 미확인 표시",
      },
    ],
  },
  {
    id: "A01",
    role: "admin",
    title: "운영 현황",
    path: "/hr/admin",
    kind: "dashboard",
    summary: "인사·데이터·AI 운영의 현재 상태를 모아 확인",
    regions: [
      {
        label: "데이터 작업",
        description: "실행 중·완료·실패 작업과 최신 버전 결과",
      },
      {
        label: "연결 진단",
        description: "기존 AI 서비스·저장소·원문 무결성 진단",
      },
      {
        label: "최근 문의·처리할 업무",
        description: "진행 중인 직원 문의와 처리할 인사 업무",
      },
    ],
  },
  {
    id: "A02",
    role: "admin",
    title: "원문·데이터",
    path: "/hr/admin/sources",
    kind: "sources",
    summary: "문서를 찾고 선택한 자료만 재수집·검사·재적재",
    regions: [
      {
        label: "검색·필터",
        description: "문서명, 답변용 조문 포함 여부와 검토 전용 구분",
      },
      {
        label: "선택 작업",
        description: "선택 문서에 정합성 검사·공식 원문 재수집·스테이징 실행",
      },
      {
        label: "출처 상세",
        description: "실제 본문 발췌·해시·버전·답변 사용 범위",
      },
    ],
  },
  {
    id: "A03",
    role: "admin",
    title: "수집·재적재 작업",
    path: "/hr/admin/jobs",
    kind: "jobs",
    summary: "실행 상태·새 버전·실패 원인과 재시도를 관리",
    regions: [
      {
        label: "작업 큐",
        description: "대기·실행·완료·실패 상태와 실제 진행률",
      },
      {
        label: "작업 제어",
        description: "중지 요청, 실패·중단 작업의 새 버전 재시도",
      },
      {
        label: "결과 보고서",
        description: "답변/검토 색인 분리 결과와 파일·색인 해시 다운로드",
      },
    ],
  },
  {
    id: "A04",
    role: "admin",
    title: "원문 검토",
    path: "/hr/admin/reviews",
    kind: "reviews",
    summary: "미확인 원문의 검토 상태와 남은 사유를 기록",
    regions: [
      {
        label: "검토 대상",
        description: "검토 구간이 포함된 문서와 보류 상태",
      },
      {
        label: "검토 기록",
        description: "확인 내용·담당 기록·시각·수정 충돌 확인",
      },
      {
        label: "사용 경계",
        description:
          "기록 완료를 답변 사용 승인이나 조직 승인으로 전환하지 않음",
      },
    ],
  },
  {
    id: "A05",
    role: "admin",
    title: "토큰·비용",
    path: "/hr/admin/usage",
    kind: "usage",
    summary: "실제 모델 사용량과 단가 기준 추정 비용을 분석",
    regions: [
      {
        label: "기간별 집계",
        description: "요청·모델 호출·입력·캐시·출력과 미집계 구분",
      },
      {
        label: "예산·차단 정책",
        description: "설정 예산·관찰 또는 차단 정책과 미집계 비용 확인",
      },
      {
        label: "호출 상세",
        description: "질문 의미 확인·초안·원문 대조의 단계별 실제 사용량",
      },
    ],
  },
  {
    id: "A06",
    role: "admin",
    title: "직원 문의",
    path: "/hr/admin/cases",
    kind: "cases",
    summary: "직원 문의의 내용·상태·처리 안내를 한 곳에서 관리",
    regions: [
      {
        label: "문의 큐",
        description: "분야·문의 번호·상태로 검색하고 우선 확인",
      },
      { label: "처리 패널", description: "문의 내용과 현재 상태를 함께 표시" },
      {
        label: "처리 안내",
        description: "담당 안내와 상태 저장·동시 수정 검사",
      },
    ],
  },
  {
    id: "A07",
    role: "admin",
    title: "예산·권한·연결",
    path: "/hr/admin/settings",
    kind: "settings",
    summary: "AI 이용 정책·단가·접근 권한과 연결 범위를 관리",
    regions: [
      {
        label: "서비스 정책",
        description: "월 예산·일일 한도·점검 모드·다음 요청 차단",
      },
      {
        label: "단가 버전",
        description: "공식 참고/관리자 입력 구분과 이후 호출부터 적용",
      },
      {
        label: "권한·연결",
        description: "역할별 실행 권한과 SSO·적재·청구 연결 상태",
      },
    ],
  },
  {
    id: "A08",
    role: "admin",
    title: "변경 이력",
    path: "/hr/admin/audit",
    kind: "audit",
    summary: "실행 주체·시각·대상·변경 값을 추적",
    regions: [
      { label: "활동 검색", description: "작업·담당자·대상 ID별 이력 조회" },
      {
        label: "변경 기록",
        description: "수집·검토·문의·예산·단가 변경과 실행 결과",
      },
      {
        label: "상세 내역",
        description: "기록된 변경 값 확인·화면에서 수정/삭제하지 않음",
      },
    ],
  },
];

export default function HrWireframes() {
  useEffect(() => {
    document.title = "K:LINK · 화면 구성·와이어프레임";
  }, []);
  const [role, setRole] = useState<Role>("employee"),
    [screenId, setScreenId] = useState("E01"),
    [device, setDevice] = useState<"desktop" | "mobile">("desktop"),
    [view, setView] = useState<"wireframe" | "map">("wireframe");
  const screen = SCREENS.find((item) => item.id === screenId) ?? SCREENS[0],
    screens = SCREENS.filter((item) => item.role === role);
  function choose(item: Screen) {
    setRole(item.role);
    setScreenId(item.id);
    setView("wireframe");
  }
  function changeRole(value: Role) {
    setRole(value);
    setScreenId(value === "employee" ? "E01" : "A01");
  }
  return (
    <div className="wf-page">
      <header className="wf-top">
        <Link to="/hr">
          <ArrowLeft size={15} />
          직원 화면으로
        </Link>
        <div>
          <span className="wf-mark" />
          K:LINK <span>SCREEN PLANNING</span>
        </div>
        <Link to="/hr/admin">
          관리자 콘솔
          <ArrowRight size={15} />
        </Link>
      </header>
      <main>
        <div className="wf-intro">
          <p>INFORMATION ARCHITECTURE & WIREFRAMES</p>
          <h1>직원·관리자 화면 구성</h1>
          <span>
            직원은 질문·원문·문의를, 관리자는 자료·운영·비용을 중심으로
            사용합니다.
          </span>
          <div>
            <span>
              <Check size={13} />
              직원 6개 화면
            </span>
            <span>
              <Check size={13} />
              관리자 8개 화면
            </span>
            <span>
              <ShieldCheck size={13} />
              복지 추천 제외
            </span>
          </div>
        </div>
        <div className="wf-toolbar">
          <div className="wf-segment">
            <button
              aria-pressed={view === "wireframe"}
              onClick={() => setView("wireframe")}
            >
              <Columns2 size={15} />
              와이어프레임
            </button>
            <button
              aria-pressed={view === "map"}
              onClick={() => setView("map")}
            >
              <ListTree size={15} />
              전체 화면 구성
            </button>
          </div>
          {view === "wireframe" && (
            <>
              <div className="wf-segment">
                <button
                  aria-pressed={role === "employee"}
                  onClick={() => changeRole("employee")}
                >
                  직원 화면
                </button>
                <button
                  aria-pressed={role === "admin"}
                  onClick={() => changeRole("admin")}
                >
                  관리자 화면
                </button>
              </div>
              <div className="wf-device">
                <button
                  aria-label="PC 와이어프레임"
                  aria-pressed={device === "desktop"}
                  onClick={() => setDevice("desktop")}
                >
                  <Monitor size={17} />
                </button>
                <button
                  aria-label="모바일 와이어프레임"
                  aria-pressed={device === "mobile"}
                  onClick={() => setDevice("mobile")}
                >
                  <Smartphone size={16} />
                </button>
              </div>
            </>
          )}
        </div>
        {view === "map" ? (
          <div className="wf-map">
            {(["employee", "admin"] as Role[]).map((value) => (
              <section key={value}>
                <header>
                  <span>{value === "employee" ? "EMPLOYEE" : "ADMIN"}</span>
                  <h2>
                    {value === "employee"
                      ? "직원 업무 공간"
                      : "인사·AI 운영 콘솔"}
                  </h2>
                  <p>
                    {value === "employee"
                      ? "찾고, 질문하고, 문의한 결과까지 확인"
                      : "자료를 관리하고, 실행과 비용을 추적"}
                  </p>
                </header>
                <div>
                  {SCREENS.filter((item) => item.role === value).map((item) => (
                    <button key={item.id} onClick={() => choose(item)}>
                      <span>{item.id}</span>
                      <div>
                        <strong>{item.title}</strong>
                        <small>{item.summary}</small>
                        <code>{item.path}</code>
                      </div>
                      <ChevronRight size={16} />
                    </button>
                  ))}
                </div>
              </section>
            ))}
          </div>
        ) : (
          <>
            <div className="wf-screen-picker" aria-label="설계할 화면 선택">
              {screens.map((item) => (
                <button
                  key={item.id}
                  aria-pressed={screenId === item.id}
                  onClick={() => choose(item)}
                >
                  <span>{item.id}</span>
                  {item.title}
                </button>
              ))}
            </div>
            <div className="wf-screen-caption">
              <div>
                <span>{screen.id}</span>
                <h2>{screen.title}</h2>
                <p>{screen.summary}</p>
              </div>
              <Link to={screen.path}>
                구현 화면 열기
                <ArrowRight size={14} />
              </Link>
            </div>
            <div className={"wf-canvas " + device}>
              <div
                className={
                  "wf-frame " + (role === "admin" ? "is-admin" : "is-employee")
                }
              >
                <div className="wf-browser-chrome">
                  <i />
                  <i />
                  <i />
                  <span>K:LINK · {screen.title}</span>
                  <small>와이어프레임 · 실제 데이터 아님</small>
                </div>
                <div className="wf-frame-body">
                  <aside className="wf-side">
                    <strong>
                      <span className="wf-mark" />
                      K:LINK
                    </strong>
                    <small>
                      {role === "admin" ? "관리자 콘솔" : "직원 업무 공간"}
                    </small>
                    <nav aria-label="와이어프레임 메뉴">
                      {screens.map((item) => (
                        <button
                          key={item.id}
                          aria-current={
                            screenId === item.id ? "page" : undefined
                          }
                          onClick={() => choose(item)}
                        >
                          <span>{item.id}</span>
                          {item.title}
                        </button>
                      ))}
                    </nav>
                    <footer>
                      <ShieldCheck size={12} />
                      접근·연결 상태
                    </footer>
                  </aside>
                  <div className="wf-content">
                    <div className="wf-mock-top">
                      <span>
                        <PanelLeft size={15} />
                        {role === "admin" ? "운영 워크스페이스" : "내 업무"}
                        <ChevronRight size={12} />
                        {screen.title}
                      </span>
                      <span>
                        검색 <Search size={13} />
                        <i />
                        계정
                      </span>
                    </div>
                    <div className="wf-mobile-label">
                      <strong>K:LINK</strong>
                      <span>{screen.title}</span>
                      <PanelLeft size={16} />
                    </div>
                    <div className="wf-mock-main">
                      <div className="wf-mock-heading">
                        <span>{screen.id}</span>
                        <h3>{screen.title}</h3>
                        <div className="wf-line short" />
                      </div>
                      <ScreenBody screen={screen} />
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <div className="wf-region-notes">
              {screen.regions.map((region, index) => (
                <section key={region.label}>
                  <span>{index + 1}</span>
                  <div>
                    <h3>{region.label}</h3>
                    <p>{region.description}</p>
                  </div>
                </section>
              ))}
            </div>
            <div className="wf-flow">
              <strong>
                {role === "employee" ? "직원 사용 흐름" : "관리자 운영 흐름"}
              </strong>
              {(role === "employee"
                ? [
                    { id: "E02", label: "질문 작성" },
                    { id: "E03", label: "원문 확인" },
                    { id: "E04", label: "필요시 문의" },
                    { id: "E04", label: "처리 결과 확인" },
                  ]
                : [
                    { id: "A02", label: "원문 확인" },
                    { id: "A03", label: "재수집·검사" },
                    { id: "A04", label: "검토 기록" },
                    { id: "A03", label: "스테이징" },
                    { id: "A05", label: "사용량·비용 확인" },
                  ]
              ).map((item, index) => (
                <button
                  key={index}
                  onClick={() =>
                    choose(SCREENS.find((value) => value.id === item.id)!)
                  }
                >
                  {item.label}
                  <ChevronRight size={13} />
                </button>
              ))}
            </div>
          </>
        )}
        <div className="wf-scope">
          <ShieldCheck size={16} />
          <p>
            기존 챗봇·실제 원문 연결을 유지합니다. 직원과 관리자의 권한은
            구분하며, 회사 SSO·운영 승인·클라우드 적재는 연결 상태에 맞게
            표시합니다.
          </p>
        </div>
      </main>
      <footer className="wf-footer">
        K:LINK · 2026.11.08 화면 설계{" "}
        <span>구성 검토용 · 구현 화면은 각 화면의 링크에서 확인</span>
      </footer>
    </div>
  );
}

function Lines({ count = 3 }: { count?: number }) {
  return (
    <div className="wf-lines">
      {Array.from({ length: count }, (_, i) => (
        <div
          key={i}
          className={"wf-line " + (i === count - 1 ? "short" : "")}
        />
      ))}
    </div>
  );
}
function Box({
  title,
  children,
  number,
}: {
  title: string;
  children?: ReactNode;
  number?: number;
}) {
  return (
    <section className="wf-box">
      <header>
        {number && <span>{number}</span>}
        <strong>{title}</strong>
      </header>
      {children ?? <Lines />}
    </section>
  );
}
function Stats({ labels }: { labels: string[] }) {
  return (
    <div className="wf-stats">
      {labels.map((label) => (
        <div key={label}>
          <span>{label}</span>
          <i />
          <div className="wf-line short" />
        </div>
      ))}
    </div>
  );
}
function Table({ headers }: { headers: string[] }) {
  return (
    <div className="wf-table">
      <div className="wf-table-head">
        {headers.map((label) => (
          <span key={label}>{label}</span>
        ))}
      </div>
      {[0, 1, 2, 3].map((row) => (
        <div className="wf-table-row" key={row}>
          {headers.map((label, index) => (
            <span key={label}>
              {index === 0 ? (
                <>
                  <div className="wf-line" />
                  <div className="wf-line short" />
                </>
              ) : (
                <i
                  className={
                    index === headers.length - 1
                      ? "wf-fake-button"
                      : "wf-fake-tag"
                  }
                />
              )}
            </span>
          ))}
        </div>
      ))}
    </div>
  );
}
function Filters({ labels }: { labels: string[] }) {
  return (
    <div className="wf-filters">
      <span>
        <Search size={13} />
        검색
      </span>
      {labels.map((label) => (
        <i key={label}>{label}</i>
      ))}
    </div>
  );
}

function ScreenBody({ screen }: { screen: Screen }) {
  const kind = screen.kind;
  if (kind === "home")
    return (
      <>
        <Box title="빠른 AI 질문" number={1}>
          <div className="wf-question">
            <Sparkles size={17} />
            <span>궁금한 인사 업무를 입력</span>
            <ArrowRight size={16} />
          </div>
          <div className="wf-small-tags">
            <span>휴가 절차</span>
            <span>급여 지급일</span>
            <span>근무시간</span>
          </div>
        </Box>
        <div className="wf-quicklinks">
          {["문의 등록", "규정 원문", "공식 양식"].map((label) => (
            <div key={label}>
              {label}
              <ChevronRight size={13} />
            </div>
          ))}
        </div>
        <div className="wf-two-columns">
          <Box title="내 문의" number={2}>
            <Table headers={["문의 제목", "처리 상태"]} />
          </Box>
          <Box title="자주 찾는 규정" number={3}>
            <div className="wf-link-list">
              {["휴가·휴직", "급여·보수", "근무·휴게시간"].map((label) => (
                <p key={label}>
                  {label}
                  <ChevronRight size={12} />
                </p>
              ))}
            </div>
          </Box>
        </div>
      </>
    );
  if (kind === "chat")
    return (
      <>
        <div className="wf-chat-controls">
          <span>현재 질문 목록</span>
          <span>근거 자료</span>
          <span>새 대화</span>
        </div>
        <div className="wf-chat-layout">
          <Box title="질문과 답변" number={1}>
            <div className="wf-user-bubble">
              사용자 질문
              <Lines count={1} />
            </div>
            <div className="wf-answer-placeholder">
              <strong>원문 기반 답변</strong>
              <Lines count={3} />
              <span className="wf-citation">인용 ① · 문서명</span>
              <Lines count={2} />
              <div className="wf-small-tags">
                <span>조건·예외 원문</span>
                <span>출처 포함 복사</span>
              </div>
            </div>
          </Box>
          <Box title="근거 원문" number={2}>
            <span className="wf-paper-label">선택한 문서 · 조문</span>
            <Lines count={5} />
            <div className="wf-metadata">출처 ID / 버전 / 승인 범위</div>
          </Box>
        </div>
        <Box title="하단 질문 작성창" number={3}>
          <div className="wf-question">
            <span>질문 입력</span>
            <i>전송 / 수신 중지</i>
          </div>
        </Box>
      </>
    );
  if (kind === "dashboard")
    return (
      <>
        <Stats labels={["답변 자료", "검토 구간", "사용 토큰", "추정 비용"]} />
        <div className="wf-two-columns">
          <Box title="데이터 작업" number={1}>
            <div className="wf-small-tags">
              <span>재수집</span>
              <ChevronRight size={12} />
              <span>검사</span>
              <ChevronRight size={12} />
              <span>스테이징</span>
            </div>
            <Table headers={["작업", "진행 상태"]} />
          </Box>
          <Box title="서비스 연결·진단" number={2}>
            <div className="wf-link-list">
              {["원문·AI 서비스", "운영 저장소", "회사 인증·적재 상태"].map(
                (label) => (
                  <p key={label}>
                    {label}
                    <span className="wf-fake-tag" />
                  </p>
                ),
              )}
            </div>
          </Box>
        </div>
        <Box title="최근 문의·처리할 업무" number={3}>
          <Table headers={["업무", "상태", "열기"]} />
        </Box>
      </>
    );
  if (kind === "usage")
    return (
      <>
        <Filters labels={["조회 기간", "CSV 내보내기"]} />
        <Stats labels={["요청 수", "입력 토큰", "출력 토큰", "추정 비용"]} />
        <div className="wf-two-columns">
          <Box title="기간별 실제 사용량" number={1}>
            <div className="wf-chart-placeholder">
              <span>실사용 집계 차트 영역</span>
              <i />
              <i />
              <i />
            </div>
          </Box>
          <Box title="예산·차단 정책" number={2}>
            <Lines count={4} />
            <div className="wf-small-tags">
              <span>정책 확인</span>
            </div>
          </Box>
        </div>
        <Box title="요청별 호출 상세" number={3}>
          <Table
            headers={["요청·모델 단계", "입력 / 출력", "추정 비용", "상세"]}
          />
        </Box>
      </>
    );
  if (kind === "jobs")
    return (
      <>
        <Stats labels={["대기·실행", "완료 작업", "실패·중단"]} />
        <div className="wf-small-tags">
          <span>원문 재수집</span>
          <ChevronRight size={12} />
          <span>정합성 검사</span>
          <ChevronRight size={12} />
          <span>별도 스테이징</span>
          <ChevronRight size={12} />
          <span>보고서</span>
        </div>
        <Filters labels={["작업 종류", "실행 상태", "새 작업"]} />
        <Box title="작업 큐·버전" number={1}>
          <Table
            headers={["작업 ID · 선택 문서", "진행률·결과", "중지·재시도"]}
          />
        </Box>
        <div className="wf-two-columns">
          <Box title="선택 작업의 결과" number={2}>
            <Lines count={3} />
            <span className="wf-paper-label">
              답변·검토 구간 / 파일·색인 해시
            </span>
          </Box>
          <Box title="기존 버전 보존" number={3}>
            <span className="wf-paper-label">현재 서비스 유지</span>
            <Lines count={2} />
          </Box>
        </div>
      </>
    );
  if (kind === "settings")
    return (
      <>
        <div className="wf-two-columns">
          <Box title="예산·서비스 정책" number={1}>
            <div className="wf-field-list">
              {[
                "월 예산",
                "일일 요청 한도",
                "관찰·차단 동작",
                "AI 점검 모드",
              ].map((label) => (
                <p key={label}>
                  <span>{label}</span>
                  <i />
                </p>
              ))}
            </div>
          </Box>
          <Box title="모델 계산 단가" number={2}>
            <div className="wf-field-list">
              {["일반 입력", "캐시 입력·쓰기", "출력", "적용 버전·출처"].map(
                (label) => (
                  <p key={label}>
                    <span>{label}</span>
                    <i />
                  </p>
                ),
              )}
            </div>
          </Box>
        </div>
        <Box title="역할별 권한·실제 연결 상태" number={3}>
          <Table headers={["기능·연결", "역할·적용 범위", "상태"]} />
        </Box>
      </>
    );
  if (kind === "account" || kind === "status")
    return (
      <>
        <div className="wf-two-columns">
          <Box
            title={kind === "account" ? "접속 정보" : "현재 기능 연결"}
            number={1}
          >
            <div className="wf-field-list">
              {(kind === "account"
                ? ["현재 계정", "회사 인증", "자료 범위", "회사 적용"]
                : [
                    "원문·AI 서비스",
                    "검토 전용 자료",
                    "조직 인증",
                    "실제 양식·신청",
                  ]
              ).map((label) => (
                <p key={label}>
                  <span>{label}</span>
                  <i />
                </p>
              ))}
            </div>
          </Box>
          <Box
            title={kind === "account" ? "정보 보관 안내" : "별도 확인 항목"}
            number={2}
          >
            <Lines count={5} />
          </Box>
        </div>
        <Box title="연결·적용 범위" number={3}>
          <Lines count={3} />
        </Box>
      </>
    );
  const headers: Record<string, string[]> = {
    library: ["문서명·조문", "적용 범위", "원문"],
    sources: ["선택·문서명", "답변용 / 검토용", "버전·상태", "작업"],
    reviews: ["문서·보류 사유", "검토 상태", "담당·시각", "기록"],
    requests: ["문의 제목", "분야", "처리 상태", "상세"],
    cases: ["문의·분야", "접수·상태", "최근 변경", "처리"],
    audit: ["시각", "실행 주체·작업", "대상", "상세"],
  };
  return (
    <>
      <Filters
        labels={
          kind === "sources"
            ? ["답변 / 검토 범위", "선택 작업"]
            : kind === "library"
              ? ["답변용 검색", "공식 양식", "검토 발췌"]
              : kind === "requests"
                ? ["문의 상태", "새 문의 등록"]
                : kind === "reviews"
                  ? ["검토 상태", "발췌 검색"]
                  : ["상태·종류", "새로고침"]
        }
      />
      {kind === "sources" && (
        <div className="wf-small-tags">
          <span>정합성 검사</span>
          <span>원문 재수집</span>
          <span>스테이징 재적재</span>
        </div>
      )}
      <Box title={screen.regions[0].label} number={1}>
        <Table headers={headers[kind] ?? ["목록", "상태", "상세"]} />
      </Box>
      <div className="wf-two-columns">
        <Box title={screen.regions[1].label} number={2}>
          <Lines count={4} />
        </Box>
        <Box title={screen.regions[2].label} number={3}>
          <Lines count={3} />
          <div className="wf-small-tags">
            <span>
              {kind === "cases"
                ? "상태·안내 저장"
                : kind === "reviews"
                  ? "검토 기록 저장"
                  : "상세 열기"}
            </span>
          </div>
        </Box>
      </div>
    </>
  );
}
