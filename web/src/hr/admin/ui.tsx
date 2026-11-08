import type { ReactNode } from "react";
import { ArrowRight, Inbox, RefreshCw } from "lucide-react";
import { Link } from "react-router-dom";
import { CASE_STATES, JOB_STATES } from "../operations";
export function PageTitle({
  eyebrow,
  title,
  description,
  children,
}: {
  eyebrow: string;
  title: string;
  description: string;
  children?: ReactNode;
}) {
  return (
    <header className="ops-page-title">
      <div>
        <p className="ops-eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      <div>{children}</div>
    </header>
  );
}
export function Stat({
  label,
  value,
  note,
  tone = "",
  children,
}: {
  label: string;
  value: ReactNode;
  note: ReactNode;
  tone?: string;
  children?: ReactNode;
}) {
  return (
    <div className={"ops-stat " + tone}>
      <div>
        <span>{label}</span>
        {children}
      </div>
      <strong>{value}</strong>
      <small>{note}</small>
    </div>
  );
}
export function Badge({
  state,
  children,
}: {
  state: string;
  children?: ReactNode;
}) {
  return (
    <span className={"ops-badge " + state}>
      {children ?? JOB_STATES[state] ?? CASE_STATES[state] ?? state}
    </span>
  );
}
export function QueryError({
  error,
  retry,
}: {
  error: Error | null;
  retry?: () => void;
}) {
  return error ? (
    <div className="ops-error" role="alert">
      <span>{error.message}</span>
      {retry && (
        <button onClick={retry}>
          <RefreshCw size={14} />
          다시 불러오기
        </button>
      )}
    </div>
  ) : null;
}
export function Empty({
  title,
  description,
  to,
  action,
}: {
  title: string;
  description: string;
  to?: string;
  action?: string;
}) {
  return (
    <div className="ops-empty">
      <Inbox size={28} />
      <h3>{title}</h3>
      <p>{description}</p>
      {to && (
        <Link to={to}>
          {action ?? "시작하기"}
          <ArrowRight size={14} />
        </Link>
      )}
    </div>
  );
}
export function Loading() {
  return (
    <p className="ops-loading" role="status">
      <RefreshCw size={15} />
      운영 정보를 불러오고 있습니다.
    </p>
  );
}
