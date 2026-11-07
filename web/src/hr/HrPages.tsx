import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import {
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleHelp,
  Clock3,
  FileCheck2,
  RefreshCw,
  Search,
  Settings2,
  ShieldCheck,
  Sparkles,
  Trash2,
} from "lucide-react";
import { Heading, Modal, Note } from "../portal/ui";
import { useHr } from "./HrContext";
import { SourceScopeNotice } from "./ReviewEvidence";
import type { EmployeeProfile, HrBenefit } from "./api";
import {
  Company,
  DecisionBadge,
  HrIcon,
  SourceView,
  Unavailable,
  attempt,
  LABELS,
} from "./ui";

export function BenefitDetail({
  benefit,
  close,
}: {
  benefit: HrBenefit;
  close: () => void;
}) {
  const { prepare, busy, forms } = useHr(),
    navigate = useNavigate();
  const [tab, setTab] = useState("conditions");
  const form = forms?.find((item) => item.id === benefit.form_id);
  return (
    <Modal
      drawer
      title={benefit.title}
      subtitle={
        benefit.synthetic
          ? "서버의 가상 규정 기준"
          : "제공된 조건을 바탕으로 한 추천"
      }
      close={close}
    >
      <div className="p-detail-summary">
        <DecisionBadge benefit={benefit} />
        <strong>{benefit.value}</strong>
        <p>
          {benefit.synthetic
            ? "가상 규정의 예시 금액·일수 · 실제 지급 기준 아님"
            : "제공된 규정 기준 · 실제 자격 최종 확인 필요"}
        </p>
        <span>
          {benefit.deadline ? benefit.deadline + "까지" : "접수 일정 별도 확인"}{" "}
          · 서버 기준일 {benefit.as_of}
        </span>
      </div>
      <div className="p-detail-tabs">
        {[
          { id: "conditions", label: "추천 이유" },
          { id: "source", label: "근거 규정" },
          { id: "prepare", label: "양식·준비" },
        ].map((item) => (
          <button
            key={item.id}
            onClick={() => setTab(item.id)}
            aria-pressed={tab === item.id}
          >
            {item.label}
          </button>
        ))}
      </div>
      <div className="p-modal-body p-detail-body">
        {tab === "conditions" ? (
          <>
            <h3>서버에서 확인한 조건</h3>
            <Company company={benefit.source.company} />
            <div className="p-conditions">
              {benefit.checks.map((check) => (
                <div key={check.id} className={check.state}>
                  <span>
                    {check.state === "pass" ? (
                      <Check size={17} />
                    ) : (
                      <CircleHelp size={17} />
                    )}
                  </span>
                  <div>
                    <strong>{check.label}</strong>
                    <p>{check.reason}</p>
                  </div>
                  <b>
                    {
                      { pass: "충족", unknown: "확인 필요", fail: "미충족" }[
                        check.state
                      ]
                    }
                  </b>
                </div>
              ))}
            </div>
            {benefit.reasons.map((reason) => (
              <p key={reason}>{reason}</p>
            ))}
            {benefit.exceptions.length > 0 && (
              <>
                <h3>예외·제외 조건</h3>
                <ul>
                  {benefit.exceptions.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </>
            )}
            <Note>
              {benefit.synthetic
                ? "가상 조건의 일치 여부입니다. 실제 KTcs 혜택의 자격 확정이나 승인이 아닙니다."
                : "규정 승인과 본인의 최종 자격·신청 승인은 구분됩니다."}
            </Note>
          </>
        ) : tab === "source" ? (
          <SourceView source={benefit.source} />
        ) : (
          <>
            <h3>필요한 준비</h3>
            <ol className="p-number-list">
              {benefit.checklist.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ol>
            <dl className="p-meta">
              <div>
                <dt>관련 양식</dt>
                <dd>{form?.title ?? "담당 부서에서 확인 필요"}</dd>
              </div>
              <div>
                <dt>공식 파일</dt>
                <dd>
                  {form?.official_available
                    ? "서버의 양식 검증 상태 확인 · 직원 권한 필요"
                    : "미연결 · 실제 회사 양식 확인 필요"}
                </dd>
              </div>
              <div>
                <dt>실제 제출</dt>
                <dd>신청·결재 연결 전</dd>
              </div>
            </dl>
            <Link
              to="/hr/library?tab=forms"
              onClick={close}
              className="p-button p-secondary"
            >
              양식 준비 안내 보기
              <ArrowRight size={16} />
            </Link>
            <Note>
              준비 체크와 실제 제출은 다릅니다. 준비 목록에 담아도 회사에 신청이
              제출되지 않아요.
            </Note>
          </>
        )}
      </div>
      <div className="p-drawer-footer">
        <Link
          className="p-button p-secondary"
          to="/hr/library?tab=rules&q=휴가"
          onClick={close}
        >
          <BookOpen size={16} />
          원문 찾기
        </Link>
        <button
          className="p-button"
          disabled={busy}
          onClick={() =>
            void attempt(prepare(benefit)).then((done) => {
              if (done) {
                close();
                navigate("/hr/preparations");
              }
            })
          }
        >
          {busy
            ? "반영 중…"
            : benefit.status === "eligible"
              ? "서버 준비 목록에 담기"
              : "확인할 항목 담기"}
          <ArrowRight size={16} />
        </button>
      </div>
    </Modal>
  );
}
function BenefitCards({
  items,
  select,
}: {
  items: HrBenefit[];
  select: (item: HrBenefit) => void;
}) {
  return (
    <div className="p-benefit-grid">
      {items.map((benefit) => (
        <article className="p-benefit-card hr-benefit-card" key={benefit.id}>
          <div className="p-benefit-card-top">
            <HrIcon id={benefit.id} />
            <Company company={benefit.source.company} />
          </div>
          <span className="p-category">{benefit.category}</span>
          <h2>
            <button onClick={() => select(benefit)}>{benefit.title}</button>
          </h2>
          <strong className="p-card-value">{benefit.value}</strong>
          <small className="p-card-value-note">
            {benefit.synthetic
              ? "가상 규정의 예시 금액·일수"
              : "제공된 규정 기준 · 개인 자격 별도 확인"}
          </small>
          <DecisionBadge benefit={benefit} />
          <p className="p-card-reason">{benefit.reasons.join(" ")}</p>
          <footer>
            <span>
              {benefit.deadline
                ? benefit.deadline + "까지"
                : "접수 일정 별도 확인"}
            </span>
            <button
              aria-label={benefit.title + " 상세 보기"}
              onClick={() => select(benefit)}
            >
              조건·근거
              <ArrowUpRight size={16} />
            </button>
          </footer>
        </article>
      ))}
    </div>
  );
}
export function HrDashboard() {
  const {
    catalog,
    plans,
    profile,
    readiness,
    updates,
    busy,
    reminders,
    refresh,
  } = useHr();
  const [selected, setSelected] = useState<HrBenefit | null>(null);
  if (!catalog)
    return (
      <Unavailable
        title="혜택 추천을 조회하지 못했어요"
        retry={() => void refresh()}
      />
    );
  const cards = catalog.cards
    .filter((card) => card.status === "eligible")
    .slice(0, 2);
  const shown = cards.length ? cards : catalog.cards.slice(0, 2);
  return (
    <>
      <section className="p-welcome">
        <div>
          <span className="p-kicker">YOUR WORK & LIFE, CONNECTED</span>
          <h1>
            오늘 필요한 인사 업무,
            <br className="hr-phone-break" />
            <strong> 한곳에서 이어가세요.</strong>
          </h1>
          <p>
            서버에서 불러온 추천과 준비 목록입니다. 실제 회사 적용 상태를 함께
            확인하세요.
          </p>
        </div>
        <Link to="/hr/profile" className="p-button p-secondary">
          <Settings2 size={16} />내 조건 관리
        </Link>
      </section>
      <section className="hr-connection-strip" aria-label="현재 연결 구분">
        <Link to="/hr/status">
          <span className="hr-dot live" />
          인사 기능 <b>연결됨</b>
          <ChevronRight size={14} />
        </Link>
        <Link to="/hr/status">
          <span className="hr-dot" />
          회사 승인 규정 <b>{readiness?.approved_policy_count ?? "미확인"}건</b>
        </Link>
        <Link to="/hr/library?tab=forms">
          <span className="hr-dot" />
          공식 양식 <b>{readiness?.official_form_count ?? "미확인"}건</b>
        </Link>
        <Link to="/hr/status">
          <span className="hr-dot" />
          회사 SSO <b>연결 전</b>
        </Link>
      </section>
      <div className="hr-summary-row">
        <Link to="/hr/benefits?status=eligible">
          <CheckCircle2 size={23} />
          <div>
            <span>조건 충족 {catalog.synthetic ? "· 예시" : ""}</span>
            <strong>
              {catalog.counts.eligible}
              <small>건</small>
            </strong>
          </div>
          <ArrowUpRight size={17} />
        </Link>
        <Link to="/hr/benefits?status=needs_review">
          <CircleHelp size={23} />
          <div>
            <span>추가 확인이 필요한 혜택</span>
            <strong>
              {catalog.counts.needs_review}
              <small>건</small>
            </strong>
          </div>
          <ArrowUpRight size={17} />
        </Link>
        <Link to="/hr/preparations">
          <FileCheck2 size={23} />
          <div>
            <span>서버에서 준비 중</span>
            <strong>
              {plans?.length ?? "—"}
              <small>건</small>
            </strong>
          </div>
          <ArrowUpRight size={17} />
        </Link>
      </div>
      <div className="hr-home-grid">
        <section>
          <div className="p-section-heading">
            <div>
              <span className="p-kicker">RECOMMENDED FOR YOU</span>
              <h2>내 조건으로 살펴본 혜택</h2>
            </div>
            <Link to="/hr/benefits" className="p-text-link">
              전체 보기
              <ChevronRight size={15} />
            </Link>
          </div>
          {shown.length ? (
            <BenefitCards items={shown} select={setSelected} />
          ) : (
            <Unavailable title="승인된 회사 규정 연결 후 추천할 수 있어요" />
          )}
          <Note>
            {catalog.synthetic
              ? "현재는 서버의 가상 규정과 예시 직원 조건으로 추천합니다."
              : "본인이 동의해 제공한 조건으로 추천합니다. 인가된 HR 원장과 최종 자격 검증은 별도입니다."}{" "}
            {profile?.employment_consent
              ? "근무 조건 활용 동의 상태가 반영됐어요."
              : "근무 조건은 동의 전이므로 확정하지 않아요."}
          </Note>
        </section>
        <aside className="hr-next-panel">
          <span className="p-kicker">BEFORE YOU CONTINUE</span>
          <h2>
            회사 적용 전,
            <br />
            먼저 확인해 주세요
          </h2>
          <div>
            <ShieldCheck size={20} />
            <span>
              <strong>실제 KTcs 현행 규정</strong>
              <small>회사 승인과 조건·예외 검토 대기</small>
            </span>
          </div>
          <div>
            <BookOpen size={20} />
            <span>
              <strong>
                한국전력 참고 원문{" "}
                {readiness?.research.source_count ?? "미확인"}개
              </strong>
              <small>KTcs 적용·사람 승인 별도 확인</small>
            </span>
          </div>
          <div>
            <FileCheck2 size={20} />
            <span>
              <strong>공식 양식·실제 제출</strong>
              <small>회사 양식과 신청·결재 연결 대기</small>
            </span>
          </div>
          <Link className="p-button p-secondary" to="/hr/status">
            연결 상태 자세히 보기
            <ArrowRight size={16} />
          </Link>
        </aside>
      </div>
      <div className="hr-home-bottom">
        <section className="hr-knowledge-banner">
          <span className="p-kicker">EVIDENCE BEFORE ANSWERS</span>
          <h2>
            궁금한 규정은,
            <br />
            원문과 함께 확인해요.
          </h2>
          <p>실제로 조회한 한국전력 참고 원문과 인용을 함께 표시합니다.</p>
          <Link className="p-button" to="/hr/assistant">
            <Sparkles size={17} />
            인사 질문하기
            <ArrowRight size={16} />
          </Link>
          <Link className="p-text-link" to="/hr/library?tab=rules&q=병가">
            병가 원문부터 찾아보기
            <ChevronRight size={15} />
          </Link>
        </section>
        <section className="hr-updates">
          <div className="p-section-heading">
            <div>
              <span className="p-kicker">UPDATES & DEADLINES</span>
              <h2>변경·마감 다시 확인</h2>
            </div>
            <Clock3 size={20} />
          </div>
          {updates ? (
            <>
              <label className="hr-native-check">
                <input
                  type="checkbox"
                  checked={updates.enabled}
                  disabled={busy}
                  onChange={(event) =>
                    void attempt(reminders(event.target.checked))
                  }
                />
                <span>이 화면에서 변경·마감 안내 받기</span>
              </label>
              {updates.enabled ? (
                <div className="hr-update-list">
                  {updates.updates.length ? (
                    updates.updates.map((item, index) => (
                      <Link
                        key={item.benefit_id + index}
                        to={
                          "/hr/benefits?benefit=" +
                          encodeURIComponent(item.benefit_id)
                        }
                      >
                        <strong>
                          {catalog.cards.find(
                            (card) => card.id === item.benefit_id,
                          )?.title ?? "이전 혜택"}
                        </strong>
                        <p>{item.message}</p>
                        {updates.synthetic && (
                          <span className="p-label">예시 규정 일정</span>
                        )}
                      </Link>
                    ))
                  ) : (
                    <p>현재 추가로 표시할 변경·마감이 없어요.</p>
                  )}
                </div>
              ) : (
                <p className="hr-updates-description">
                  원할 때 켜고 끌 수 있어요. 동의 전에는 변경·마감을 표시하지
                  않습니다.
                </p>
              )}
              <small>
                화면 안의 안내만 제공합니다. 메일·문자·회사 알림은 발송하지
                않습니다.
              </small>
            </>
          ) : (
            <Unavailable title="변경 안내를 조회하지 못했어요" />
          )}
        </section>
      </div>
      {selected && (
        <BenefitDetail benefit={selected} close={() => setSelected(null)} />
      )}
    </>
  );
}
export function HrBenefits() {
  const { catalog, refresh } = useHr(),
    [params, setParams] = useSearchParams(),
    [selected, setSelected] = useState<HrBenefit | null>(null);
  const filter = params.get("status") ?? "all",
    query = params.get("q") ?? "",
    requested = params.get("benefit");
  const [category, setCategory] = useState("all");
  function update(key: string, value: string) {
    const next = new URLSearchParams(window.location.search);
    value === "all" || !value ? next.delete(key) : next.set(key, value);
    setParams(next, { replace: true });
  }
  if (!catalog) return <Unavailable retry={() => void refresh()} />;
  const detail =
    selected ?? catalog.cards.find((card) => card.id === requested);
  const filtered = catalog.cards.filter(
    (card) =>
      (filter === "all" || card.status === filter) &&
      (category === "all" || card.category === category) &&
      (card.title + card.category).includes(query),
  );
  return (
    <>
      <Heading
        label="PERSONAL RECOMMENDATIONS"
        title="내 조건과 규정을 함께 확인해요."
        action={
          <Link className="p-button p-secondary" to="/hr/profile">
            <Settings2 size={16} />
            추천 조건 관리
          </Link>
        }
      >
        추천은 서버에서 계산합니다. 가상 규정의 예시와 회사 적용 상태를 구분해
        표시해요.
      </Heading>
      <div className="p-filter-tabs" aria-label="서버 혜택 상태 필터">
        {[
          { id: "all", label: "전체", count: catalog.cards.length },
          ...Object.entries(LABELS).map(([id, label]) => ({
            id,
            label,
            count: catalog.counts[id as keyof typeof LABELS],
          })),
        ].map((item) => (
          <button
            key={item.id}
            aria-pressed={filter === item.id}
            onClick={() => update("status", item.id)}
          >
            {item.label}
            <span>{item.count}</span>
          </button>
        ))}
      </div>
      <div className="p-benefit-controls">
        <label className="p-inline-search">
          <Search size={18} />
          <input
            aria-label="연결된 혜택 검색"
            placeholder="혜택 이름이나 분야 검색"
            maxLength={200}
            value={query}
            onChange={(event) => update("q", event.target.value)}
          />
        </label>
        <select
          aria-label="연결된 혜택 분야"
          className="hr-select"
          value={category}
          onChange={(event) => setCategory(event.target.value)}
        >
          <option value="all">모든 분야</option>
          {[...new Set(catalog.cards.map((card) => card.category))].map(
            (item) => (
              <option key={item}>{item}</option>
            ),
          )}
        </select>
      </div>
      <div className="p-result-heading">
        <p>
          총 <b>{filtered.length}</b>개의 혜택
        </p>
        <span>
          {catalog.synthetic ? "서버의 가상 규정" : "회사 규정 확인 범위"} ·
          최종 자격 확정 전
        </span>
      </div>
      {filtered.length ? (
        <BenefitCards items={filtered} select={setSelected} />
      ) : (
        <Unavailable
          title={
            catalog.configuration_required
              ? "승인된 회사 규정이 아직 연결되지 않았어요"
              : "현재 조건에 맞는 검색 결과가 없어요"
          }
        />
      )}
      <Note>
        조건 충족 표시는 지급·휴가 승인이나 실제 신청 완료를 뜻하지 않습니다.
        조건과 근거를 확인한 뒤 준비 목록에 담아주세요.
      </Note>
      {detail && (
        <BenefitDetail
          key={detail.id}
          benefit={detail}
          close={() => {
            setSelected(null);
            update("benefit", "");
          }}
        />
      )}
    </>
  );
}
export function HrPreparations() {
  const { plans, catalog, busy, check, remove, prepare, refresh } = useHr();
  if (!plans)
    return (
      <Unavailable
        title="서버 준비 목록을 조회하지 못했어요"
        retry={() => void refresh()}
      />
    );
  return (
    <>
      <Heading
        label="YOUR PREPARATIONS"
        title="준비한 내용, 서버에서 이어가요."
        action={
          <Link className="p-button p-secondary" to="/hr/benefits">
            혜택 더 찾기
            <ArrowUpRight size={16} />
          </Link>
        }
      >
        현재 서버 접속 동안 유지됩니다. 서버 재시작·접속 만료 이후의 보관은
        보장하지 않습니다.
      </Heading>
      {!plans.length ? (
        <div className="p-empty">
          <FileCheck2 size={35} />
          <h2>서버에 담은 준비 목록이 없어요</h2>
          <p>혜택의 조건과 근거를 확인하고 준비를 시작해 보세요.</p>
          <Link className="p-button" to="/hr/benefits">
            혜택 살펴보기
            <ArrowRight size={16} />
          </Link>
        </div>
      ) : (
        <div className="p-preparation-grid">
          {plans.map((plan) => {
            const benefit = catalog?.cards.find(
              (card) => card.id === plan.benefit_id,
            );
            return (
              <article key={plan.id} className="p-preparation-card hr-plan">
                <header>
                  <HrIcon id={plan.benefit_id} />
                  <div>
                    <small>서버 준비 목록</small>
                    <h2>{plan.title}</h2>
                  </div>
                  <button
                    className="p-icon-button"
                    disabled={busy}
                    aria-label={plan.title + " 서버 준비 삭제"}
                    onClick={() => void attempt(remove(plan.id))}
                  >
                    <Trash2 size={19} />
                  </button>
                </header>
                <div className="hr-plan-status">
                  <span
                    className={
                      "p-status " + (plan.stale ? "needs_review" : "eligible")
                    }
                  >
                    {plan.stale ? "조건·규정 재확인 필요" : "준비 중 · 미제출"}
                  </span>
                  <small>
                    {plan.checked.length} / {plan.checklist.length}
                  </small>
                </div>
                {plan.stale && (
                  <Note>
                    조건이나 규정이 바뀌었거나 추가 확인이 필요해 이전 체크를
                    사용할 수 없어요.
                  </Note>
                )}
                <div className="hr-checklist">
                  {plan.checklist.map((item, index) => (
                    <label key={item}>
                      <input
                        aria-label={plan.title + " " + item}
                        type="checkbox"
                        checked={plan.checked.includes(index)}
                        disabled={busy || plan.stale}
                        onChange={(event) =>
                          void attempt(check(plan, index, event.target.checked))
                        }
                      />
                      <span>{item}</span>
                    </label>
                  ))}
                </div>
                {plan.checked.length === plan.checklist.length &&
                  !plan.stale && (
                    <p className="hr-check-complete">
                      <CheckCircle2 size={16} />
                      확인 표시 완료 · 회사 검토·승인과는 별도입니다.
                    </p>
                  )}
                <footer>
                  <Link
                    className="p-text-link"
                    to={
                      "/hr/benefits?benefit=" +
                      encodeURIComponent(plan.benefit_id)
                    }
                  >
                    최신 조건·근거
                    <ChevronRight size={15} />
                  </Link>
                  <Link className="p-text-link" to="/hr/library?tab=forms">
                    공식 양식 확인
                    <ChevronRight size={15} />
                  </Link>
                </footer>
                {plan.stale && benefit?.status === "eligible" && (
                  <button
                    className="p-button p-secondary"
                    disabled={busy}
                    onClick={() => void attempt(prepare(benefit))}
                  >
                    <RefreshCw size={15} />
                    최신 조건으로 준비 다시 시작
                  </button>
                )}
                <button className="hr-submit-disabled" disabled>
                  실제 신청·결재 연결 전
                </button>
              </article>
            );
          })}
        </div>
      )}
      <Note>
        새로고침 후에도 서버 접속이 유효하면 준비 목록을 다시 불러옵니다. 실제
        회사 시스템에 제출하거나 신청을 승인하지 않습니다.
      </Note>
    </>
  );
}
export function HrProfile() {
  const { profile, refresh } = useHr();
  if (!profile)
    return (
      <Unavailable
        title="본인의 조건을 조회하지 못했어요"
        retry={() => void refresh()}
      />
    );
  return <ProfileEditor key={JSON.stringify(profile)} initial={profile} />;
}
function ProfileEditor({ initial }: { initial: EmployeeProfile }) {
  const { saveProfile, revoke, busy, session } = useHr(),
    [draft, setDraft] = useState(initial),
    [ages, setAges] = useState(initial.children_ages?.join(", ") ?? ""),
    [noChildren, setNoChildren] = useState(initial.children_ages?.length === 0),
    [error, setError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    const parts = ages.trim() ? ages.split(",").map((item) => item.trim()) : [];
    if (
      draft.family_consent &&
      !noChildren &&
      parts.some((item) => !/^\d+$/.test(item) || Number(item) > 30)
    ) {
      setError("자녀 나이는 0~30세 정수를 쉼표로 나누어 입력해 주세요.");
      return;
    }
    const payload = {
      ...draft,
      hire_date: draft.employment_consent ? draft.hire_date : null,
      employment_type: draft.employment_consent ? draft.employment_type : null,
      children_ages: draft.family_consent
        ? noChildren
          ? []
          : parts.length
            ? parts.map(Number)
            : null
        : null,
      household_size: draft.family_consent ? draft.household_size : null,
    };
    await attempt(saveProfile(payload));
  }
  return (
    <>
      <Heading
        label="YOUR CONDITIONS & CONSENT"
        title="동의한 조건만 추천에 반영해요."
      >
        서버에서 조회한 본인 조건입니다.{" "}
        {session?.mode === "demo"
          ? "예시 체험 중이므로 실제 개인정보를 입력하지 마세요."
          : "직접 제공한 조건이며 인가된 HR 원장과 별도입니다."}
      </Heading>
      <div className="p-profile-layout">
        <form className="p-profile-form" onSubmit={submit}>
          <fieldset className="hr-profile-fieldset" disabled={busy}>
            <section className="p-profile-section">
              <header>
                <span>01</span>
                <div>
                  <h2>근무 조건 활용</h2>
                  <p>고용형태·입사일을 조건 확인에 사용합니다.</p>
                </div>
              </header>
              <label className="hr-native-check">
                <input
                  type="checkbox"
                  aria-label="서버 근무 정보 활용 동의"
                  checked={draft.employment_consent}
                  onChange={(event) =>
                    setDraft({
                      ...draft,
                      employment_consent: event.target.checked,
                    })
                  }
                />
                <span>근무 조건 활용에 동의</span>
              </label>
              <fieldset disabled={!draft.employment_consent}>
                <legend className="p-sr-only">근무 조건</legend>
                <label>
                  고용형태
                  <select
                    aria-label="서버 고용형태"
                    value={draft.employment_type ?? ""}
                    onChange={(event) =>
                      setDraft({
                        ...draft,
                        employment_type: (event.target.value ||
                          null) as EmployeeProfile["employment_type"],
                      })
                    }
                  >
                    <option value="">확인 전</option>
                    <option value="regular">정규직</option>
                    <option value="fixed_term">기간제</option>
                    <option value="part_time">시간제</option>
                  </select>
                </label>
                <label>
                  입사일
                  <input
                    className="hr-input"
                    aria-label="서버 입사일"
                    type="date"
                    value={draft.hire_date ?? ""}
                    max={new Intl.DateTimeFormat("sv-SE", {
                      timeZone: "Asia/Seoul",
                    }).format(new Date())}
                    onChange={(event) =>
                      setDraft({
                        ...draft,
                        hire_date: event.target.value || null,
                      })
                    }
                  />
                </label>
              </fieldset>
            </section>
            <section className="p-profile-section">
              <header>
                <span>02</span>
                <div>
                  <h2>
                    가족 조건 활용 <small>선택</small>
                  </h2>
                  <p>이름·주민번호 없이 나이와 가구원 수만 사용합니다.</p>
                </div>
              </header>
              <label className="hr-native-check">
                <input
                  type="checkbox"
                  aria-label="서버 가족 정보 활용 동의"
                  checked={draft.family_consent}
                  onChange={(event) =>
                    setDraft({ ...draft, family_consent: event.target.checked })
                  }
                />
                <span>가족 조건 활용에 동의</span>
              </label>
              <fieldset disabled={!draft.family_consent}>
                <legend className="p-sr-only">가족 조건</legend>
                <label>
                  자녀 나이
                  <input
                    className="hr-input"
                    aria-label="서버 자녀 나이"
                    placeholder="예: 5, 9 / 모르면 비워두기"
                    maxLength={80}
                    disabled={noChildren}
                    value={ages}
                    onChange={(event) => setAges(event.target.value)}
                  />
                </label>
                <label>
                  가구원 수
                  <input
                    className="hr-input"
                    type="number"
                    aria-label="서버 가구원 수"
                    min={1}
                    max={20}
                    value={draft.household_size ?? ""}
                    onChange={(event) =>
                      setDraft({
                        ...draft,
                        household_size: event.target.value
                          ? Number(event.target.value)
                          : null,
                      })
                    }
                  />
                </label>
                <label className="hr-native-check">
                  <input
                    type="checkbox"
                    aria-label="자녀 없음 확인"
                    checked={noChildren}
                    onChange={(event) => setNoChildren(event.target.checked)}
                  />
                  <span>자녀 없음으로 확인</span>
                </label>
              </fieldset>
            </section>
            {error && (
              <p role="alert" className="hr-field-error">
                {error}
              </p>
            )}
            <div className="p-profile-actions">
              <span>제공한 조건 기준 · 최종 자격 별도 확인</span>
              <button className="p-button" type="submit">
                {busy ? "서버에 반영 중…" : "서버에 조건 반영"}
                <Check size={16} />
              </button>
            </div>
          </fieldset>
        </form>
        <aside className="p-privacy-panel hr-privacy">
          <ShieldCheck size={28} />
          <h2>
            선택도 철회도,
            <br />
            내가 결정해요.
          </h2>
          <ul>
            <li>선택하지 않은 정보는 추천에 미사용</li>
            <li>서버 저장 성공을 확인한 후 추천 갱신</li>
            <li>조건 변경 시 이전 준비 항목 재확인</li>
            <li>대화에 프로필을 자동 첨부하지 않음</li>
          </ul>
          <div>
            <h3>동의를 철회하면</h3>
            <p>
              서버 응답을 확인한 후 조건·준비 목록·변경 안내를 비웁니다. 삭제가
              실패하면 완료로 표시하지 않습니다.
            </p>
            <button
              className="p-revoke-button"
              disabled={busy}
              onClick={() => void attempt(revoke())}
            >
              서버 동의 철회·정보 비우기
              <Trash2 size={15} />
            </button>
          </div>
        </aside>
      </div>
      <Note>
        {session?.mode === "demo"
          ? "예시 조건은 현재 서버 접속 동안만 유지됩니다. 실제 회사 직원 DB 저장이나 동의 이력의 운영 검증이 아닙니다."
          : "현재 저장소·직원 권한·보존 정책의 운영 검증 상태를 연결 상태 화면에서 확인해 주세요."}
      </Note>
    </>
  );
}
const GATE_NAMES = [
  "규정과 자격 조건",
  "직원 계정·본인 정보 보호",
  "회사 승인 원문·답변",
  "공식 양식·실제 신청",
  "변경·마감·전달",
  "운영 승인·복구 점검",
];
export function HrReadiness() {
  const { readiness, refresh, busy } = useHr();
  return (
    <>
      <Heading
        label="CONNECTION & APPLICABILITY"
        title="연결된 기능과 확인할 일을 구분해요."
        action={
          <button
            className="p-button p-secondary"
            disabled={busy}
            onClick={() => void refresh()}
          >
            <RefreshCw size={16} />
            현재 상태 다시 조회
          </button>
        }
      >
        화면과 서버가 연결된 상태를 회사의 규정·직원 자격·운영 승인과
        구분합니다.
      </Heading>
      <div className="hr-status-overview">
        <div>
          <span className="hr-dot live" />
          <strong>인사 기능 연결됨</strong>
          <p>서버 추천·조건 저장·준비 목록·원문 조회</p>
        </div>
        <div>
          <span className="hr-dot" />
          <strong>회사 적용·실제 신청 확인 전</strong>
          <p>승인 규정·공식 양식·조직 인증 연결 대기</p>
        </div>
      </div>
      <SourceScopeNotice />
      {readiness ? (
        <>
          <div className="hr-gates">
            {readiness.gates.map((gate) => (
              <article key={gate.code}>
                <span className="hr-gate-number">0{gate.priority}</span>
                <div>
                  <h2>{GATE_NAMES[gate.priority - 1] ?? gate.code}</h2>
                  <p>{gate.message}</p>
                </div>
                <span
                  className={
                    "p-status " + (gate.ready ? "eligible" : "needs_review")
                  }
                >
                  {gate.ready ? "서버 확인 범위 충족" : "별도 확인 필요"}
                </span>
              </article>
            ))}
          </div>
          <section className="hr-real-scope">
            <h2>현재 자료·계정의 범위</h2>
            <dl className="p-meta">
              <div>
                <dt>회사 승인 규정</dt>
                <dd>
                  {readiness.approved_policy_count}건 · 실제 KTcs 현행 규정 승인
                  기준
                </dd>
              </div>
              <div>
                <dt>공식 양식</dt>
                <dd>
                  {readiness.official_form_count}건 · 검증된 회사 빈 양식 기준
                </dd>
              </div>
              <div>
                <dt>참고 원문</dt>
                <dd>
                  한국전력 {readiness.research.document_count}문서 ·{" "}
                  {readiness.research.source_count}구간
                </dd>
              </div>
              <div>
                <dt>참고 원문 승인</dt>
                <dd>
                  사람 승인 {readiness.research.human_approved_count}건 · KTcs
                  적용 별도 확인
                </dd>
              </div>
              <div>
                <dt>회사 SSO</dt>
                <dd>연결 전 · 예시 직원 접속과 구분</dd>
              </div>
              <div>
                <dt>직원 저장소</dt>
                <dd>Supabase 적재 보류 · 이 화면에서 연결을 재검증하지 않음</dd>
              </div>
              <div>
                <dt>실제 제출</dt>
                <dd>
                  {readiness.actual_submission_enabled
                    ? "별도 권한·승인 확인 필요"
                    : "연결 전 · 신청·승인 처리되지 않음"}
                </dd>
              </div>
              <div>
                <dt>질문 기능</dt>
                <dd>로컬 원문 기반 · 지정 모델로 초안·원문 자동 재검토</dd>
              </div>
            </dl>
            <details className="hr-integrity">
              <summary>연결 진단 정보</summary>
              <p>Supabase 연결 재조회·스키마 적용·적재를 수행하지 않습니다.</p>
              <p>
                원문 검색: {readiness.research.method} · 검색 성능 재평가를
                수행한 것은 아닙니다.
              </p>
            </details>
          </section>
          <Note>
            {readiness.note} 코드 검사와 자동 답변 검토는 사람의 독립 승인이나
            의미 정확성 보증과 다릅니다.
          </Note>
        </>
      ) : (
        <Unavailable
          title="실제 적용 준비 상태를 조회하지 못했어요"
          retry={() => void refresh()}
        />
      )}
    </>
  );
}
