import { useState, type FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { Eye, EyeOff } from 'lucide-react'
import { ApiError } from './api/client'
import { useAuth } from './auth/AuthContext'
import { Logo, cx } from './components/ui'

const inputClass =
  'h-[46px] w-full rounded-[10px] border border-line-strong bg-panel px-3.5 text-[15px] outline-none transition-colors placeholder:text-faint focus:border-brand'

export function LoginPage() {
  const { user, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  // 로그인 전에 보려던 화면으로 돌려보낸다
  const from = (location.state as { from?: { pathname: string } } | null)?.from?.pathname ?? '/'
  if (user) return <Navigate to={from} replace />

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (!username.trim() || !password) {
      setError('아이디와 비밀번호를 입력해 주세요.')
      return
    }
    setPending(true)
    setError(null)
    try {
      await login(username, password)
      navigate(from, { replace: true })
    } catch (err) {
      setError(err instanceof ApiError && err.status === 401 ? err.message : '로그인하지 못했어요. 잠시 후 다시 시도해 주세요.')
      setPending(false)
    }
  }

  return (
    <div className="flex h-screen flex-col items-center justify-center gap-6 bg-side px-4">
      <form
        onSubmit={onSubmit}
        noValidate
        className="flex w-full max-w-[400px] flex-col gap-7 rounded-2xl border border-line bg-panel p-10"
      >
        <div className="flex flex-col items-center gap-4 text-center">
          <Logo size={36} />
          <div className="flex flex-col items-center gap-1.5">
            <h1 className="text-[22px] font-semibold">K-LINK</h1>
            <p className="text-sm leading-[1.6] text-pretty text-muted">회사 계정으로 로그인하면 내 권한에 맞는 사내 문서를 검색할 수 있어요.</p>
          </div>
        </div>

        <div className="flex flex-col gap-3">
          <label className="flex flex-col gap-1.5">
            <span className="text-[13px] font-medium text-ink-2">아이디</span>
            <input
              className={inputClass}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="사번 또는 회사 이메일"
              autoComplete="username"
              autoFocus
            />
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="text-[13px] font-medium text-ink-2">비밀번호</span>
            <div className="relative">
              <input
                className={cx(inputClass, 'pr-11')}
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="비밀번호"
                autoComplete="current-password"
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                aria-label={showPassword ? '비밀번호 숨기기' : '비밀번호 보기'}
                className="absolute top-1/2 right-2 flex size-8 -translate-y-1/2 items-center justify-center rounded-md text-faint hover:text-ink-2"
              >
                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
          </label>
          {error && (
            <div role="alert" className="rounded-lg bg-err-bg px-3 py-2 text-[13px] text-err">
              {error}
            </div>
          )}
        </div>

        <button
          type="submit"
          disabled={pending}
          className="h-[46px] rounded-[10px] bg-brand text-[15px] font-semibold text-white transition-colors hover:bg-brand-strong disabled:opacity-60"
        >
          {pending ? '로그인 중…' : '로그인'}
        </button>

        <div className="flex flex-col gap-0.5 border-t border-line pt-[18px] text-[13px] leading-[1.6] text-muted">
          <span>비밀번호를 잊었거나 로그인이 안 되나요?</span>
          <span>
            IT 지원팀 내선 1234 ·{' '}
            <a href="mailto:it-help@company.com" className="whitespace-nowrap text-brand underline underline-offset-2">it-help@company.com</a>
          </span>
        </div>
      </form>
      <div className="text-xs text-faint">대화 내용은 사내 서버에만 저장되며 외부로 전송되지 않습니다.</div>
    </div>
  )
}
