import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowRight,
  CheckCircle2,
  ChevronRight,
  FileCheck2,
  Plus,
  ShieldCheck,
  Trash2,
  X,
} from 'lucide-react'
import { useWorkspace } from './WorkspaceContext'
import {
  handleTabKey,
  BenefitIcon,
  CheckRow,
  EmptyState,
  Modal,
  PageHeading,
  StatusBadge,
} from './components'

export function PreparationsPage() {
  const { preparations, benefits, toggleCheck, removePreparation, select } = useWorkspace()
  const [filter, setFilter] = useState('all'),
    [activeId, setActiveId] = useState<string | null>(null),
    [deleteId, setDeleteId] = useState<string | null>(null)
  const entries = preparations
    .map((d) => ({
      ...d,
      benefit: benefits.find((b) => b.id === d.benefitId)!,
    }))
    .filter((d) => d.benefit)
  const done = entries.filter((d) => d.checked.length === d.benefit.checklist.length)
  const shown = entries.filter(
    (d) =>
      filter === 'all' ||
      (filter === 'done'
        ? d.checked.length === d.benefit.checklist.length
        : d.checked.length < d.benefit.checklist.length),
  )
  const active = entries.find((d) => d.benefitId === activeId)
  return (
    <>
      <PageHeading
        eyebrow="MY PREPARATIONS"
        title="차근차근, 신청 준비"
        description="필요한 조건과 서류를 확인하면서 신청 전 준비를 이어가세요."
        action={
          <Link className="kl-button primary" to="/workspace/benefits">
            <Plus size={16} />
            혜택 찾아 담기
          </Link>
        }
      />
      <section className="kl-preparation-overview">
        <span>
          <FileCheck2 size={28} />
        </span>
        <div>
          <h2>
            {entries.length
              ? `${entries.length}건의 신청을 준비하고 있어요.`
              : '아직 준비 중인 신청이 없어요.'}
          </h2>
          <p>체크리스트를 모두 확인해도 실제 신청·결재는 제출되지 않아요.</p>
        </div>
        <div>
          <strong>
            {done.length}
            <small> / {entries.length}</small>
          </strong>
          <span>항목 확인 완료</span>
        </div>
      </section>
      <div
        className="kl-tabbar"
        role="tablist"
        onKeyDown={handleTabKey}
        aria-label="신청 준비 상태"
      >
        {[
          { id: 'all', label: '전체', count: entries.length },
          {
            id: 'progress',
            label: '준비 중',
            count: entries.length - done.length,
          },
          { id: 'done', label: '항목 확인 완료', count: done.length },
        ].map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={filter === t.id}
            tabIndex={filter === t.id ? 0 : -1}
            onClick={() => setFilter(t.id)}
          >
            {t.label}
            <span>{t.count}</span>
          </button>
        ))}
      </div>
      {shown.length ? (
        <div className="kl-preparation-list">
          {shown.map((d) => (
            <article key={d.benefitId} className="kl-preparation-card">
              <BenefitIcon benefit={d.benefit} />
              <div className="kl-preparation-copy">
                <span
                  className={`kl-prep-status ${d.checked.length === d.benefit.checklist.length ? 'complete' : ''}`}
                >
                  {d.checked.length === d.benefit.checklist.length
                    ? '항목 확인 완료'
                    : '신청 준비 중'}
                </span>
                <h2>{d.benefit.title}</h2>
                <p>{d.benefit.value} · 예시 혜택 · 실제 미제출</p>
                <div className="kl-prep-progress">
                  <span>
                    <i
                      style={{
                        width: `${(d.checked.length / d.benefit.checklist.length) * 100}%`,
                      }}
                    />
                  </span>
                  <small>
                    {d.checked.length}/{d.benefit.checklist.length} 항목 확인
                  </small>
                </div>
              </div>
              <div className="kl-preparation-actions">
                <button
                  aria-label={`${d.benefit.title} 준비 목록 삭제`}
                  className="kl-icon-button"
                  onClick={() => setDeleteId(d.benefitId)}
                >
                  <Trash2 size={16} />
                </button>
                <button className="kl-button secondary" onClick={() => setActiveId(d.benefitId)}>
                  이어서 준비하기
                  <ChevronRight size={15} />
                </button>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <EmptyState
          title={entries.length ? '이 상태의 준비 목록이 없어요' : '첫 번째 혜택을 준비해 볼까요?'}
          description={
            entries.length
              ? '다른 상태를 선택해 준비한 내용을 확인하세요.'
              : '혜택 상세에서 신청 준비를 시작하면 여기에 모아드려요.'
          }
          icon={FileCheck2}
        >
          <Link className="kl-button primary" to="/workspace/benefits">
            나의 혜택 찾아보기
            <ArrowRight size={15} />
          </Link>
        </EmptyState>
      )}
      <div className="kl-inline-note">
        <ShieldCheck size={17} />
        <p>
          본 화면은 준비 과정을 체험하는 시안입니다. 실제 제출은 공식 양식·업무 시스템·사용 권한이
          연결된 뒤 제공해요.
        </p>
      </div>
      {active && (
        <Modal
          title={active.benefit.title}
          subtitle="신청 전 준비 체크리스트"
          close={() => setActiveId(null)}
          drawer
        >
          <div className="kl-modal-body">
            <div className="kl-prep-detail-status">
              <StatusBadge status={active.benefit.status} />
              <span className="kl-tag">실제 미제출</span>
            </div>
            <h3 className="kl-subheading">준비할 내용을 하나씩 확인해요.</h3>
            <p className="kl-body-copy">
              체크는 예시 준비 상태를 기록하는 동작이에요. 증빙 확인이나 담당 부서 승인으로 간주하지
              않아요.
            </p>
            <div className="kl-prep-checks">
              {active.benefit.checklist.map((c, i) => (
                <CheckRow
                  key={c}
                  checked={active.checked.includes(i)}
                  title={c}
                  onChange={() => toggleCheck(active.benefitId, i)}
                />
              ))}
            </div>
            {active.checked.length === active.benefit.checklist.length && (
              <div className="kl-prep-complete" role="status">
                <CheckCircle2 size={22} />
                <div>
                  <strong>준비 항목을 모두 확인했어요.</strong>
                  <p>정식 신청 경로와 회사의 최종 확인이 남아 있어요.</p>
                </div>
              </div>
            )}
            <div className="kl-form-placeholder">
              <FileCheck2 size={23} />
              <div>
                <strong>회사 공식 양식·신청 경로</strong>
                <p>현재 연결 전이에요. 준비 목록은 계속 확인할 수 있어요.</p>
              </div>
            </div>
            <button
              className="kl-button secondary full"
              onClick={() => {
                const id = active.benefitId
                setActiveId(null)
                select(id)
              }}
            >
              혜택 조건과 규정 다시 보기
              <ArrowRight size={15} />
            </button>
          </div>
          <div className="kl-drawer-actions single">
            <button disabled className="kl-button primary full">
              실제 신청 · 업무 시스템 연결 후 가능
            </button>
            <p>현재 회사에 제출되는 내용은 없습니다.</p>
          </div>
        </Modal>
      )}
      {deleteId && (
        <Modal title="준비 목록에서 삭제할까요?" close={() => setDeleteId(null)}>
          <div className="kl-modal-body">
            <p className="kl-body-copy">
              이 혜택의 체크 내역을 삭제해요. 필요하면 혜택 상세에서 다시 시작할 수 있어요.
            </p>
            <div className="kl-confirm-actions">
              <button className="kl-button secondary" onClick={() => setDeleteId(null)}>
                <X size={15} />
                닫기
              </button>
              <button
                className="kl-button danger"
                onClick={() => {
                  removePreparation(deleteId)
                  setDeleteId(null)
                  if (activeId === deleteId) setActiveId(null)
                }}
              >
                준비 목록 삭제
              </button>
            </div>
          </div>
        </Modal>
      )}
    </>
  )
}
