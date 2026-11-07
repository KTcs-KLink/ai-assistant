import { useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  ArrowRight,
  ArrowUpRight,
  Bookmark,
  Check,
  CheckCircle2,
  ChevronRight,
  FileCheck2,
  FileText,
  ListFilter,
  Search,
  Settings2,
  ShieldCheck,
  Trash2,
} from "lucide-react";
import { useWorkspace } from "../workspace/WorkspaceContext";
import {
  BLANK_PROFILE,
  consented,
  deadlineLabel,
  EMPLOYMENT_LABEL,
} from "../workspace/model";
import { formReferences } from "../workspace/forms";
import type {
  FormReference,
  Profile as ProfileType,
  Status,
} from "../workspace/types";
import {
  Badge,
  BenefitIcon,
  Empty,
  Heading,
  Modal,
  Note,
  Source,
  STATUS,
} from "./ui";

export function Benefits() {
  const { benefits, saved, toggleSaved, select } = useWorkspace();
  const [params, setParams] = useSearchParams();
  const filter = params.get("status") ?? "all";
  const query = params.get("q") ?? "";
  const [category, setCategory] = useState("all");
  const [sort, setSort] = useState("recommended");
  const categories = [...new Set(benefits.map((b) => b.category))];
  const filtered = benefits
    .filter(
      (b) =>
        (filter === "all" ||
          (filter === "saved" ? saved.includes(b.id) : b.status === filter)) &&
        (category === "all" || b.category === category) &&
        (b.title + b.category + b.description).includes(query),
    )
    .sort((a, b) =>
      sort === "deadline"
        ? (a.daysLeft ?? 999) - (b.daysLeft ?? 999)
        : ["eligible", "needs_review", "ineligible"].indexOf(a.status) -
          ["eligible", "needs_review", "ineligible"].indexOf(b.status),
    );
  function update(key: string, value: string) {
    // Merge the latest URL even if the preceding navigation is still rendering.
    const next = new URLSearchParams(window.location.search);
    if (!value || value === "all") next.delete(key);
    else next.set(key, value);
    setParams(next, { replace: true });
  }
  const tabs = [
    { id: "all", label: "전체", count: benefits.length },
    ...(["eligible", "needs_review", "ineligible"] as Status[]).map(
      (status) => ({
        id: status,
        label: STATUS[status],
        count: benefits.filter((b) => b.status === status).length,
      }),
    ),
    { id: "saved", label: "저장한 혜택", count: saved.length },
  ];
  return (
    <>
      <Heading
        label="BENEFITS & WELLBEING"
        title="나를 위한 혜택, 한곳에서."
        action={
          <Link className="p-button p-secondary" to="/workspace/profile">
            <Settings2 size={16} />
            추천 조건 관리
          </Link>
        }
      >
        복지·수당·휴가를 살펴보고 조건과 근거를 확인하세요. 모든 내용은 가상
        예시입니다.
      </Heading>
      <div className="p-filter-tabs" aria-label="혜택 상태 필터">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            aria-pressed={filter === tab.id}
            onClick={() => update("status", tab.id)}
          >
            {tab.label}
            <span>{tab.count}</span>
          </button>
        ))}
      </div>
      <div className="p-benefit-controls">
        <label className="p-inline-search">
          <Search size={18} />
          <input
            value={query}
            onChange={(event) => update("q", event.target.value)}
            maxLength={200}
            placeholder="혜택 이름이나 분야 검색"
            aria-label="혜택 검색"
          />
        </label>
        <label className="p-select-label">
          <ListFilter size={16} />
          <span className="p-sr-only">분야</span>
          <select
            aria-label="혜택 분야"
            value={category}
            onChange={(event) => setCategory(event.target.value)}
          >
            <option value="all">모든 분야</option>
            {categories.map((item) => (
              <option key={item}>{item}</option>
            ))}
          </select>
        </label>
        <label className="p-select-label">
          <span className="p-sr-only">정렬</span>
          <select
            aria-label="혜택 정렬"
            value={sort}
            onChange={(event) => setSort(event.target.value)}
          >
            <option value="recommended">추천순</option>
            <option value="deadline">마감 가까운 순</option>
          </select>
        </label>
      </div>
      <div className="p-result-heading">
        <p>
          총 <b>{filtered.length}</b>개의 혜택
        </p>
        <span>2026.11.07 · 가상 규정·조건 기준</span>
      </div>
      {filtered.length ? (
        <div className="p-benefit-grid">
          {filtered.map((benefit) => (
            <article className="p-benefit-card" key={benefit.id}>
              <div className="p-benefit-card-top">
                <BenefitIcon benefit={benefit} />
                <button
                  className="p-icon-button"
                  onClick={() => toggleSaved(benefit.id)}
                  aria-label={
                    benefit.title +
                    (saved.includes(benefit.id) ? " 저장 취소" : " 저장")
                  }
                  aria-pressed={saved.includes(benefit.id)}
                >
                  <Bookmark
                    size={20}
                    fill={saved.includes(benefit.id) ? "currentColor" : "none"}
                  />
                </button>
              </div>
              <span className="p-category">{benefit.category}</span>
              <h2>
                <button onClick={() => select(benefit.id)}>
                  {benefit.title}
                </button>
              </h2>
              <p className="p-card-description">{benefit.description}</p>
              <strong className="p-card-value">{benefit.value}</strong>
              <small className="p-card-value-note">{benefit.value_note}</small>
              <Badge status={benefit.status} />
              <p className="p-card-reason">{benefit.reason}</p>
              <footer>
                <span>{deadlineLabel(benefit)}</span>
                <button
                  aria-label={benefit.title + " 자세히 보기"}
                  onClick={() => select(benefit.id)}
                >
                  상세 보기
                  <ArrowUpRight size={16} />
                </button>
              </footer>
            </article>
          ))}
        </div>
      ) : (
        <Empty title="조건에 맞는 결과가 없어요">
          검색어·분야·상태를 바꿔보세요. 저장한 혜택은 상세 화면에서 담을 수
          있습니다.
        </Empty>
      )}
    </>
  );
}

export function Library() {
  const { benefits } = useWorkspace();
  const [params, setParams] = useSearchParams();
  const [sourceId, setSourceId] = useState<string | null>(null);
  const [form, setForm] = useState<FormReference | null>(null);
  const source = benefits.find((b) => b.id === sourceId);
  const tab = params.get("tab") === "forms" ? "forms" : "rules";
  const query = params.get("q") ?? "";
  function update(key: string, value: string) {
    // Preserve a just-selected tab when the user immediately starts searching.
    const next = new URLSearchParams(window.location.search);
    value ? next.set(key, value) : next.delete(key);
    setParams(next, { replace: true });
  }
  const rules = benefits.filter((b) =>
    (b.title + b.category + b.quote).includes(query),
  );
  const forms = formReferences.filter((f) =>
    (f.title + f.category + f.description).includes(query),
  );
  return (
    <>
      <Heading
        label="KNOWLEDGE & RESOURCES"
        title="필요한 규정과 양식을 찾아요."
      >
        내용과 출처를 함께 확인하세요. 실제 회사 규정과 공식 양식은 연결
        전입니다.
      </Heading>
      <div className="p-filter-tabs">
        <button
          aria-pressed={tab === "rules"}
          onClick={() => update("tab", "rules")}
        >
          규정 살펴보기<span>{benefits.length}</span>
        </button>
        <button
          aria-pressed={tab === "forms"}
          onClick={() => update("tab", "forms")}
        >
          양식 준비 가이드<span>{formReferences.length}</span>
        </button>
      </div>
      <label className="p-inline-search p-library-search">
        <Search size={19} />
        <input
          aria-label="규정·양식 검색"
          value={query}
          maxLength={200}
          onChange={(event) => update("q", event.target.value)}
          placeholder="규정, 양식 이름 또는 업무를 검색하세요"
        />
      </label>
      <div className="p-library-notice">
        <ShieldCheck size={18} />
        <p>
          {tab === "rules"
            ? "아래 규정은 화면 검증을 위한 가상 문구입니다. 회사·버전·검토 상태를 상세 화면에서 확인할 수 있어요."
            : "아래 항목은 양식 종류와 준비 항목을 안내합니다. 공식 파일은 제공하지 않으며, 실제 양식은 회사에서 확인해야 합니다."}
        </p>
      </div>
      <div className="p-document-list">
        <div className="p-document-list-header">
          <span>{tab === "rules" ? "규정·업무" : "양식·업무"}</span>
          <span>상태</span>
        </div>
        {tab === "rules"
          ? rules.map((benefit) => (
              <button
                key={benefit.id}
                className="p-document-row"
                onClick={() => setSourceId(benefit.id)}
              >
                <span className="p-document-icon">
                  <FileText size={22} />
                </span>
                <span>
                  <small>
                    {benefit.category} · {benefit.section}
                  </small>
                  <strong>{benefit.title}</strong>
                  <p>화면 검증용 가상 복지 규정 · demo-2026.11.07</p>
                </span>
                <span className="p-label">가상 규정</span>
                <ChevronRight size={18} />
              </button>
            ))
          : forms.map((item) => (
              <button
                key={item.id}
                className="p-document-row"
                onClick={() => setForm(item)}
              >
                <span className="p-document-icon">
                  <FileCheck2 size={22} />
                </span>
                <span>
                  <small>{item.category}</small>
                  <strong>{item.title}</strong>
                  <p>{item.description}</p>
                </span>
                <span className="p-label">공식 파일 미연결</span>
                <ChevronRight size={18} />
              </button>
            ))}
        {(tab === "rules" ? rules.length : forms.length) === 0 && (
          <div className="p-empty-compact">
            <Search size={27} />
            <h2>검색 결과가 없어요</h2>
            <p>다른 업무 이름으로 검색해 보세요.</p>
            <button className="p-text-link" onClick={() => update("q", "")}>
              검색어 지우기
              <ArrowRight size={15} />
            </button>
          </div>
        )}
      </div>
      {source && (
        <Modal
          drawer
          title={source.title + " · 근거"}
          close={() => setSourceId(null)}
        >
          <div className="p-modal-body">
            <Source benefit={source} />
          </div>
        </Modal>
      )}
      {form && (
        <Modal
          title={form.title}
          subtitle="양식 준비 가이드 · 공식 양식 아님"
          close={() => setForm(null)}
        >
          <div className="p-modal-body">
            <p>{form.description}</p>
            <h3>먼저 정리할 항목</h3>
            <ol className="p-number-list">
              {form.fields.map((field) => (
                <li key={field}>{field}</li>
              ))}
            </ol>
            <Note>
              공식 양식의 파일·버전·제출 경로는 아직 연결되지 않았습니다. 실제
              서식은 담당 부서에서 확인해 주세요.
            </Note>
            <Link
              className="p-button p-secondary"
              to="/workspace/preparations"
              onClick={() => setForm(null)}
            >
              나의 준비 목록 보기
              <ArrowRight size={15} />
            </Link>
          </div>
        </Modal>
      )}
    </>
  );
}

export function Preparations() {
  const { benefits, preparations, toggleCheck, removePreparation, select } =
    useWorkspace();
  const total = preparations.reduce(
    (sum, draft) =>
      sum +
      (benefits.find((b) => b.id === draft.benefitId)?.checklist.length ?? 0),
    0,
  );
  const complete = preparations.reduce(
    (sum, draft) => sum + draft.checked.length,
    0,
  );
  return (
    <>
      <Heading
        label="MY PREPARATIONS"
        title="준비는 차근차근, 빠짐없이."
        action={
          <Link className="p-button p-secondary" to="/workspace/benefits">
            혜택 더 찾아보기
            <ArrowUpRight size={16} />
          </Link>
        }
      >
        담아둔 혜택의 조건·증빙·양식을 확인하세요. 실제 신청이나 제출 단계는
        아닙니다.
      </Heading>
      {preparations.length > 0 ? (
        <>
          <div className="p-preparation-summary">
            <span>
              <FileCheck2 size={23} />
              <strong>{preparations.length}건 준비 중</strong>
            </span>
            <span>
              확인한 항목{" "}
              <b>
                {complete} / {total}
              </b>
            </span>
            <progress
              max={total || 1}
              value={complete}
              aria-label="전체 준비 진행률"
            />
          </div>
          <div className="p-preparation-grid">
            {preparations.map((draft) => {
              const benefit = benefits.find((b) => b.id === draft.benefitId);
              if (!benefit) return null;
              const done = draft.checked.length === benefit.checklist.length;
              return (
                <article className="p-preparation-card" key={draft.benefitId}>
                  <header>
                    <BenefitIcon benefit={benefit} />
                    <div>
                      <small>{benefit.category}</small>
                      <h2>{benefit.title}</h2>
                    </div>
                    <button
                      className="p-icon-button"
                      aria-label={benefit.title + " 준비 목록에서 삭제"}
                      onClick={() => removePreparation(benefit.id)}
                    >
                      <Trash2 size={18} />
                    </button>
                  </header>
                  <div className="p-preparation-state">
                    <Badge status={benefit.status} />
                    <span>
                      {done ? "예시 체크 완료" : "항목 확인 중"} ·{" "}
                      {draft.checked.length}/{benefit.checklist.length}
                    </span>
                  </div>
                  <div className="p-checklist">
                    {benefit.checklist.map((item, index) => (
                      <label
                        key={item}
                        className={
                          draft.checked.includes(index) ? "checked" : ""
                        }
                      >
                        <input
                          type="checkbox"
                          checked={draft.checked.includes(index)}
                          onChange={() => toggleCheck(benefit.id, index)}
                        />
                        <span className="p-custom-check">
                          {draft.checked.includes(index) && <Check size={14} />}
                        </span>
                        <span>{item}</span>
                      </label>
                    ))}
                  </div>
                  {done && (
                    <div className="p-prepared-note">
                      <CheckCircle2 size={16} />
                      확인 표시만 완료되었습니다. 회사의 검토·승인은 별도입니다.
                    </div>
                  )}
                  <footer>
                    <button
                      className="p-text-link"
                      onClick={() => select(benefit.id)}
                    >
                      조건·근거 다시 보기
                      <ChevronRight size={15} />
                    </button>
                    <Link
                      className="p-text-link"
                      to={
                        "/workspace/library?tab=forms&q=" +
                        encodeURIComponent(
                          benefit.category === "휴가·휴직" ? "휴가" : "",
                        )
                      }
                    >
                      양식 확인
                      <ArrowUpRight size={15} />
                    </Link>
                  </footer>
                </article>
              );
            })}
          </div>
          <Note>
            확인 표시는 현재 탭에만 저장됩니다. 모든 항목을 체크해도 실제 자격
            확정·신청·지급·승인이 이루어지지 않습니다.
          </Note>
        </>
      ) : (
        <Empty title="준비할 혜택을 담아보세요">
          혜택 상세에서 ‘신청 준비에 담기’를 선택하면 필요한 항목을 이곳에서
          확인할 수 있습니다.
        </Empty>
      )}
    </>
  );
}

export function Profile() {
  const { profile, saveProfile, revoke, reset } = useWorkspace();
  const [draft, setDraft] = useState<ProfileType>(profile);
  const [revoked, setRevoked] = useState(false);
  function submit(event: FormEvent) {
    event.preventDefault();
    saveProfile(draft);
    setDraft(consented(draft));
    setRevoked(false);
  }
  return (
    <>
      <Heading
        label="MY INFORMATION & PRIVACY"
        title="필요한 정보만, 내가 선택해요."
      >
        실제 개인정보 대신 미리 정해진 가상 조건을 선택합니다. 선택하지 않은
        정보는 추천에 사용하지 않아요.
      </Heading>
      <div className="p-profile-layout">
        <form onSubmit={submit} className="p-profile-form">
          <section className="p-profile-section">
            <header>
              <span>01</span>
              <div>
                <h2>근무 조건</h2>
                <p>고용형태와 근속 조건에 맞는 혜택을 살펴봐요.</p>
              </div>
              <label className="p-switch">
                <input
                  type="checkbox"
                  aria-label="가상 근무 정보 활용 동의"
                  checked={draft.employment_consent}
                  onChange={(event) =>
                    setDraft({
                      ...draft,
                      employment_consent: event.target.checked,
                    })
                  }
                />
                <span />
                <b>{draft.employment_consent ? "동의" : "미동의"}</b>
              </label>
            </header>
            <fieldset disabled={!draft.employment_consent}>
              <legend className="p-sr-only">가상 근무 조건 선택</legend>
              <label>
                고용형태
                <select
                  aria-label="가상 고용형태"
                  value={draft.employment_type ?? ""}
                  onChange={(event) =>
                    setDraft({
                      ...draft,
                      employment_type: (event.target.value ||
                        null) as ProfileType["employment_type"],
                    })
                  }
                >
                  <option value="">선택 안 함</option>
                  {Object.entries(EMPLOYMENT_LABEL).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label} · 가상
                    </option>
                  ))}
                </select>
              </label>
              <label>
                입사일
                <select
                  aria-label="가상 입사일"
                  value={draft.hire_date ?? ""}
                  onChange={(event) =>
                    setDraft({
                      ...draft,
                      hire_date: event.target.value || null,
                    })
                  }
                >
                  <option value="">선택 안 함</option>
                  <option value="2019-03-11">2019.03.11 · 7년 근속 예시</option>
                  <option value="2026-08-01">
                    2026.08.01 · 신규 입사 예시
                  </option>
                  <option value="2010-03-01">2010.03.01 · 장기근속 예시</option>
                </select>
              </label>
            </fieldset>
          </section>
          <section className="p-profile-section">
            <header>
              <span>02</span>
              <div>
                <h2>
                  가족 조건 <small>선택</small>
                </h2>
                <p>이름·주민번호 없이 연령과 가구원 수만 사용해요.</p>
              </div>
              <label className="p-switch">
                <input
                  type="checkbox"
                  aria-label="가상 가족 정보 활용 동의"
                  checked={draft.family_consent}
                  onChange={(event) =>
                    setDraft({ ...draft, family_consent: event.target.checked })
                  }
                />
                <span />
                <b>{draft.family_consent ? "동의" : "미동의"}</b>
              </label>
            </header>
            <fieldset disabled={!draft.family_consent}>
              <legend className="p-sr-only">가상 가족 조건 선택</legend>
              <label>
                자녀 나이
                <select
                  aria-label="가상 자녀 나이"
                  value={
                    draft.children_ages === null
                      ? "unknown"
                      : draft.children_ages.join(",")
                  }
                  onChange={(event) =>
                    setDraft({
                      ...draft,
                      children_ages:
                        event.target.value === "unknown"
                          ? null
                          : event.target.value
                            ? event.target.value.split(",").map(Number)
                            : [],
                    })
                  }
                >
                  <option value="unknown">선택 안 함</option>
                  <option value="5,9">만 5세·9세 자녀 · 가상</option>
                  <option value="5">만 5세 자녀 · 가상</option>
                  <option value="15">만 15세 자녀 · 가상</option>
                  <option value="">자녀 없음 · 가상</option>
                </select>
              </label>
              <label>
                가구원 수
                <select
                  aria-label="가상 가구원 수"
                  value={draft.household_size ?? ""}
                  onChange={(event) =>
                    setDraft({
                      ...draft,
                      household_size: event.target.value
                        ? Number(event.target.value)
                        : null,
                    })
                  }
                >
                  <option value="">선택 안 함</option>
                  {[1, 2, 3, 4, 5].map((size) => (
                    <option key={size} value={size}>
                      {size}명 · 가상
                    </option>
                  ))}
                </select>
              </label>
            </fieldset>
          </section>
          <div className="p-profile-actions">
            <span>예시 기준일 2026.11.07</span>
            <button className="p-button" type="submit">
              선택한 조건 반영
              <Check size={17} />
            </button>
          </div>
        </form>
        <aside className="p-privacy-panel">
          <span className="p-privacy-icon">
            <ShieldCheck size={27} />
          </span>
          <h2>
            내 정보의 주인은
            <br />
            나니까요.
          </h2>
          <ul>
            <li>동의 항목만 추천에 활용</li>
            <li>이름·주민번호·증빙 파일 미수집</li>
            <li>현재 탭의 메모리에만 유지</li>
            <li>새로고침 시 가상 기본값으로 초기화</li>
          </ul>
          <div>
            <h3>동의를 철회하면</h3>
            <p>
              추천 조건·대화·준비 정보를 즉시 비웁니다. 저장한 혜택 이름은 남아
              있어도 개인 조건을 적용하지 않아요.
            </p>
            <button
              className="p-revoke-button"
              type="button"
              onClick={() => {
                revoke();
                setDraft(BLANK_PROFILE);
                setRevoked(true);
              }}
            >
              동의 철회·예시 정보 비우기
              <Trash2 size={15} />
            </button>
            {revoked && (
              <p role="status" className="p-revoked">
                <CheckCircle2 size={16} />
                철회했습니다. 조건이 필요한 혜택은 ‘추가 확인’으로 표시됩니다.
              </p>
            )}
          </div>
          <button
            className="p-text-link"
            type="button"
            onClick={() => {
              reset();
              setDraft({
                employment_consent: true,
                family_consent: true,
                hire_date: "2019-03-11",
                employment_type: "regular",
                children_ages: [5, 9],
                household_size: 4,
              });
              setRevoked(false);
            }}
          >
            처음 가상 조건으로 복원
            <ArrowRight size={14} />
          </button>
        </aside>
      </div>
      <Note>
        가상 동의 화면입니다. 실제 서비스의 동의 이력 저장·철회 처리·보존 기간
        정책은 백엔드 연결 후 별도 검증이 필요합니다.
      </Note>
    </>
  );
}
