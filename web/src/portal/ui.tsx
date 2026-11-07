import {
  useEffect,
  useId,
  useRef,
  type ReactNode,
  type KeyboardEvent,
} from "react";
import { Link } from "react-router-dom";
import {
  ArrowUpRight,
  Award,
  BookOpen,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleHelp,
  Heart,
  House,
  Leaf,
  ShieldCheck,
  X,
} from "lucide-react";
import type { PreviewBenefit, Status } from "../workspace/types";

export const STATUS = {
  eligible: "조건 충족",
  needs_review: "추가 확인",
  ineligible: "해당 없음",
};
export function Logo() {
  return (
    <span className="p-logo">
      <span className="p-logomark" aria-hidden="true">
        <i />
        <i />
      </span>
      <b>
        K:LINK<span>직원 포털</span>
      </b>
    </span>
  );
}
export function BenefitIcon({ benefit }: { benefit: PreviewBenefit }) {
  const Icon =
    {
      family: Heart,
      leave: Leaf,
      learning: BookOpen,
      award: Award,
      school: BookOpen,
      home: House,
    }[benefit.icon] ?? Heart;
  return (
    <span className={`p-benefit-icon ${benefit.icon}`}>
      <Icon size={22} strokeWidth={1.6} />
    </span>
  );
}
export function Badge({ status }: { status: Status }) {
  const Icon = status === "eligible" ? CheckCircle2 : CircleHelp;
  return (
    <span className={`p-status ${status}`}>
      <Icon size={13} />
      {STATUS[status]}
    </span>
  );
}
export function Modal({
  title,
  subtitle,
  children,
  close,
  drawer = false,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
  close: () => void;
  drawer?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const id = useId();
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const dialog = ref.current;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    dialog?.showModal();
    return () => {
      dialog?.close();
      document.body.style.overflow = overflow;
      previous?.focus();
    };
  }, []);
  function trapFocus(event: KeyboardEvent<HTMLDialogElement>) {
    if (event.key !== "Tab") return;
    const items = Array.from(
      ref.current?.querySelectorAll<HTMLElement>(
        'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])',
      ) ?? [],
    ).filter((item) => item.checkVisibility());
    const first = items[0],
      last = items[items.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last?.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first?.focus();
    }
  }
  return (
    <dialog
      ref={ref}
      aria-labelledby={id}
      className={`p-modal ${drawer ? "p-drawer" : ""}`}
      onKeyDown={trapFocus}
      onCancel={(event) => {
        event.preventDefault();
        close();
      }}
      onClick={(event) => {
        if (event.target === event.currentTarget) close();
      }}
    >
      <div className="p-modal-surface">
        <header>
          <div>
            <span className="p-kicker">K:LINK · PREVIEW</span>
            <h2 id={id}>{title}</h2>
            {subtitle && <p>{subtitle}</p>}
          </div>
          <button className="p-icon-button" onClick={close} aria-label="닫기">
            <X size={21} />
          </button>
        </header>
        {children}
      </div>
    </dialog>
  );
}
export function Source({ benefit }: { benefit: PreviewBenefit }) {
  return (
    <div className="p-source">
      <div className="p-source-title">
        <BookOpen size={19} />
        <div>
          <strong>화면 검증용 가상 복지 규정</strong>
          <small>{benefit.section} · demo-2026.11.07</small>
        </div>
        <span className="p-label">가상 자료</span>
      </div>
      <blockquote>{benefit.quote}</blockquote>
      <dl className="p-meta">
        <div>
          <dt>출처 ID</dt>
          <dd>DEMO-{benefit.id}</dd>
        </div>
        <div>
          <dt>회사·적용 범위</dt>
          <dd>가상 시연 자료 · KTcs 적용 미확인</dd>
        </div>
        <div>
          <dt>검토 상태</dt>
          <dd>회사 승인 전 · 현행성 미확인</dd>
        </div>
        <div>
          <dt>원본 해시</dt>
          <dd>가상 문구이므로 실제 규정 해시 없음</dd>
        </div>
      </dl>
      <Note>
        이 문구는 실제 회사 규정이 아닙니다. 실제 자격과 금액은 승인된 규정에서
        확인해야 합니다.
      </Note>
    </div>
  );
}
export function Note({ children }: { children: ReactNode }) {
  return (
    <div className="p-note">
      <ShieldCheck size={16} />
      <p>{children}</p>
    </div>
  );
}
export function Heading({
  label,
  title,
  children,
  action,
}: {
  label: string;
  title: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="p-page-heading">
      <div>
        <span className="p-kicker">{label}</span>
        <h1>{title}</h1>
        <p>{children}</p>
      </div>
      {action}
    </div>
  );
}
export function SectionLink({
  to,
  children,
}: {
  to: string;
  children: ReactNode;
}) {
  return (
    <Link className="p-text-link" to={to}>
      {children}
      <ChevronRight size={15} />
    </Link>
  );
}
export function Empty({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="p-empty">
      <span>
        <Check size={26} />
      </span>
      <h2>{title}</h2>
      <p>{children}</p>
      <Link to="/workspace/benefits" className="p-button">
        혜택 둘러보기
        <ArrowUpRight size={16} />
      </Link>
    </div>
  );
}
