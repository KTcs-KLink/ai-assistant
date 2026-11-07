import { useEffect, useState, type FormEvent } from 'react'
import {
  ArrowRight,
  Bell,
  CheckCircle2,
  ChevronRight,
  Heart,
  RotateCcw,
  ShieldCheck,
  SlidersHorizontal,
  UserRound,
  Users,
  X,
} from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import { useWorkspace } from './WorkspaceContext'
import { CheckRow, Modal, PageHeading } from './components'
import { BLANK_PROFILE, INITIAL_PROFILE, PREVIEW_DATE } from './model'
import type { Profile } from './types'

export function ProfilePage() {
  const navigate = useNavigate()
  const { profile, saveProfile, revoke, reset, announce } = useWorkspace()
  const [draft, setDraft] = useState<Profile>(profile),
    [ages, setAges] = useState(profile.children_ages?.join(', ') ?? ''),
    [none, setNone] = useState(profile.children_ages?.length === 0)
  const [error, setError] = useState(''),
    [revokeOpen, setRevokeOpen] = useState(false),
    [notifications, setNotifications] = useState(false)
  useEffect(() => {
    setDraft(profile)
    setAges(profile.children_ages?.join(', ') ?? '')
    setNone(profile.children_ages?.length === 0)
  }, [profile])
  function submit(e: FormEvent) {
    e.preventDefault()
    setError('')
    const tokens = ages.split(',').map((x) => x.trim())
    let children: number[] | null = draft.family_consent
      ? none
        ? []
        : ages.trim()
          ? tokens.map(Number)
          : null
      : null
    if (
      draft.family_consent &&
      !none &&
      ages.trim() &&
      (tokens.length > 10 || tokens.some((t) => !/^\d+$/.test(t) || Number(t) > 30))
    ) {
      setError('자녀 나이는 0~30세 정수로 입력해 주세요. 예: 5, 9')
      return
    }
    if (
      draft.employment_consent &&
      draft.hire_date &&
      (draft.hire_date < '1960-01-01' || draft.hire_date > PREVIEW_DATE)
    ) {
      setError('입사일을 예시 기준일 이전으로 입력해 주세요.')
      return
    }
    if (none) children = []
    saveProfile({ ...draft, children_ages: children })
    navigate('/workspace/benefits')
  }
  function discard() {
    setDraft(profile)
    setAges(profile.children_ages?.join(', ') ?? '')
    setNone(profile.children_ages?.length === 0)
    setError('')
    announce('저장된 예시 조건으로 돌아왔어요.')
  }
  return (
    <>
      <PageHeading
        eyebrow="MY INFORMATION"
        title="내 정보·동의 관리"
        description="추천에 사용할 조건을 직접 선택하고, 언제든 바꿀 수 있어요."
      />
      <div className="kl-profile-columns">
        <div>
          <section className="kl-profile-identity">
            <span className="kl-avatar large">K</span>
            <div>
              <h2>
                체험 직원<span className="kl-tag">가상 프로필</span>
              </h2>
              <p>실제 사번·이름·주민등록번호를 입력하지 않는 화면이에요.</p>
            </div>
            <ShieldCheck size={23} />
          </section>
          <form className="kl-profile-form" onSubmit={submit}>
            <section className="kl-panel">
              <div className="kl-form-section-title">
                <span>
                  <UserRound size={20} />
                </span>
                <div>
                  <h2>근무 정보</h2>
                  <p>근속기간과 고용 조건에 맞는 혜택을 찾는 데 사용해요.</p>
                </div>
              </div>
              <CheckRow
                checked={draft.employment_consent}
                title="근무 정보를 추천에 사용하는 데 동의해요"
                description="고용형태·입사일만 사용해요. HR에서 확인된 정보로 간주하지 않습니다."
                onChange={() =>
                  setDraft({
                    ...draft,
                    employment_consent: !draft.employment_consent,
                  })
                }
              />
              <fieldset disabled={!draft.employment_consent}>
                <label>
                  고용형태
                  <select
                    value={draft.employment_type ?? ''}
                    onChange={(e) =>
                      setDraft({
                        ...draft,
                        employment_type: (e.target.value as Profile['employment_type']) || null,
                      })
                    }
                  >
                    <option value="">선택하지 않음</option>
                    <option value="regular">정규직</option>
                    <option value="fixed_term">기간제</option>
                    <option value="part_time">시간제</option>
                  </select>
                </label>
                <label>
                  입사일
                  <input
                    type="date"
                    value={draft.hire_date ?? ''}
                    min="1960-01-01"
                    max={PREVIEW_DATE}
                    onChange={(e) => setDraft({ ...draft, hire_date: e.target.value || null })}
                  />
                  <small>예시 기준일: 2026.11.07</small>
                </label>
              </fieldset>
            </section>
            <section className="kl-panel">
              <div className="kl-form-section-title">
                <span className="pink">
                  <Heart size={20} />
                </span>
                <div>
                  <h2>
                    가족 정보 <small>선택</small>
                  </h2>
                  <p>가족·육아 혜택을 찾을 때 필요한 조건만 사용해요.</p>
                </div>
              </div>
              <CheckRow
                checked={draft.family_consent}
                title="가족 정보를 추천에 사용하는 데 동의해요"
                description="가구원 수와 자녀 나이만 사용해요. 이름과 생년월일은 받지 않아요."
                onChange={() => setDraft({ ...draft, family_consent: !draft.family_consent })}
              />
              <fieldset disabled={!draft.family_consent}>
                <label>
                  가구원 수
                  <input
                    type="number"
                    min={1}
                    max={20}
                    value={draft.household_size ?? ''}
                    placeholder="선택 입력"
                    onChange={(e) =>
                      setDraft({
                        ...draft,
                        household_size: e.target.value ? Number(e.target.value) : null,
                      })
                    }
                  />
                  <small>본인을 포함한 가구원 수를 입력해요.</small>
                </label>
                <label>
                  자녀 만 나이
                  <input
                    value={none ? '' : ages}
                    disabled={none}
                    placeholder="예: 5, 9"
                    onChange={(e) => setAges(e.target.value)}
                  />
                  <small>쉼표로 구분해요. 비우면 미제공으로 처리해요.</small>
                </label>
                <label className="kl-inline-check">
                  <input
                    type="checkbox"
                    checked={none}
                    onChange={(e) => setNone(e.target.checked)}
                  />
                  자녀 없음
                </label>
              </fieldset>
            </section>
            {error && (
              <div className="kl-form-error" role="alert">
                {error}
              </div>
            )}
            <div className="kl-form-save">
              <button type="button" className="kl-button secondary" onClick={discard}>
                변경 취소
              </button>
              <button className="kl-button primary" type="submit">
                조건 저장하고 혜택 다시 보기
                <CheckCircle2 size={16} />
              </button>
            </div>
          </form>
          <section className="kl-panel kl-notification-setting">
            <div>
              <span>
                <Bell size={19} />
              </span>
              <div>
                <h2>혜택 알림</h2>
                <p>알림 설정 화면의 동작을 미리 살펴봐요. 실제 알림은 발송되지 않아요.</p>
              </div>
            </div>
            <button
              className={`kl-switch ${notifications ? 'on' : ''}`}
              role="switch"
              aria-checked={notifications}
              aria-label="혜택 알림 미리보기"
              onClick={() => {
                setNotifications(!notifications)
                announce('알림 설정의 미리보기 상태를 변경했어요. 실제 발송은 연결 전이에요.')
              }}
            >
              <span />
            </button>
          </section>
          <button className="kl-revoke-link" onClick={() => setRevokeOpen(true)}>
            모든 동의 철회 및 조건 삭제
            <ChevronRight size={14} />
          </button>
        </div>
        <aside className="kl-profile-guide">
          <section className="kl-panel">
            <span className="kl-guide-icon">
              <ShieldCheck size={25} />
            </span>
            <h2>
              내 정보는
              <br />
              내가 선택한 만큼만.
            </h2>
            <p>
              동의하지 않은 조건으로 혜택을 판단하지 않아요. 동의를 끄고 저장하면 해당 예시 정보를
              삭제해요.
            </p>
            <ul>
              <li>
                <CheckCircle2 size={14} />
                필요한 조건만 선택해요.
              </li>
              <li>
                <CheckCircle2 size={14} />
                미제공과 해당 없음을 구분해요.
              </li>
              <li>
                <CheckCircle2 size={14} />
                언제든 철회·삭제할 수 있어요.
              </li>
            </ul>
            <div className="kl-profile-storage-note">
              시안의 정보는 현재 화면의 메모리에만 유지돼요. 새로고침하면 처음 예시로 돌아갑니다.
            </div>
          </section>
          <section className="kl-profile-restart">
            <SlidersHorizontal size={21} />
            <h3>다른 조건으로 비교해 볼까요?</h3>
            <p>고용형태나 자녀 나이를 바꾸면 추천 결과가 어떻게 달라지는지 볼 수 있어요.</p>
            <button
              className="kl-text-link"
              onClick={() => {
                reset()
                setDraft(INITIAL_PROFILE)
                setError('')
              }}
            >
              <RotateCcw size={14} />
              처음 예시로 초기화
            </button>
          </section>
          <Link className="kl-profile-back" to="/workspace/benefits">
            <Users size={18} />내 혜택으로 돌아가기
            <ArrowRight size={15} />
          </Link>
        </aside>
      </div>
      {revokeOpen && (
        <Modal title="동의를 철회하고 정보를 삭제할까요?" close={() => setRevokeOpen(false)}>
          <div className="kl-modal-body">
            <div className="kl-revoke-symbol">
              <ShieldCheck size={30} />
            </div>
            <p className="kl-body-copy">
              입사일·고용형태·가족 조건과 신청 준비 기록을 지워요. 정보를 다시 제공하기 전에는 해당
              조건을 확인할 수 없는 상태로 안내합니다.
            </p>
            <div className="kl-confirm-actions">
              <button className="kl-button secondary" onClick={() => setRevokeOpen(false)}>
                <X size={15} />
                닫기
              </button>
              <button
                className="kl-button danger"
                onClick={() => {
                  revoke()
                  setDraft(BLANK_PROFILE)
                  setAges('')
                  setNone(false)
                  setError('')
                  setRevokeOpen(false)
                }}
              >
                동의 철회 및 삭제
              </button>
            </div>
          </div>
        </Modal>
      )}
    </>
  )
}
