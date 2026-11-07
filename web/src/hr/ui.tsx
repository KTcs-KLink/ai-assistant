import {
  BookOpen,
  CheckCircle2,
  CircleHelp,
  Heart,
  Home,
  Leaf,
  GraduationCap,
  Award,
  ShieldCheck,
} from "lucide-react";
import { Note } from "../portal/ui";
import type { Decision, EvidenceSource, HrBenefit, PolicySource } from "./api";
export const LABELS: Record<Decision, string> = {
  eligible: "조건 충족",
  needs_review: "추가 확인",
  ineligible: "해당 없음",
};
export function DecisionBadge({ benefit }: { benefit: HrBenefit }) {
  return (
    <span className={"p-status " + benefit.status}>
      {benefit.status === "eligible" ? (
        <CheckCircle2 size={13} />
      ) : (
        <CircleHelp size={13} />
      )}{" "}
      {LABELS[benefit.status]}
      {benefit.synthetic ? " · 예시" : ""}
    </span>
  );
}
export function HrIcon({ id }: { id: string }) {
  const Icon =
    {
      childcare: Heart,
      "family-leave": Leaf,
      learning: BookOpen,
      "long-service": Award,
      school: GraduationCap,
      housing: Home,
    }[id] ?? BookOpen;
  return (
    <span className="p-benefit-icon">
      <Icon size={23} />
    </span>
  );
}
export function Company({ company }: { company: string }) {
  return (
    <span className="p-label">
      {company === "KEPCO"
        ? "한국전력 참고자료"
        : company === "DEMO"
          ? "가상 규정"
          : company === "KTCS"
            ? "KTcs 자료"
            : company}
    </span>
  );
}
export function SourceView({
  source,
}: {
  source: EvidenceSource | PolicySource;
}) {
  const reference = "text" in source;
  return (
    <div className="hr-source-view">
      <div className="hr-source-heading">
        <BookOpen size={20} />
        <div>
          <h3>{source.title}</h3>
          <p>{source.section}</p>
        </div>
      </div>
      <Company company={source.company} />
      <Note>
        {source.company === "KEPCO"
          ? "한국전력 공개 대체자료입니다. 실제 KTcs 규정·자격에 적용할 수 있는지 확인되지 않았어요."
          : source.company === "DEMO"
            ? "서버 기능 확인용 가상 규정입니다. 실제 회사 제도나 자격을 뜻하지 않아요."
            : "제공된 회사·버전·검토 범위를 확인해 주세요. 최종 개인 자격·신청 승인은 별도입니다."}
      </Note>
      <h3 className="hr-source-caption">서버에서 조회한 원문</h3>
      <blockquote className="hr-original">
        {reference ? source.text : source.quote}
      </blockquote>
      <dl className="p-meta">
        <div>
          <dt>출처 ID</dt>
          <dd>{source.id}</dd>
        </div>
        <div>
          <dt>버전</dt>
          <dd>{source.version || "확인 필요"}</dd>
        </div>
        {reference && (
          <>
            <div>
              <dt>적용 대상</dt>
              <dd>{source.employee_scope}</dd>
            </div>
            <div>
              <dt>사람 승인</dt>
              <dd>
                {source.human_approved
                  ? "서버의 승인 상태 확인"
                  : "독립된 사람 승인 전"}
              </dd>
            </div>
            <div>
              <dt>현행성</dt>
              <dd>
                {source.effective_status === "UNVERIFIED"
                  ? "미확인"
                  : source.effective_status}
              </dd>
            </div>
            <div>
              <dt>KTcs 적용</dt>
              <dd>
                {source.ktcs_applicable ? "별도 적용 범위 확인" : "미확인"}
              </dd>
            </div>
          </>
        )}
      </dl>
      <details className="hr-integrity">
        <summary>원문 식별 정보</summary>
        <p>본문 SHA-256</p>
        <code>{source.sha256}</code>
        {reference && source.source_file_sha256 && (
          <>
            <p>원본 파일 SHA-256</p>
            <code>{source.source_file_sha256}</code>
          </>
        )}
      </details>
    </div>
  );
}
export function Unavailable({
  title = "조회하지 못했어요",
  retry,
}: {
  title?: string;
  retry?: () => void;
}) {
  return (
    <div className="hr-unavailable">
      <ShieldCheck size={26} />
      <h2>{title}</h2>
      <p>
        확인되지 않은 내용을 대신 표시하지 않습니다. 연결을 확인한 뒤 다시
        조회해 주세요.
      </p>
      {retry && (
        <button className="p-button p-secondary" onClick={retry}>
          다시 조회
        </button>
      )}
    </div>
  );
}
export async function attempt(promise: Promise<unknown>) {
  try {
    await promise;
    return true;
  } catch {
    return false;
  }
}
