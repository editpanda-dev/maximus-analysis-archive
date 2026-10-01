import { useState, useEffect, useRef } from 'react'

// ─── Data ────────────────────────────────────────────────────────────────────

interface Destination {
  rank: number; name: string; district: string; time: number
  cost: string; score: number; scoreLabel: string
  tags: string[]; reason: string
  detail: { signal: string; method: string; vintage: string }
}

const DESTINATIONS: Destination[] = [
  { rank: 1, name: '성수동', district: '성동구', time: 27, cost: '1,650원', score: 94, scoreLabel: '매우 적합',
    tags: ['주말 저녁 식사 패턴 우수', '상권 활력 높음'],
    reason: '동일 시간대·조건의 관측 유입 신호가 강하고 상권 활동성 지표가 높게 집계됨.',
    detail: { signal: '동일 조건 집계 유입 (출발지 동 × 목적지 동 × 목적 × 시간대)', method: 'F0-public-rule · 공개 데이터 규칙 기반', vintage: '관측 기간 감사 필요 · 실시간 아님' } },
  { rank: 2, name: '연남동', district: '마포구', time: 29, cost: '1,650원', score: 87, scoreLabel: '적합',
    tags: ['식사 목적 적합', '동일 조건 유입 신호'],
    reason: '식사 목적 방문 관측 비율이 높으며 주말 저녁 유입이 꾸준히 관측됨.',
    detail: { signal: '목적별 집계 방문 비율', method: 'F0-public-rule', vintage: '관측 기간 감사 필요' } },
  { rank: 3, name: '을지로', district: '중구', time: 25, cost: '1,250원', score: 83, scoreLabel: '적합',
    tags: ['접근성 우수', '저녁 시간대 활동성'],
    reason: '이동 시간이 짧고 저녁 시간대 상업 활동성 집계가 안정적으로 관측됨.',
    detail: { signal: '이동시간 + 시간대별 활동성 집계', method: 'F0-public-rule', vintage: '관측 기간 감사 필요' } },
  { rank: 4, name: '건대입구', district: '광진구', time: 22, cost: '1,450원', score: 79, scoreLabel: '양호',
    tags: ['이동시간 부담 낮음', '다양한 식사 선택지'],
    reason: '가장 짧은 이동 시간으로 도달 가능하며 식사 업종 다양성이 높게 관측됨.',
    detail: { signal: '이동시간 최단 + 업종 다양성 집계', method: 'F0-public-rule', vintage: '관측 기간 감사 필요' } },
  { rank: 5, name: '망원동', district: '마포구', time: 30, cost: '1,650원', score: 71, scoreLabel: '양호',
    tags: ['숨은 목적지 후보', '기대 대비 유입 우수'],
    reason: '검색 빈도 대비 실제 관측 유입이 상대적으로 높아 과소평가된 후보로 분류됨.',
    detail: { signal: '기대 대비 관측 유입 비율', method: 'F0-public-rule', vintage: '관측 기간 감사 필요' } },
]

// Demo fixtures only: purpose changes the ranking basis and explanation. Replace with
// audited public-transport and commercial-area data before any operational release.
const PURPOSE_RANKING: Record<string, { order: string[]; tags: string[]; reason: string }> = {
  '식사': { order: ['성수동', '연남동', '을지로', '건대입구', '망원동'], tags: ['식사 목적 적합', '주말 저녁 유입 신호'], reason: '식사 목적과 선택한 시간대의 집계 신호를 우선 반영한 데모 결과입니다.' },
  '카페': { order: ['연남동', '망원동', '성수동', '건대입구', '을지로'], tags: ['카페 탐색 적합', '체류형 상권 신호'], reason: '카페 목적의 상권 다양성과 시간대별 집계 신호를 우선 반영한 데모 결과입니다.' },
  '데이트': { order: ['성수동', '을지로', '연남동', '망원동', '건대입구'], tags: ['데이트 목적 적합', '복합 활동성 신호'], reason: '데이트 목적에서 필요한 복합 활동성과 선택 시간대 신호를 우선 반영한 데모 결과입니다.' },
  '쇼핑': { order: ['건대입구', '성수동', '을지로', '연남동', '망원동'], tags: ['쇼핑 목적 적합', '상권 선택지 신호'], reason: '쇼핑 목적의 선택지 다양성과 이동 부담을 함께 반영한 데모 결과입니다.' },
  '문화/전시': { order: ['을지로', '성수동', '건대입구', '연남동', '망원동'], tags: ['문화·전시 목적 적합', '시간대 활동성 신호'], reason: '문화·전시 목적의 접근성과 시간대 활동성 신호를 우선 반영한 데모 결과입니다.' },
  '산책/휴식': { order: ['망원동', '성수동', '연남동', '건대입구', '을지로'], tags: ['산책·휴식 목적 적합', '여유 활동성 신호'], reason: '산책·휴식 목적의 체류 환경과 시간대 신호를 우선 반영한 데모 결과입니다.' },
}

function getDestinationsForPurpose(purpose: string): Destination[] {
  const profile = PURPOSE_RANKING[purpose] ?? PURPOSE_RANKING['식사']
  return profile.order.map((name, index) => {
    const base = DESTINATIONS.find(destination => destination.name === name)!
    return {
      ...base,
      rank: index + 1,
      score: Math.max(61, base.score - index * 4),
      tags: profile.tags,
      reason: profile.reason,
      detail: { ...base.detail, signal: `${purpose} · ${profile.tags.join(' · ')}`, method: 'F0-public-rule · 목적별 fixture', vintage: '데모 fixture · 관측 기간 감사 필요 · 실시간 아님' },
    }
  })
}

// ─── Design tokens ───────────────────────────────────────────────────────────
const C = {
  bg: '#F2F2F7',
  card: '#FFFFFF',
  cobalt: '#3B5BDB',
  cobaltLight: '#EEF2FF',
  cobaltPale: '#F0F4FF',
  navy: '#0D1B4B',
  emerald: '#059669',
  emeraldLight: '#ECFDF5',
  slate: '#8E8E93',
  slateLight: '#C7C7CC',
  border: 'rgba(60,60,67,0.14)',
  separator: 'rgba(60,60,67,0.18)',
  label: '#000000',
  labelSecondary: 'rgba(60,60,67,0.6)',
  labelTertiary: 'rgba(60,60,67,0.36)',
  navBg: 'rgba(242,242,247,0.92)',
  tabBg: 'rgba(255,255,255,0.92)',
}

// ─── Logo SVG ─────────────────────────────────────────────────────────────────
function PinIcon({ size = 32 }: { size?: number }) {
  return (
    <svg viewBox="0 0 52 68" width={size * 52 / 68} height={size} fill="none">
      <path d="M26 2C17.716 2 11 8.716 11 17c0 11.5 15 27 15 27s15-15.5 15-27C41 8.716 34.284 2 26 2z"
        fill="url(#pg)" />
      <circle cx="26" cy="16.5" r="5.5" fill="white" />
      <path d="M17 40 Q9 48 15 56 Q21 63 26 60 Q31 57 28 65"
        stroke="url(#rg)" strokeWidth="4.5" strokeLinecap="round" fill="none" />
      <line x1="43" y1="10" x2="49" y2="7" stroke="#34D399" strokeWidth="2.5" strokeLinecap="round" />
      <line x1="45" y1="17" x2="52" y2="17" stroke="#34D399" strokeWidth="2.5" strokeLinecap="round" />
      <line x1="43" y1="24" x2="49" y2="27" stroke="#34D399" strokeWidth="2.5" strokeLinecap="round" />
      <defs>
        <linearGradient id="pg" x1="11" y1="2" x2="41" y2="44" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#82B4FF" />
          <stop offset="100%" stopColor="#3B5BDB" />
        </linearGradient>
        <linearGradient id="rg" x1="17" y1="40" x2="28" y2="65" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#6FA3F8" /><stop offset="100%" stopColor="#3B5BDB" />
        </linearGradient>
      </defs>
    </svg>
  )
}

// ─── iOS primitives ───────────────────────────────────────────────────────────
function StatusBar({ light = false }: { light?: boolean }) {
  const [time, setTime] = useState(() => {
    const d = new Date()
    return `${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`
  })
  useEffect(() => {
    const id = setInterval(() => {
      const d = new Date()
      setTime(`${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`)
    }, 10000)
    return () => clearInterval(id)
  }, [])
  const col = light ? 'rgba(255,255,255,0.9)' : '#0D1B4B'
  return (
    <div style={{ height: 50, display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between',
      padding: '0 26px 9px', flexShrink: 0 }}>
      <span style={{ fontSize: 15, fontWeight: 700, color: col, fontFamily: '-apple-system, sans-serif', letterSpacing: '-0.02em' }}>
        {time}
      </span>
      <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
        <svg viewBox="0 0 17 12" width="17" height="12"><g fill={col}>
          <rect x="0" y="8" width="3" height="4" rx="0.7"/>
          <rect x="4.5" y="5" width="3" height="7" rx="0.7"/>
          <rect x="9" y="2.5" width="3" height="9.5" rx="0.7"/>
          <rect x="13.5" y="0" width="3" height="12" rx="0.7"/>
        </g></svg>
        <svg viewBox="0 0 16 12" width="16" height="12" fill="none">
          <path d="M8 9.5a1.5 1.5 0 110 3 1.5 1.5 0 010-3z" fill={col}/>
          <path d="M3.5 6.5a6.5 6.5 0 019 0" stroke={col} strokeWidth="1.5" strokeLinecap="round"/>
          <path d="M0.5 3.5a11 11 0 0115 0" stroke={col} strokeWidth="1.5" strokeLinecap="round"/>
        </svg>
        <div style={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <div style={{ width: 22, height: 11, border: `1.5px solid ${col}`, borderRadius: 3, padding: '1.5px', display: 'flex' }}>
            <div style={{ flex: 0.85, background: col, borderRadius: 1.5 }} />
          </div>
          <div style={{ width: 2, height: 5, background: col, borderRadius: '0 1px 1px 0', opacity: 0.4 }} />
        </div>
      </div>
    </div>
  )
}

function HomeIndicator({ light = false }: { light?: boolean }) {
  return (
    <div style={{ height: 34, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
      <div style={{ width: 134, height: 5, background: light ? 'rgba(255,255,255,0.4)' : C.navy, borderRadius: 3, opacity: 0.2 }} />
    </div>
  )
}

function DynamicIsland() {
  return (
    <div style={{ position: 'absolute', top: 12, left: '50%', transform: 'translateX(-50%)',
      width: 120, height: 34, background: '#000', borderRadius: 20, zIndex: 20 }} />
  )
}

// ─── Segmented Control (iOS style) ───────────────────────────────────────────
function SegmentedControl({ options, value, onChange }: {
  options: string[]; value: string; onChange: (v: string) => void
}) {
  return (
    <div style={{ display: 'flex', background: 'rgba(118,118,128,0.12)', borderRadius: 9, padding: 2, gap: 2 }}>
      {options.map(opt => {
        const active = opt === value
        return (
          <button key={opt} onClick={() => onChange(opt)} style={{
            flex: 1, padding: '6px 4px', fontSize: 13, fontWeight: active ? 600 : 400,
            color: active ? C.navy : C.slate,
            background: active ? '#FFFFFF' : 'transparent',
            border: 'none', borderRadius: 7, cursor: 'pointer',
            fontFamily: "'Noto Sans KR', system-ui, sans-serif",
            letterSpacing: '-0.02em',
            boxShadow: active ? '0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.08)' : 'none',
            transition: 'all 0.15s ease',
          }}>{opt}</button>
        )
      })}
    </div>
  )
}

// ─── iOS form row ─────────────────────────────────────────────────────────────
function FormRow({ label, value, chevron = false }: { label: string; value?: string; chevron?: boolean }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '12px 16px', minHeight: 44 }}>
      <span style={{ fontSize: 15, color: C.label, letterSpacing: '-0.02em', fontWeight: 400 }}>{label}</span>
      <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
        {value && <span style={{ fontSize: 15, color: C.labelSecondary, letterSpacing: '-0.02em' }}>{value}</span>}
        {chevron && <svg viewBox="0 0 8 13" width="8" height="13" fill="none">
          <path d="M1 1.5l5.5 5L1 11.5" stroke="rgba(60,60,67,0.3)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>}
      </div>
    </div>
  )
}

function SectionCard({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <div style={{ background: C.card, borderRadius: 12, overflow: 'hidden',
      boxShadow: '0 1px 0 rgba(0,0,0,0.04)', ...style }}>
      {children}
    </div>
  )
}

function Divider() {
  return <div style={{ height: 1, background: C.separator, marginLeft: 16 }} />
}

// ─── Score ring ───────────────────────────────────────────────────────────────
function ScoreRing({ score, dark = false }: { score: number; dark?: boolean }) {
  const c = score >= 90 ? '#34D399' : score >= 80 ? (dark ? '#818CF8' : C.cobalt) : C.slate
  const r = 16, circ = 2 * Math.PI * r
  return (
    <div style={{ position: 'relative', width: 40, height: 40 }}>
      <svg viewBox="0 0 36 36" width={40} height={40} style={{ transform: 'rotate(-90deg)' }}>
        <circle cx="18" cy="18" r={r} fill="none" stroke={dark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.06)'} strokeWidth="2.5"/>
        <circle cx="18" cy="18" r={r} fill="none" stroke={c} strokeWidth="2.5"
          strokeLinecap="round" strokeDasharray={circ} strokeDashoffset={circ * (1 - score/100)}/>
      </svg>
      <span style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center',
        justifyContent: 'center', fontSize: 11, fontWeight: 700, color: c, letterSpacing: '-0.03em' }}>
        {score}
      </span>
    </div>
  )
}

// ─── Apple Sign In ────────────────────────────────────────────────────────────
function AppleSignInButton({ onPress }: { onPress: () => void }) {
  const [pressed, setPressed] = useState(false)
  return (
    <button onPointerDown={() => setPressed(true)} onPointerUp={() => { setPressed(false); onPress() }}
      onPointerLeave={() => setPressed(false)}
      style={{
        width: '100%', padding: '15px 20px',
        background: pressed ? '#222' : '#000', color: '#FFF',
        border: 'none', borderRadius: 14, fontSize: 17, fontWeight: 600,
        fontFamily: '-apple-system, "SF Pro Display", "Noto Sans KR", sans-serif',
        cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10,
        letterSpacing: '-0.01em',
        transform: pressed ? 'scale(0.97)' : 'scale(1)',
        transition: 'transform 0.1s ease, background 0.1s',
      }}>
      <svg viewBox="0 0 24 24" width="19" height="19" fill="white">
        <path d="M17.05 20.28c-.98.95-2.05.8-3.08.35-1.09-.46-2.09-.48-3.24 0-1.44.62-2.2.44-3.06-.35C2.79 15.25 3.51 7.7 9.05 7.4c1.36.07 2.29.74 3.08.8 1.18-.24 2.31-.93 3.57-.84 1.51.12 2.65.72 3.4 1.8-3.12 1.87-2.38 5.98.48 7.13-.57 1.5-1.31 2.99-2.53 3.99zM12.03 7.25c-.15-2.23 1.66-4.07 3.74-4.25.29 2.58-2.34 4.5-3.74 4.25z"/>
      </svg>
      Apple로 계속하기
    </button>
  )
}

// ─── Splash Screen ────────────────────────────────────────────────────────────
function SplashScreen({ onSignIn }: { onSignIn: () => void }) {
  const [phase, setPhase] = useState<'logo'|'login'>('logo')
  useEffect(() => { const t = setTimeout(() => setPhase('login'), 1500); return () => clearTimeout(t) }, [])

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', position: 'relative', background: '#FFFFFF' }}>
      {/* Logo phase */}
      <div style={{
        position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center', background: '#FFFFFF',
        opacity: phase === 'logo' ? 1 : 0,
        transform: phase === 'logo' ? 'scale(1)' : 'scale(1.1)',
        transition: 'opacity 0.4s ease, transform 0.4s ease',
        pointerEvents: phase === 'logo' ? 'auto' : 'none',
      }}>
        <div style={{ animation: 'logoIn 0.6s cubic-bezier(0.34,1.56,0.64,1) both' }}>
          <PinIcon size={72} />
        </div>
        <div style={{ fontSize: 34, fontWeight: 900, color: C.navy, letterSpacing: '-0.04em', marginTop: 12 }}>
          어디가지
        </div>
      </div>

      {/* Login phase */}
      <div style={{
        position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
        opacity: phase === 'login' ? 1 : 0,
        transform: phase === 'login' ? 'translateY(0)' : 'translateY(20px)',
        transition: 'opacity 0.45s ease 0.05s, transform 0.45s ease 0.05s',
        pointerEvents: phase === 'login' ? 'auto' : 'none',
      }}>
        {/* Hero area */}
        <div style={{
          flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          background: 'linear-gradient(180deg, #EEF2FF 0%, #FAFBFF 55%, #FFFFFF 100%)',
          padding: '0 36px',
        }}>
          {/* App icon */}
          <div style={{
            width: 96, height: 96, background: '#FFFFFF', borderRadius: 24,
            boxShadow: '0 4px 24px rgba(59,91,219,0.18), 0 1px 6px rgba(0,0,0,0.06)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 22,
          }}>
            <PinIcon size={56} />
          </div>
          <h1 style={{ fontSize: 34, fontWeight: 900, color: C.navy, letterSpacing: '-0.04em', marginBottom: 10, textAlign: 'center', lineHeight: 1.15 }}>
            어디가지
          </h1>
          <p style={{ fontSize: 15, color: C.labelSecondary, textAlign: 'center', lineHeight: 1.65, letterSpacing: '-0.02em', maxWidth: 240 }}>
            갈 수 있는 범위 안에서,<br />가장 가치 있는 선택.
          </p>
          <div style={{ display: 'flex', gap: 7, marginTop: 22, flexWrap: 'wrap', justifyContent: 'center' }}>
            {['도달 가능성 우선', '이유 설명', '공개 데이터'].map(l => (
              <span key={l} style={{ padding: '5px 11px', background: C.cobaltLight, color: '#3730A3',
                fontSize: 11, fontWeight: 600, borderRadius: 100, letterSpacing: '-0.01em' }}>{l}</span>
            ))}
          </div>
        </div>

        {/* Sign in area */}
        <div style={{ padding: '24px 24px 10px', display: 'flex', flexDirection: 'column', gap: 12, background: '#FFFFFF' }}>
          <AppleSignInButton onPress={onSignIn} />
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ flex: 1, height: 1, background: C.border }} />
            <span style={{ fontSize: 12, color: C.slate, fontWeight: 500 }}>또는</span>
            <div style={{ flex: 1, height: 1, background: C.border }} />
          </div>
          <button onClick={onSignIn} style={{
            width: '100%', padding: '14px 20px', background: 'transparent',
            color: C.labelSecondary, border: `1.5px solid ${C.border}`,
            borderRadius: 14, fontSize: 15, fontWeight: 600, cursor: 'pointer',
            fontFamily: "'Noto Sans KR', system-ui, sans-serif", letterSpacing: '-0.01em',
          }}>둘러보기</button>
          <p style={{ fontSize: 10.5, color: C.slateLight, textAlign: 'center', lineHeight: 1.6, letterSpacing: '-0.01em', padding: '0 8px' }}>
            계속하면 <span style={{ color: C.slate, textDecoration: 'underline' }}>이용약관</span> 및{' '}
            <span style={{ color: C.slate, textDecoration: 'underline' }}>개인정보처리방침</span>에 동의합니다.
          </p>
        </div>
      </div>
    </div>
  )
}

// ─── NLP parser (rule-based keyword matching, F0 tier) ───────────────────────
const NLP_RULES: { keywords: string[]; category: string; label: string }[] = [
  { keywords: ['술','맥주','소주','막걸리','와인','포차','호프','bar','바','이자카야'], category: '술집/바', label: '🍺 술집/바' },
  { keywords: ['영화','공연','전시','뮤지컬','연극','콘서트','갤러리','팝업'], category: '문화/공연', label: '🎭 문화/공연' },
  { keywords: ['데이트','분위기','로맨틱','커플','기념일','이쁜','감성'], category: '카페/식사', label: '✨ 카페/식사' },
  { keywords: ['헬스','운동','클라이밍','필라테스','요가','스포츠','수영','볼링'], category: '운동/스포츠', label: '🏃 운동/스포츠' },
  { keywords: ['머리','네일','피부','미용','뷰티','헤어','왁싱','스파'], category: '뷰티/미용', label: '💇 뷰티/미용' },
  { keywords: ['쇼핑','옷','신발','쇼룸','편집샵','빈티지','아울렛'], category: '쇼핑', label: '🛍 쇼핑' },
  { keywords: ['카페','커피','디저트','브런치','스터디','작업','노트북'], category: '카페', label: '☕ 카페' },
  { keywords: ['산책','공원','자연','힐링','바람','야경','한강'], category: '여가/자연', label: '🌿 여가/자연' },
  { keywords: ['친구','모임','파티','회식','단체'], category: '식사', label: '🍽 식사' },
  { keywords: ['밥','식사','점심','저녁','저녁밥','맛집','한식','양식','일식','중식'], category: '식사', label: '🍽 식사' },
]

function parseNLP(text: string): { category: string; label: string; confidence: number; matched: string[] } {
  const lower = text.toLowerCase()
  for (const rule of NLP_RULES) {
    const matched = rule.keywords.filter(k => lower.includes(k))
    if (matched.length > 0) return { category: rule.category, label: rule.label, confidence: Math.min(60 + matched.length * 15, 95), matched }
  }
  return { category: '식사', label: '🍽 식사', confidence: 42, matched: [] }
}

// ─── Location Sheet (iOS bottom sheet) ───────────────────────────────────────
const RECENT_LOCATIONS = [
  { name: '홍대입구역', sub: '서울 마포구 동교동', icon: '🕐' },
  { name: '강남역', sub: '서울 강남구 역삼동', icon: '🕐' },
  { name: '경희대학교', sub: '서울 동대문구 회기동', icon: '🕐' },
]
const SEARCH_RESULTS: Record<string, { name: string; sub: string }[]> = {
  '외대': [{ name: '외대앞역', sub: '서울 동대문구 회기동' }, { name: '한국외국어대학교', sub: '서울 동대문구 이문동' }],
  '홍대': [{ name: '홍대입구역', sub: '서울 마포구 동교동' }, { name: '홍익대학교', sub: '서울 마포구 상수동' }],
  '강남': [{ name: '강남역', sub: '서울 강남구 역삼동' }, { name: '강남구청역', sub: '서울 강남구 삼성동' }, { name: '강남대로', sub: '서울 강남구' }],
  '서울': [{ name: '서울역', sub: '서울 용산구 동자동' }, { name: '서울시청', sub: '서울 중구 태평로' }],
  '신촌': [{ name: '신촌역', sub: '서울 마포구 노고산동' }, { name: '연세대학교', sub: '서울 서대문구 신촌동' }],
  '이태원': [{ name: '이태원역', sub: '서울 용산구 이태원동' }],
  '성수': [{ name: '성수역', sub: '서울 성동구 성수동' }, { name: '성수동 카페거리', sub: '서울 성동구 성수동2가' }],
}

function getSearchResults(query: string) {
  if (!query.trim()) return []
  const key = Object.keys(SEARCH_RESULTS).find(k => query.includes(k))
  if (key) return SEARCH_RESULTS[key]
  return [{ name: `"${query}" 검색 결과`, sub: '결과를 찾지 못했습니다' }]
}

interface LocationValue { name: string; sub: string }

// ─── Map address anchors (SVG 900×900, center=450) ────────────────────────────
const MAP_ANCHORS: (LocationValue & { sx: number; sy: number })[] = [
  { sx: 378, sy: 458, name: '외대앞역', sub: '서울 동대문구 회기동' },
  { sx: 248, sy: 458, name: '회기역', sub: '서울 동대문구 회기동' },
  { sx: 530, sy: 458, name: '경희대입구', sub: '서울 동대문구 이문동' },
  { sx: 165, sy: 260, name: '한국외국어대학교', sub: '서울 동대문구 이문동' },
  { sx: 660, sy: 220, name: '경희대학교 정문', sub: '서울 동대문구 이문동' },
  { sx: 378, sy: 290, name: '청량리 방면', sub: '서울 동대문구 청량리동' },
  { sx: 378, sy: 640, name: '전농동', sub: '서울 동대문구 전농동' },
  { sx: 620, sy: 540, name: '이문동 주민센터', sub: '서울 동대문구 이문동' },
  { sx: 140, sy: 570, name: '서울시립대 방면', sub: '서울 동대문구 전농동' },
  { sx: 490, sy: 340, name: '경희대 후문', sub: '서울 동대문구 이문동' },
  { sx: 200, sy: 420, name: '외대 정문', sub: '서울 동대문구 이문동' },
  { sx: 700, sy: 450, name: '이문삼거리', sub: '서울 동대문구 이문동' },
]

function getMapAddress(ox: number, oy: number): LocationValue {
  const cx = 450 - ox, cy = 450 - oy
  let best = MAP_ANCHORS[0], bestDist = Infinity
  for (const a of MAP_ANCHORS) {
    const d = Math.hypot(a.sx - cx, a.sy - cy)
    if (d < bestDist) { bestDist = d; best = a }
  }
  return { name: best.name, sub: best.sub }
}

// ─── Map SVG (outer: 900×900, modeled on 외대앞/회기/이문 area) ───────────────
function SeoulMapSVG() {
  return (
    <svg viewBox="0 0 900 900" width="900" height="900" style={{ display: 'block', userSelect: 'none' }}>
      {/* Base */}
      <rect width="900" height="900" fill="#F0EBE1"/>

      {/* Green — 외대 캠퍼스 */}
      <path d="M60,80 L300,80 L310,160 L290,340 L240,380 L180,390 L70,370 L50,280 L60,80Z" fill="#C8DDB0" stroke="#A8C888" strokeWidth="1.2"/>
      {/* Green — 경희대 캠퍼스 */}
      <path d="M510,70 L800,70 L810,360 L760,390 L520,400 L500,280 L510,70Z" fill="#C8DDB0" stroke="#A8C888" strokeWidth="1.2"/>
      {/* Small park south */}
      <rect x="400" y="570" width="90" height="65" rx="5" fill="#CBDFA8" stroke="#A8C888" strokeWidth="1"/>
      {/* Riverside green strip */}
      <rect x="0" y="590" width="900" height="28" fill="#D0E6B0" opacity="0.5"/>

      {/* ── Building blocks ── */}
      {[
        [80,410,55,35],[145,410,65,35],[220,405,50,40],[280,408,60,35],
        [80,460,70,50],[160,462,55,48],[225,460,65,50],[300,460,55,50],
        [80,525,60,40],[150,522,70,42],[230,520,55,44],[296,522,58,42],
        [80,578,55,36],[145,578,72,36],[228,576,60,38],[300,578,54,36],
        [398,410,55,35],[462,408,60,38],[530,405,55,38],[596,408,60,36],
        [398,462,58,48],[464,460,55,50],[528,460,65,50],[602,460,55,48],
        [396,522,60,42],[464,520,58,44],[530,518,62,46],[600,520,58,44],
        [396,578,58,36],[462,578,62,36],[532,576,58,38],[600,576,60,36],
        [710,410,55,35],[775,410,60,35],[710,460,58,48],[775,460,58,48],
        [710,520,60,42],[775,522,55,42],[710,576,58,36],[776,576,56,36],
        [145,300,60,40],[215,296,55,44],[280,298,60,40],[340,300,50,38],
        [398,310,55,40],[460,308,58,42],[526,310,60,38],[594,308,55,40],
      ].map(([x,y,w,h], i) => (
        <rect key={i} x={x} y={y} width={w} height={h} rx="2" fill={i%3===0?'#E4DDD0':'#DEDAD2'} stroke="#CFC8BC" strokeWidth="0.6"/>
      ))}

      {/* ── Roads — draw border then fill ── */}
      {/* 경희대로 (main E-W arterial) */}
      <line x1="0" y1="454" x2="900" y2="454" stroke="#CBBFA8" strokeWidth="28"/>
      <line x1="0" y1="454" x2="900" y2="454" stroke="#FFFFFF" strokeWidth="22"/>

      {/* 북부간선도로 */}
      <line x1="0" y1="592" x2="900" y2="592" stroke="#CBBFA8" strokeWidth="20"/>
      <line x1="0" y1="592" x2="900" y2="592" stroke="#FFFFFF" strokeWidth="16"/>

      {/* 회기로 (main N-S) */}
      <line x1="378" y1="0" x2="378" y2="900" stroke="#CBBFA8" strokeWidth="22"/>
      <line x1="378" y1="0" x2="378" y2="900" stroke="#FFFFFF" strokeWidth="18"/>

      {/* 외대앞길 N-S */}
      <line x1="248" y1="0" x2="248" y2="600" stroke="#D4CAB8" strokeWidth="16"/>
      <line x1="248" y1="0" x2="248" y2="600" stroke="#FFFFFF" strokeWidth="13"/>

      {/* 이문로 N-S (east) */}
      <line x1="534" y1="0" x2="534" y2="600" stroke="#D4CAB8" strokeWidth="14"/>
      <line x1="534" y1="0" x2="534" y2="600" stroke="#FFFFFF" strokeWidth="11"/>

      {/* 경희대로13길 E-W secondary */}
      <line x1="0" y1="350" x2="900" y2="350" stroke="#D8D0C0" strokeWidth="12"/>
      <line x1="0" y1="350" x2="900" y2="350" stroke="#FFFFFF" strokeWidth="9"/>

      {/* Alley grid — small roads */}
      {[145,220,300,464,600,710].map(x => (
        <line key={x} x1={x} y1="350" x2={x} y2="600" stroke="#EEEADE" strokeWidth="6"/>
      ))}
      {[410,520].map(y => (
        <line key={y} x1="70" y1={y} x2="820" y2={y} stroke="#EEEADE" strokeWidth="6"/>
      ))}

      {/* ── Subway Line 1 ── */}
      <line x1="0" y1="460" x2="900" y2="460" stroke="#003DA5" strokeWidth="4" strokeDasharray="14 7" opacity="0.5"/>

      {/* ── Road labels ── */}
      <text x="120" y="447" fontSize="9" fill="#9A9080" fontFamily="'Noto Sans KR',system-ui" fontWeight="500">경희대로</text>
      <text x="430" y="447" fontSize="9" fill="#9A9080" fontFamily="'Noto Sans KR',system-ui" fontWeight="500">경희대로</text>
      <text x="650" y="447" fontSize="9" fill="#9A9080" fontFamily="'Noto Sans KR',system-ui" fontWeight="500">경희대로</text>
      <text x="385" y="340" fontSize="8" fill="#B0A898" fontFamily="'Noto Sans KR',system-ui" transform="rotate(90,385,340)">회기로</text>
      <text x="254" y="310" fontSize="8" fill="#B0A898" fontFamily="'Noto Sans KR',system-ui" transform="rotate(90,254,310)">외대앞길</text>

      {/* Campus labels */}
      <text x="175" y="225" textAnchor="middle" fontSize="11" fontWeight="700" fill="#6A8A50" fontFamily="'Noto Sans KR',system-ui">한국외국어대학교</text>
      <text x="660" y="230" textAnchor="middle" fontSize="11" fontWeight="700" fill="#6A8A50" fontFamily="'Noto Sans KR',system-ui">경희대학교</text>

      {/* ── Station markers ── */}
      {/* 외대앞역 */}
      <circle cx="378" cy="460" r="11" fill="#003DA5" stroke="#FFFFFF" strokeWidth="3"/>
      <circle cx="378" cy="460" r="4.5" fill="#FFFFFF"/>
      <text x="378" y="482" textAnchor="middle" fontSize="10" fontWeight="700" fill="#003DA5" fontFamily="'Noto Sans KR',system-ui">외대앞</text>

      {/* 회기역 */}
      <circle cx="248" cy="460" r="9" fill="#003DA5" stroke="#FFFFFF" strokeWidth="2.5"/>
      <circle cx="248" cy="460" r="3.5" fill="#FFFFFF"/>
      <text x="248" y="479" textAnchor="middle" fontSize="9" fill="#003DA5" fontFamily="'Noto Sans KR',system-ui" fontWeight="600">회기</text>

      {/* 경희대역 (implied) */}
      <circle cx="534" cy="460" r="9" fill="#003DA5" stroke="#FFFFFF" strokeWidth="2.5"/>
      <circle cx="534" cy="460" r="3.5" fill="#FFFFFF"/>
      <text x="534" y="479" textAnchor="middle" fontSize="9" fill="#003DA5" fontFamily="'Noto Sans KR',system-ui" fontWeight="600">경희대</text>
    </svg>
  )
}

// ─── Map Detail Sheet ─────────────────────────────────────────────────────────
function MapDetailSheet({ initialLocation, onBack, onConfirm }: {
  initialLocation: LocationValue
  onBack: () => void
  onConfirm: (loc: LocationValue) => void
}) {
  const [offset, setOffset] = useState({ x: 0, y: 0 })
  const [dragging, setDragging] = useState(false)
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 })
  const [startOffset, setStartOffset] = useState({ x: 0, y: 0 })
  const [confirmed, setConfirmed] = useState(false)
  const mapRef = useRef<HTMLDivElement>(null)

  const currentAddr = getMapAddress(offset.x, offset.y)

  const onPointerDown = (e: React.PointerEvent) => {
    e.currentTarget.setPointerCapture(e.pointerId)
    setDragging(true)
    setDragStart({ x: e.clientX, y: e.clientY })
    setStartOffset({ ...offset })
  }
  const onPointerMove = (e: React.PointerEvent) => {
    if (!dragging) return
    setOffset({
      x: startOffset.x + (e.clientX - dragStart.x),
      y: startOffset.y + (e.clientY - dragStart.y),
    })
  }
  const onPointerUp = () => setDragging(false)

  const handleConfirm = () => {
    setConfirmed(true)
    setTimeout(() => onConfirm(currentAddr), 400)
  }

  // SVG translate: center (450,450) of map → center of viewport (195, 215 approx)
  const mapTranslateX = -450 + 195 + offset.x
  const mapTranslateY = -450 + 200 + offset.y

  return (
    <div style={{
      position: 'absolute', inset: 0, zIndex: 250,
      background: '#F0EBE1',
      display: 'flex', flexDirection: 'column',
      animation: 'slideInRight 0.3s cubic-bezier(0.32,0.72,0,1) both',
    }}>
      {/* Nav bar */}
      <div style={{
        height: 52, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 8px 0 4px', flexShrink: 0,
        background: 'rgba(240,235,225,0.92)', backdropFilter: 'blur(16px)',
        borderBottom: '1px solid rgba(0,0,0,0.08)',
      }}>
        <button onClick={onBack} style={{
          display: 'flex', alignItems: 'center', gap: 3, padding: '8px 12px',
          background: 'none', border: 'none', cursor: 'pointer', color: C.cobalt,
          fontSize: 15, fontWeight: 600, fontFamily: "'Noto Sans KR', system-ui",
        }}>
          <svg viewBox="0 0 10 17" width="9" height="16" fill="none">
            <path d="M8.5 1.5L1.5 8.5l7 7" stroke={C.cobalt} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          뒤로
        </button>
        <span style={{ fontSize: 16, fontWeight: 700, color: C.navy, letterSpacing: '-0.03em', position: 'absolute', left: '50%', transform: 'translateX(-50%)' }}>
          위치 확인
        </span>
        <div style={{ width: 64 }} />
      </div>

      {/* Map area */}
      <div ref={mapRef} style={{ flex: 1, overflow: 'hidden', position: 'relative', cursor: dragging ? 'grabbing' : 'grab' }}
        onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={onPointerUp} onPointerLeave={onPointerUp}>

        {/* Map SVG */}
        <div style={{
          position: 'absolute', top: 0, left: 0,
          transform: `translate(${mapTranslateX}px, ${mapTranslateY}px)`,
          transition: dragging ? 'none' : 'transform 0.18s ease',
          willChange: 'transform',
        }}>
          <SeoulMapSVG />
        </div>

        {/* Address bubble above pin */}
        <div style={{
          position: 'absolute', top: '50%', left: '50%',
          transform: 'translate(-50%, -68px)',
          background: C.navy, color: '#FFFFFF',
          padding: '7px 14px', borderRadius: 20,
          fontSize: 13, fontWeight: 600, letterSpacing: '-0.02em',
          whiteSpace: 'nowrap', pointerEvents: 'none',
          boxShadow: '0 4px 16px rgba(13,27,75,0.3)',
          transition: 'opacity 0.15s',
          opacity: dragging ? 0.75 : 1,
          fontFamily: "'Noto Sans KR', system-ui",
        }}>
          {currentAddr.name}
          {/* Tail */}
          <div style={{
            position: 'absolute', bottom: -6, left: '50%', transform: 'translateX(-50%)',
            width: 0, height: 0,
            borderLeft: '6px solid transparent', borderRight: '6px solid transparent',
            borderTop: `6px solid ${C.navy}`,
          }}/>
        </div>

        {/* Center pin */}
        <div style={{
          position: 'absolute', top: '50%', left: '50%',
          transform: 'translate(-50%, -100%)',
          pointerEvents: 'none',
          filter: dragging ? 'drop-shadow(0 8px 12px rgba(0,0,0,0.35))' : 'drop-shadow(0 4px 8px rgba(0,0,0,0.25))',
          transition: 'filter 0.12s',
        }}>
          <svg viewBox="0 0 36 48" width="36" height="48" fill="none">
            <path d="M18 2C10.268 2 4 8.268 4 16c0 10 14 28 14 28s14-18 14-28C32 8.268 25.732 2 18 2z" fill={C.cobalt}/>
            <circle cx="18" cy="16" r="6" fill="white"/>
            <circle cx="18" cy="16" r="3" fill={C.cobalt}/>
          </svg>
        </div>

        {/* Pin shadow */}
        <div style={{
          position: 'absolute', top: '50%', left: '50%',
          transform: `translate(-50%, ${dragging ? '4px' : '2px'})`,
          width: 16, height: 6,
          background: 'rgba(0,0,0,0.2)',
          borderRadius: '50%',
          pointerEvents: 'none',
          transition: 'transform 0.12s',
          filter: 'blur(2px)',
        }}/>

        {/* Zoom controls */}
        <div style={{
          position: 'absolute', right: 14, bottom: 16,
          display: 'flex', flexDirection: 'column', gap: 1,
          background: C.card, borderRadius: 10,
          boxShadow: '0 2px 10px rgba(0,0,0,0.15)', overflow: 'hidden',
        }}>
          {['+', '−'].map(sym => (
            <button key={sym} onClick={() => setOffset(o => ({
              x: o.x * (sym === '+' ? 1.4 : 0.7),
              y: o.y * (sym === '+' ? 1.4 : 0.7),
            }))} style={{
              width: 36, height: 36, display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: 'none', border: 'none', cursor: 'pointer',
              fontSize: 20, color: C.navy, fontWeight: 300, lineHeight: 1,
              borderBottom: sym === '+' ? `1px solid ${C.border}` : 'none',
            }}>{sym}</button>
          ))}
        </div>

        {/* Re-center button */}
        <button onClick={() => setOffset({ x: 0, y: 0 })} style={{
          position: 'absolute', right: 14, bottom: 98,
          width: 36, height: 36, display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: C.card, border: 'none', borderRadius: 10, cursor: 'pointer',
          boxShadow: '0 2px 10px rgba(0,0,0,0.15)',
        }}>
          <svg viewBox="0 0 20 20" width="18" height="18" fill="none">
            <circle cx="10" cy="10" r="3.5" fill={offset.x === 0 && offset.y === 0 ? C.cobalt : C.slate}/>
            <circle cx="10" cy="10" r="7" stroke={offset.x === 0 && offset.y === 0 ? C.cobalt : C.slate} strokeWidth="1.5"/>
            <path d="M10 1v2M10 17v2M1 10h2M17 10h2" stroke={offset.x === 0 && offset.y === 0 ? C.cobalt : C.slate} strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
        </button>

        {/* Drag hint */}
        {!dragging && offset.x === 0 && offset.y === 0 && (
          <div style={{
            position: 'absolute', bottom: 16, left: '50%', transform: 'translateX(-50%)',
            background: 'rgba(0,0,0,0.48)', color: 'white', borderRadius: 20,
            padding: '6px 14px', fontSize: 12, fontWeight: 500,
            letterSpacing: '-0.01em', pointerEvents: 'none', whiteSpace: 'nowrap',
            fontFamily: "'Noto Sans KR', system-ui",
            animation: 'fadeUp 0.4s ease 0.5s both',
          }}>
            지도를 드래그해 위치를 조정하세요
          </div>
        )}
      </div>

      {/* Bottom address bar + confirm */}
      <div style={{
        background: C.card, borderTop: '1px solid rgba(0,0,0,0.08)',
        padding: '14px 16px 10px', flexShrink: 0,
        boxShadow: '0 -4px 16px rgba(0,0,0,0.06)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
          <div style={{ width: 36, height: 36, borderRadius: 10, background: C.cobaltLight,
            display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
            <svg viewBox="0 0 20 24" width="14" height="18" fill="none">
              <path d="M10 1C6.134 1 3 4.134 3 8c0 5.5 7 13 7 13s7-7.5 7-13c0-3.866-3.134-7-7-7z" fill={C.cobalt}/>
              <circle cx="10" cy="8" r="2.5" fill="white"/>
            </svg>
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 15, fontWeight: 700, color: C.navy, letterSpacing: '-0.03em', lineHeight: 1.2 }}>
              {currentAddr.name}
            </div>
            <div style={{ fontSize: 12, color: C.labelSecondary, letterSpacing: '-0.01em' }}>
              {currentAddr.sub}
            </div>
          </div>
        </div>
        <button onClick={handleConfirm} style={{
          width: '100%', padding: '14px', borderRadius: 14, border: 'none', cursor: 'pointer',
          background: confirmed ? C.emerald : C.cobalt, color: '#FFFFFF',
          fontSize: 16, fontWeight: 700, letterSpacing: '-0.02em',
          fontFamily: "'Noto Sans KR', system-ui",
          display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
          transition: 'background 0.2s',
        }}>
          {confirmed ? (
            <>
              <svg viewBox="0 0 20 20" width="16" height="16" fill="none">
                <path d="M4 10l4 4 8-8" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
              위치 설정 완료
            </>
          ) : '이 위치로 설정'}
        </button>
      </div>
    </div>
  )
}

function LocationSheet({ onClose, onSelect }: {
  onClose: () => void
  onSelect: (loc: LocationValue) => void
}) {
  const [query, setQuery] = useState('')
  const [gpsState, setGpsState] = useState<'idle'|'loading'|'done'>('idle')
  const inputRef = useRef<HTMLInputElement>(null)
  const results = getSearchResults(query)

  useEffect(() => { setTimeout(() => inputRef.current?.focus(), 120) }, [])

  const handleGPS = () => {
    setGpsState('loading')
    setTimeout(() => {
      setGpsState('done')
      setTimeout(() => { onSelect({ name: '현재 위치', sub: '서울 동대문구 회기동 (GPS)' }) }, 600)
    }, 1800)
  }

  return (
    /* Backdrop */
    <div style={{ position: 'absolute', inset: 0, zIndex: 100, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end' }}
      onClick={onClose}>
      <div style={{ flex: 1, background: 'rgba(0,0,0,0.35)' }} />
      {/* Sheet */}
      <div onClick={e => e.stopPropagation()} style={{
        background: '#F2F2F7', borderRadius: '20px 20px 0 0',
        padding: '0 0 34px',
        animation: 'sheetUp 0.32s cubic-bezier(0.32,0.72,0,1) both',
        maxHeight: '82%', display: 'flex', flexDirection: 'column',
      }}>
        {/* Handle */}
        <div style={{ display: 'flex', justifyContent: 'center', padding: '10px 0 4px' }}>
          <div style={{ width: 36, height: 4, background: 'rgba(60,60,67,0.3)', borderRadius: 2 }} />
        </div>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 20px 12px' }}>
          <span style={{ fontSize: 17, fontWeight: 700, color: C.navy, letterSpacing: '-0.03em' }}>출발지 설정</span>
          <button onClick={onClose} style={{ fontSize: 15, fontWeight: 600, color: C.cobalt, background: 'none', border: 'none', cursor: 'pointer', fontFamily: "'Noto Sans KR', system-ui" }}>닫기</button>
        </div>

        {/* Search bar */}
        <div style={{ padding: '0 16px 12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', background: 'rgba(118,118,128,0.12)', borderRadius: 10, padding: '9px 12px', gap: 8 }}>
            <svg viewBox="0 0 20 20" width="16" height="16" fill="none">
              <circle cx="8.5" cy="8.5" r="5.5" stroke={C.slate} strokeWidth="1.6"/>
              <path d="M13 13l3.5 3.5" stroke={C.slate} strokeWidth="1.6" strokeLinecap="round"/>
            </svg>
            <input ref={inputRef} value={query} onChange={e => setQuery(e.target.value)}
              placeholder="역, 동네, 장소 검색"
              style={{ flex: 1, background: 'none', border: 'none', outline: 'none', fontSize: 15,
                color: C.navy, fontFamily: "'Noto Sans KR', system-ui", letterSpacing: '-0.02em' }} />
            {query && <button onClick={() => setQuery('')} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, display: 'flex' }}>
              <svg viewBox="0 0 16 16" width="16" height="16" fill={C.slate}><circle cx="8" cy="8" r="7"/><path d="M5.5 5.5l5 5M10.5 5.5l-5 5" stroke="white" strokeWidth="1.4" strokeLinecap="round"/></svg>
            </button>}
          </div>
        </div>

        <div style={{ overflowY: 'auto', flex: 1 }}>
          {/* GPS option */}
          {!query && (
            <div style={{ padding: '0 16px 12px' }}>
              <button onClick={handleGPS} style={{
                width: '100%', padding: '13px 16px', background: C.card, borderRadius: 12, border: 'none', cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: 12, fontFamily: "'Noto Sans KR', system-ui",
                boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
              }}>
                <div style={{ width: 36, height: 36, borderRadius: 10, background: gpsState === 'done' ? '#ECFDF5' : C.cobaltLight,
                  display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, transition: 'background 0.3s' }}>
                  {gpsState === 'loading' ? (
                    <div style={{ width: 16, height: 16, border: `2px solid ${C.cobalt}`, borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 0.7s linear infinite' }} />
                  ) : gpsState === 'done' ? (
                    <svg viewBox="0 0 20 20" width="16" height="16" fill="none"><path d="M4 10l4 4 8-8" stroke="#059669" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
                  ) : (
                    <svg viewBox="0 0 20 20" width="16" height="16" fill="none">
                      <circle cx="10" cy="10" r="4" fill={C.cobalt}/>
                      <circle cx="10" cy="10" r="7" stroke={C.cobalt} strokeWidth="1.5"/>
                      <path d="M10 1v2M10 17v2M1 10h2M17 10h2" stroke={C.cobalt} strokeWidth="1.5" strokeLinecap="round"/>
                    </svg>
                  )}
                </div>
                <div style={{ flex: 1, textAlign: 'left' }}>
                  <div style={{ fontSize: 15, fontWeight: 600, color: gpsState === 'done' ? C.emerald : C.navy, letterSpacing: '-0.02em' }}>
                    {gpsState === 'loading' ? '위치 확인 중…' : gpsState === 'done' ? '위치 확인됨' : '현재 위치 사용'}
                  </div>
                  <div style={{ fontSize: 12, color: C.labelSecondary, letterSpacing: '-0.01em' }}>
                    {gpsState === 'done' ? '서울 동대문구 회기동' : 'GPS 기반 자동 감지'}
                  </div>
                </div>
              </button>
            </div>
          )}

          {/* Search results or recents */}
          {query ? (
            <div style={{ padding: '0 16px' }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: C.slate, letterSpacing: '0.04em', marginBottom: 8, paddingLeft: 4 }}>검색 결과</div>
              <SectionCard>
                {results.length > 0 ? results.map((r, i) => (
                  <div key={r.name}>
                    <button onClick={() => { onSelect(r) }} style={{
                      width: '100%', padding: '12px 16px', background: 'none', border: 'none', cursor: 'pointer',
                      display: 'flex', alignItems: 'center', gap: 12, fontFamily: "'Noto Sans KR', system-ui",
                    }}>
                      <div style={{ width: 32, height: 32, borderRadius: 8, background: C.cobaltLight, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                        <svg viewBox="0 0 16 20" width="12" height="16" fill="none">
                          <path d="M8 1C4.686 1 2 3.686 2 7c0 4.5 6 11 6 11s6-6.5 6-11c0-3.314-2.686-6-6-6z" fill={C.cobalt}/>
                          <circle cx="8" cy="7" r="2" fill="white"/>
                        </svg>
                      </div>
                      <div style={{ flex: 1, textAlign: 'left' }}>
                        <div style={{ fontSize: 15, fontWeight: 500, color: C.navy, letterSpacing: '-0.02em' }}>{r.name}</div>
                        <div style={{ fontSize: 12, color: C.labelSecondary }}>{r.sub}</div>
                      </div>
                    </button>
                    {i < results.length - 1 && <Divider />}
                  </div>
                )) : (
                  <div style={{ padding: '20px 16px', textAlign: 'center', color: C.slate, fontSize: 14 }}>검색 결과가 없습니다</div>
                )}
              </SectionCard>
            </div>
          ) : (
            <div style={{ padding: '0 16px' }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: C.slate, letterSpacing: '0.04em', marginBottom: 8, paddingLeft: 4 }}>최근 검색</div>
              <SectionCard>
                {RECENT_LOCATIONS.map((loc, i) => (
                  <div key={loc.name}>
                    <button onClick={() => { onSelect(loc) }} style={{
                      width: '100%', padding: '12px 16px', background: 'none', border: 'none', cursor: 'pointer',
                      display: 'flex', alignItems: 'center', gap: 12, fontFamily: "'Noto Sans KR', system-ui",
                    }}>
                      <div style={{ width: 32, height: 32, borderRadius: 8, background: C.bg, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, fontSize: 16 }}>{loc.icon}</div>
                      <div style={{ flex: 1, textAlign: 'left' }}>
                        <div style={{ fontSize: 15, fontWeight: 500, color: C.navy, letterSpacing: '-0.02em' }}>{loc.name}</div>
                        <div style={{ fontSize: 12, color: C.labelSecondary }}>{loc.sub}</div>
                      </div>
                      <svg viewBox="0 0 8 13" width="7" height="11" fill="none">
                        <path d="M1 1.5l5.5 5L1 11.5" stroke="rgba(60,60,67,0.3)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                    </button>
                    {i < RECENT_LOCATIONS.length - 1 && <Divider />}
                  </div>
                ))}
              </SectionCard>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ─── Purpose Selector ─────────────────────────────────────────────────────────
const PURPOSES = [
  { id: '식사',      emoji: '🍽', label: '식사' },
  { id: '카페',      emoji: '☕', label: '카페' },
  { id: '쇼핑',      emoji: '🛍', label: '쇼핑' },
  { id: '여가/오락',  emoji: '🎮', label: '여가' },
  { id: '술집/바',   emoji: '🍺', label: '술/바' },
  { id: '문화/공연', emoji: '🎭', label: '문화' },
  { id: '뷰티/미용', emoji: '💇', label: '뷰티' },
  { id: '운동/스포츠',emoji: '🏃', label: '운동' },
  { id: '여가/자연', emoji: '🌿', label: '자연' },
  { id: '기타',      emoji: '✏️', label: '기타' },
]

function PurposeSelector({ value, onChange }: {
  value: string
  onChange: (v: string, displayLabel?: string) => void
}) {
  const [showNLP, setShowNLP] = useState(false)
  const [nlpText, setNlpText] = useState('')
  const [nlpState, setNlpState] = useState<'idle'|'analyzing'|'done'>('idle')
  const [nlpResult, setNlpResult] = useState<ReturnType<typeof parseNLP>|null>(null)
  const nlpRef = useRef<HTMLInputElement>(null)

  const handleSelectPurpose = (id: string) => {
    if (id === '기타') {
      setShowNLP(true)
      setNlpState('idle')
      setNlpResult(null)
      setNlpText('')
      setTimeout(() => nlpRef.current?.focus(), 80)
      onChange('기타')
    } else {
      setShowNLP(false)
      onChange(id)
    }
  }

  const handleNLPSubmit = () => {
    if (!nlpText.trim()) return
    setNlpState('analyzing')
    setNlpResult(null)
    setTimeout(() => {
      const result = parseNLP(nlpText)
      setNlpResult(result)
      setNlpState('done')
      onChange(result.category, `기타 → ${result.label}`)
    }, 1400)
  }

  return (
    <div>
      {/* Purpose grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 7 }}>
        {PURPOSES.map(p => {
          const active = value === p.id || (p.id !== '기타' && value === p.id)
          const isOther = p.id === '기타'
          const isActive = value === p.id || (isOther && showNLP)
          return (
            <button key={p.id} onClick={() => handleSelectPurpose(p.id)} style={{
              padding: '9px 4px 8px',
              background: isActive ? C.cobaltLight : 'rgba(118,118,128,0.1)',
              border: isActive ? `1.5px solid #C7D2FE` : '1.5px solid transparent',
              borderRadius: 10, cursor: 'pointer',
              display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3,
              fontFamily: "'Noto Sans KR', system-ui",
              transition: 'all 0.14s ease',
            }}>
              <span style={{ fontSize: 18, lineHeight: 1 }}>{p.emoji}</span>
              <span style={{ fontSize: 11, fontWeight: isActive ? 700 : 400, color: isActive ? '#3730A3' : C.labelSecondary, letterSpacing: '-0.01em' }}>{p.label}</span>
            </button>
          )
        })}
      </div>

      {/* NLP input (shown when 기타 is selected) */}
      {showNLP && (
        <div style={{ marginTop: 10, animation: 'fadeUp 0.2s ease both' }}>
          <div style={{ display: 'flex', alignItems: 'center', background: 'rgba(118,118,128,0.1)', borderRadius: 10, padding: '10px 12px', gap: 8 }}>
            <span style={{ fontSize: 14 }}>✏️</span>
            <input ref={nlpRef} value={nlpText}
              onChange={e => { setNlpText(e.target.value); setNlpState('idle'); setNlpResult(null) }}
              onKeyDown={e => e.key === 'Enter' && handleNLPSubmit()}
              placeholder="예: 조용한 데이트, 친구랑 맥주 한 잔…"
              style={{ flex: 1, background: 'none', border: 'none', outline: 'none', fontSize: 14,
                color: C.navy, fontFamily: "'Noto Sans KR', system-ui", letterSpacing: '-0.02em' }} />
            <button onClick={handleNLPSubmit} style={{
              padding: '5px 10px', background: C.cobalt, color: 'white', border: 'none', borderRadius: 7,
              fontSize: 12, fontWeight: 700, cursor: 'pointer', fontFamily: "'Noto Sans KR', system-ui",
              letterSpacing: '-0.01em', opacity: nlpText.trim() ? 1 : 0.4,
              transition: 'opacity 0.15s',
            }}>분석</button>
          </div>

          {/* NLP states */}
          {nlpState === 'analyzing' && (
            <div style={{ marginTop: 8, padding: '10px 12px', background: C.cobaltPale, borderRadius: 9,
              display: 'flex', alignItems: 'center', gap: 8 }}>
              <div style={{ width: 14, height: 14, border: `2px solid ${C.cobalt}`, borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 0.7s linear infinite', flexShrink: 0 }} />
              <span style={{ fontSize: 13, color: C.cobalt, letterSpacing: '-0.01em' }}>목적 분석 중…</span>
            </div>
          )}

          {nlpState === 'done' && nlpResult && (
            <div style={{ marginTop: 8, padding: '11px 14px', background: C.emeraldLight, borderRadius: 9,
              border: '1px solid #A7F3D0', animation: 'fadeUp 0.2s ease both' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <svg viewBox="0 0 16 16" width="14" height="14" fill="none">
                    <circle cx="8" cy="8" r="7" fill="#059669"/>
                    <path d="M4.5 8l2.5 2.5 5-5" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                  <span style={{ fontSize: 13, fontWeight: 700, color: '#065F46', letterSpacing: '-0.02em' }}>
                    분류 완료: {nlpResult.label}
                  </span>
                </div>
                <span style={{ fontSize: 11, fontWeight: 600, color: C.emerald, background: '#D1FAE5',
                  padding: '2px 7px', borderRadius: 6 }}>
                  신뢰도 {nlpResult.confidence}%
                </span>
              </div>
              {nlpResult.matched.length > 0 && (
                <p style={{ fontSize: 11, color: '#065F46', opacity: 0.75, lineHeight: 1.5, letterSpacing: '-0.01em' }}>
                  감지된 키워드: {nlpResult.matched.map(k => `"${k}"`).join(', ')}
                </p>
              )}
              <p style={{ fontSize: 10.5, color: '#065F46', opacity: 0.55, marginTop: 3, lineHeight: 1.4, letterSpacing: '-0.01em' }}>
                규칙 기반 F0 분류 · 실제 NLP 모델 아님
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ─── Calendar types & utils ──────────────────────────────────────────────────
type TimeSlot = '오전' | '낮' | '저녁' | '밤'
interface DateTimeValue { date: Date; slot: TimeSlot }

const DOW_KO = ['일', '월', '화', '수', '목', '금', '토']

const SLOT_META: Record<TimeSlot, { emoji: string; range: string }> = {
  '오전': { emoji: '🌅', range: '06:00–11:59' },
  '낮':   { emoji: '☀️', range: '12:00–17:59' },
  '저녁': { emoji: '🌆', range: '18:00–21:59' },
  '밤':   { emoji: '🌙', range: '22:00–05:59' },
}

function detectSlot(d: Date): TimeSlot {
  const h = d.getHours()
  if (h >= 6 && h < 12) return '오전'
  if (h >= 12 && h < 18) return '낮'
  if (h >= 18 && h < 22) return '저녁'
  return '밤'
}

function formatDateLabel(date: Date, slot: TimeSlot) {
  const m = date.getMonth() + 1
  const d = date.getDate()
  const dow = DOW_KO[date.getDay()]
  const isWknd = date.getDay() === 0 || date.getDay() === 6
  return { primary: `${m}월 ${d}일 (${dow})`, secondary: slot, isWknd }
}

function isSameDay(a: Date, b: Date) {
  return a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() && a.getDate() === b.getDate()
}

function isToday(d: Date) { return isSameDay(d, new Date()) }

function isPast(d: Date) {
  const today = new Date(); today.setHours(0,0,0,0)
  return d < today
}

function getMonthCells(year: number, month: number) {
  const first = new Date(year, month, 1)
  const last = new Date(year, month + 1, 0)
  const cells: { date: Date; cur: boolean }[] = []
  for (let i = 0; i < first.getDay(); i++)
    cells.push({ date: new Date(year, month, i - first.getDay() + 1), cur: false })
  for (let d = 1; d <= last.getDate(); d++)
    cells.push({ date: new Date(year, month, d), cur: true })
  while (cells.length % 7 !== 0)
    cells.push({ date: new Date(year, month + 1, cells.length - last.getDate() - first.getDay() + 1), cur: false })
  return cells
}

// ─── Calendar Sheet ───────────────────────────────────────────────────────────
function CalendarSheet({ value, onClose, onSelect }: {
  value: DateTimeValue
  onClose: () => void
  onSelect: (v: DateTimeValue) => void
}) {
  const [viewYear,  setViewYear]  = useState(value.date.getFullYear())
  const [viewMonth, setViewMonth] = useState(value.date.getMonth())
  const [selDate,   setSelDate]   = useState(value.date)
  const [selSlot,   setSelSlot]   = useState<TimeSlot>(value.slot)

  const cells = getMonthCells(viewYear, viewMonth)
  const weeks: typeof cells[] = []
  for (let i = 0; i < cells.length; i += 7) weeks.push(cells.slice(i, i + 7))

  const prevMonth = () => {
    if (viewMonth === 0) { setViewYear(y => y - 1); setViewMonth(11) }
    else setViewMonth(m => m - 1)
  }
  const nextMonth = () => {
    if (viewMonth === 11) { setViewYear(y => y + 1); setViewMonth(0) }
    else setViewMonth(m => m + 1)
  }

  const confirm = () => { onSelect({ date: selDate, slot: selSlot }); onClose() }

  return (
    <div style={{ position: 'absolute', inset: 0, zIndex: 300, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end' }}
      onClick={onClose}>
      {/* Scrim */}
      <div style={{ flex: 1, background: 'rgba(0,0,0,0.4)' }} />

      {/* Sheet */}
      <div onClick={e => e.stopPropagation()} style={{
        background: '#F2F2F7', borderRadius: '20px 20px 0 0',
        padding: '0 0 34px',
        animation: 'sheetUp 0.32s cubic-bezier(0.32,0.72,0,1) both',
        display: 'flex', flexDirection: 'column',
      }}>
        {/* Handle */}
        <div style={{ display: 'flex', justifyContent: 'center', padding: '10px 0 2px' }}>
          <div style={{ width: 36, height: 4, background: 'rgba(60,60,67,0.28)', borderRadius: 2 }} />
        </div>

        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 20px 10px' }}>
          <span style={{ fontSize: 17, fontWeight: 700, color: C.navy, letterSpacing: '-0.03em' }}>날짜 · 시간대 선택</span>
          <button onClick={onClose} style={{ fontSize: 15, fontWeight: 600, color: C.cobalt, background: 'none', border: 'none', cursor: 'pointer', fontFamily: "'Noto Sans KR', system-ui" }}>닫기</button>
        </div>

        {/* Calendar card */}
        <div style={{ margin: '0 16px', background: C.card, borderRadius: 14, padding: '14px 12px', boxShadow: '0 1px 3px rgba(0,0,0,0.06)' }}>
          {/* Month nav */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
            <button onClick={prevMonth} style={{ width: 32, height: 32, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(118,118,128,0.1)', border: 'none', borderRadius: 8, cursor: 'pointer' }}>
              <svg viewBox="0 0 8 13" width="7" height="11" fill="none">
                <path d="M7 1.5L1.5 7 7 12.5" stroke={C.navy} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
            <span style={{ fontSize: 16, fontWeight: 700, color: C.navy, letterSpacing: '-0.03em' }}>
              {viewYear}년 {viewMonth + 1}월
            </span>
            <button onClick={nextMonth} style={{ width: 32, height: 32, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(118,118,128,0.1)', border: 'none', borderRadius: 8, cursor: 'pointer' }}>
              <svg viewBox="0 0 8 13" width="7" height="11" fill="none">
                <path d="M1 1.5L6.5 7 1 12.5" stroke={C.navy} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
          </div>

          {/* DOW headers */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', marginBottom: 4 }}>
            {DOW_KO.map((d, i) => (
              <div key={d} style={{ textAlign: 'center', fontSize: 11, fontWeight: 600, paddingBottom: 6,
                color: i === 0 ? '#EF4444' : i === 6 ? C.cobalt : C.slate,
                letterSpacing: '-0.01em' }}>{d}</div>
            ))}
          </div>

          {/* Date grid */}
          {weeks.map((week, wi) => (
            <div key={wi} style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: '2px 0', marginBottom: 2 }}>
              {week.map(({ date, cur }, di) => {
                const today   = isToday(date)
                const sel     = isSameDay(date, selDate)
                const past    = isPast(date)
                const isSun   = date.getDay() === 0
                const isSat   = date.getDay() === 6
                const dimmed  = !cur || past

                return (
                  <button key={di} onClick={() => cur && setSelDate(date)}
                    disabled={!cur}
                    style={{
                      width: '100%', aspectRatio: '1', border: 'none', borderRadius: '50%', cursor: cur ? 'pointer' : 'default',
                      background: sel ? C.navy : today ? C.cobaltLight : 'transparent',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: 14, fontWeight: sel ? 700 : today ? 600 : 400,
                      color: sel ? '#FFFFFF' : today ? C.cobalt : dimmed ? C.slateLight : isSun ? '#EF4444' : isSat ? C.cobalt : C.navy,
                      transition: 'background 0.12s',
                      fontFamily: "'Noto Sans KR', system-ui",
                    }}>
                    {date.getDate()}
                  </button>
                )
              })}
            </div>
          ))}

          {/* Today indicator legend */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 10, paddingTop: 10, borderTop: `1px solid ${C.border}` }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
              <div style={{ width: 20, height: 20, borderRadius: '50%', background: C.cobaltLight, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <span style={{ fontSize: 10, color: C.cobalt, fontWeight: 700 }}>오</span>
              </div>
              <span style={{ fontSize: 11, color: C.slate }}>오늘</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
              <div style={{ width: 20, height: 20, borderRadius: '50%', background: C.navy }} />
              <span style={{ fontSize: 11, color: C.slate }}>선택됨</span>
            </div>
            <div style={{ marginLeft: 'auto' }}>
              <span style={{ fontSize: 11, color: C.slate }}>
                {formatDateLabel(selDate, selSlot).primary}
              </span>
            </div>
          </div>
        </div>

        {/* Time slot selector */}
        <div style={{ margin: '12px 16px 0' }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: C.slate, letterSpacing: '0.04em', marginBottom: 8, paddingLeft: 2 }}>시간대</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
            {(Object.entries(SLOT_META) as [TimeSlot, typeof SLOT_META[TimeSlot]][]).map(([slot, meta]) => {
              const active = selSlot === slot
              return (
                <button key={slot} onClick={() => setSelSlot(slot)} style={{
                  padding: '10px 4px 9px',
                  background: active ? C.navy : C.card,
                  border: active ? 'none' : `1.5px solid ${C.border}`,
                  borderRadius: 12, cursor: 'pointer',
                  display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4,
                  fontFamily: "'Noto Sans KR', system-ui",
                  boxShadow: active ? '0 2px 8px rgba(13,27,75,0.2)' : '0 1px 2px rgba(0,0,0,0.04)',
                  transition: 'all 0.14s ease',
                }}>
                  <span style={{ fontSize: 18, lineHeight: 1 }}>{meta.emoji}</span>
                  <span style={{ fontSize: 13, fontWeight: active ? 700 : 500, color: active ? '#FFFFFF' : C.navy, letterSpacing: '-0.02em' }}>{slot}</span>
                  <span style={{ fontSize: 10, color: active ? 'rgba(255,255,255,0.55)' : C.slate, letterSpacing: '-0.01em' }}>{meta.range}</span>
                </button>
              )
            })}
          </div>
        </div>

        {/* Confirm */}
        <div style={{ margin: '14px 16px 0' }}>
          <button onClick={confirm} style={{
            width: '100%', padding: '15px', background: C.cobalt, color: '#FFFFFF',
            border: 'none', borderRadius: 14, fontSize: 16, fontWeight: 700, cursor: 'pointer',
            fontFamily: "'Noto Sans KR', system-ui", letterSpacing: '-0.02em',
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
          }}>
            <svg viewBox="0 0 20 20" width="16" height="16" fill="none">
              <path d="M4 10l4 4 8-8" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            {formatDateLabel(selDate, selSlot).primary} · {selSlot} 선택
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── Home Screen ──────────────────────────────────────────────────────────────
function HomeScreen({ onSearch, onOpenLocation, origin, onOpenCalendar, dateTime, setDateTime }: {
  onSearch: (purpose: string, purposeDisplay: string) => void
  onOpenLocation: () => void
  origin: LocationValue
  onOpenCalendar: () => void
  dateTime: DateTimeValue
  setDateTime: (v: DateTimeValue) => void
}) {
  const [maxTime, setMaxTime] = useState('30분')
  const [transport, setTransport] = useState<'대중교통' | '자차'>('대중교통')
  const [purpose, setPurpose] = useState('식사')
  const [purposeDisplay, setPurposeDisplay] = useState('식사')

  const handlePurposeChange = (v: string, display?: string) => {
    setPurpose(v)
    setPurposeDisplay(display ?? v)
  }

  const dtLabel = formatDateLabel(dateTime.date, dateTime.slot)

  return (
    <div style={{ flex: 1, overflowY: 'auto', background: C.bg, position: 'relative' }}>
      <div style={{ padding: '8px 16px 32px', display: 'flex', flexDirection: 'column', gap: 20 }}>

        {/* Large title */}
        <div style={{ paddingTop: 4 }}>
          <h1 style={{ fontSize: 34, fontWeight: 800, color: C.navy, letterSpacing: '-0.04em', lineHeight: 1.15, marginBottom: 4 }}>
            어디가지
          </h1>
          <p style={{ fontSize: 14, color: C.labelSecondary, letterSpacing: '-0.02em', lineHeight: 1.5 }}>
            조건을 입력하면 갈 수 있는 곳을 추천해요
          </p>
        </div>

        {/* 출발지 */}
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: C.labelSecondary, letterSpacing: '-0.01em',
            textTransform: 'uppercase', marginBottom: 8, paddingLeft: 4 }}>출발지</div>
          <SectionCard>
            <button onClick={onOpenLocation} style={{
              width: '100%', padding: '12px 16px', background: 'none', border: 'none', cursor: 'pointer',
              display: 'flex', alignItems: 'center', gap: 12, fontFamily: "'Noto Sans KR', system-ui",
            }}>
              <div style={{ width: 36, height: 36, background: origin.name === '현재 위치' ? C.emeraldLight : C.cobaltLight,
                borderRadius: 10, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, transition: 'background 0.3s' }}>
                {origin.name === '현재 위치' ? (
                  <svg viewBox="0 0 20 20" width="16" height="16" fill="none">
                    <circle cx="10" cy="10" r="4" fill={C.emerald}/>
                    <circle cx="10" cy="10" r="7" stroke={C.emerald} strokeWidth="1.5"/>
                    <path d="M10 1v2M10 17v2M1 10h2M17 10h2" stroke={C.emerald} strokeWidth="1.5" strokeLinecap="round"/>
                  </svg>
                ) : (
                  <svg viewBox="0 0 20 24" width="14" height="18" fill="none">
                    <path d="M10 1C6.134 1 3 4.134 3 8c0 5.5 7 13 7 13s7-7.5 7-13c0-3.866-3.134-7-7-7z" fill={C.cobalt}/>
                    <circle cx="10" cy="8" r="2.5" fill="white"/>
                  </svg>
                )}
              </div>
              <div style={{ flex: 1, textAlign: 'left' }}>
                <div style={{ fontSize: 16, fontWeight: 600, color: C.navy, letterSpacing: '-0.02em' }}>{origin.name}</div>
                <div style={{ fontSize: 12, color: C.labelSecondary, letterSpacing: '-0.01em' }}>{origin.sub}</div>
              </div>
              <svg viewBox="0 0 8 13" width="8" height="13" fill="none">
                <path d="M1 1.5l5.5 5L1 11.5" stroke="rgba(60,60,67,0.3)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
          </SectionCard>
        </div>

        {/* 이동 조건 */}
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: C.labelSecondary, letterSpacing: '-0.01em',
            textTransform: 'uppercase', marginBottom: 8, paddingLeft: 4 }}>이동 조건</div>
          <SectionCard>
            {/* Transport mode */}
            <div style={{ padding: '12px 16px 10px' }}>
              <div style={{ fontSize: 13, color: C.labelSecondary, marginBottom: 8, letterSpacing: '-0.01em' }}>이동 수단</div>
              <div style={{ display: 'flex', gap: 8 }}>
                {(['대중교통', '자차'] as const).map(mode => {
                  const active = transport === mode
                  return (
                    <button key={mode} onClick={() => setTransport(mode)} style={{
                      flex: 1, padding: '9px 0', borderRadius: 10, border: 'none', cursor: 'pointer',
                      background: active ? C.navy : 'rgba(120,120,128,0.08)',
                      color: active ? '#FFFFFF' : C.labelSecondary,
                      fontSize: 14, fontWeight: active ? 700 : 500,
                      fontFamily: "'Noto Sans KR', system-ui",
                      letterSpacing: '-0.02em',
                      display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                      transition: 'all 0.18s ease',
                    }}>
                      {mode === '대중교통' ? (
                        <svg viewBox="0 0 18 18" width="15" height="15" fill="none">
                          <rect x="2" y="3" width="14" height="9" rx="2.5" stroke={active ? '#FFFFFF' : C.labelSecondary} strokeWidth="1.5"/>
                          <path d="M5 12v2M13 12v2" stroke={active ? '#FFFFFF' : C.labelSecondary} strokeWidth="1.5" strokeLinecap="round"/>
                          <circle cx="6" cy="7.5" r="1.5" fill={active ? '#FFFFFF' : C.labelSecondary}/>
                          <circle cx="12" cy="7.5" r="1.5" fill={active ? '#FFFFFF' : C.labelSecondary}/>
                          <path d="M2 8h14" stroke={active ? '#FFFFFF' : C.labelSecondary} strokeWidth="1.2"/>
                        </svg>
                      ) : (
                        <svg viewBox="0 0 20 14" width="17" height="12" fill="none">
                          <path d="M1 9h1M18 9h1M2 9h16M3 5h9l3 4H3V5z" stroke={active ? '#FFFFFF' : C.labelSecondary} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                          <circle cx="5.5" cy="11" r="1.5" stroke={active ? '#FFFFFF' : C.labelSecondary} strokeWidth="1.5"/>
                          <circle cx="14.5" cy="11" r="1.5" stroke={active ? '#FFFFFF' : C.labelSecondary} strokeWidth="1.5"/>
                        </svg>
                      )}
                      {mode}
                    </button>
                  )
                })}
              </div>
            </div>
            <Divider />
            <div style={{ padding: '10px 16px 10px' }}>
              <div style={{ fontSize: 13, color: C.labelSecondary, marginBottom: 8, letterSpacing: '-0.01em' }}>
                최대 이동시간{transport === '자차' ? ' (운전)' : ''}
              </div>
              <SegmentedControl options={['20분', '30분', '40분', '60분']} value={maxTime} onChange={setMaxTime} />
            </div>
            <Divider />
            <div style={{ padding: '13px 16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <div style={{ width: 32, height: 32, background: C.cobaltLight, borderRadius: 8,
                    display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, fontSize: 16 }}>
                    {SLOT_META[dateTime.slot].emoji}
                  </div>
                  <div>
                    <div style={{ fontSize: 15, fontWeight: 600, color: C.navy, letterSpacing: '-0.02em', lineHeight: 1.2 }}>
                      {dtLabel.primary}
                    </div>
                    <div style={{ fontSize: 12, color: dtLabel.isWknd ? C.cobalt : C.labelSecondary, letterSpacing: '-0.01em', marginTop: 1 }}>
                      {dtLabel.secondary} · {SLOT_META[dateTime.slot].range}
                      {dtLabel.isWknd && <span style={{ marginLeft: 6, fontSize: 10, fontWeight: 700, color: C.cobalt, background: C.cobaltLight, padding: '1px 5px', borderRadius: 4 }}>주말</span>}
                    </div>
                  </div>
                </div>
                <button onClick={onOpenCalendar} style={{
                  padding: '6px 12px', background: C.cobaltLight, color: C.cobalt,
                  border: '1px solid #C7D2FE', borderRadius: 8, fontSize: 12, fontWeight: 700,
                  cursor: 'pointer', fontFamily: "'Noto Sans KR', system-ui", letterSpacing: '-0.01em',
                  flexShrink: 0,
                }}>변경</button>
              </div>
            </div>
          </SectionCard>
        </div>

        {/* 목적 */}
        <div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8, paddingLeft: 4 }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: C.labelSecondary, letterSpacing: '-0.01em', textTransform: 'uppercase' }}>목적</div>
            {purposeDisplay !== purpose && (
              <span style={{ fontSize: 11, fontWeight: 600, color: C.cobalt, letterSpacing: '-0.01em' }}>{purposeDisplay}</span>
            )}
          </div>
          <SectionCard>
            <div style={{ padding: '14px 14px 14px' }}>
              <PurposeSelector value={purpose} onChange={handlePurposeChange} />
            </div>
          </SectionCard>
        </div>

        {/* CTA */}
        <button onClick={() => onSearch(purpose, purposeDisplay)} style={{
          width: '100%', padding: '16px', background: C.navy, color: '#FFFFFF',
          border: 'none', borderRadius: 14, fontSize: 17, fontWeight: 700, cursor: 'pointer',
          fontFamily: "'Noto Sans KR', system-ui, sans-serif", letterSpacing: '-0.02em',
          boxShadow: '0 4px 14px rgba(13,27,75,0.28)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
        }}>
          <span>추천 보기</span>
          <svg viewBox="0 0 20 20" width="18" height="18" fill="none">
            <path d="M4 10h12M10 4l6 6-6 6" stroke="white" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </button>

        {/* Trust note */}
        <SectionCard>
          <div style={{ padding: '14px 16px', display: 'flex', gap: 10, alignItems: 'flex-start' }}>
            <svg viewBox="0 0 20 20" width="18" height="18" fill="none" style={{ flexShrink: 0, marginTop: 1 }}>
              <circle cx="10" cy="10" r="8" stroke={C.slate} strokeWidth="1.5"/>
              <path d="M10 9v5M10 7v.5" stroke={C.slate} strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
            <p style={{ fontSize: 12, color: C.labelSecondary, lineHeight: 1.65, letterSpacing: '-0.01em' }}>
              공개 데이터 규칙 기반 · 실시간 교통 정보 아님 · 인과 관계를 보장하지 않습니다
            </p>
          </div>
        </SectionCard>
      </div>

    </div>
  )
}

// ─── Result Card ──────────────────────────────────────────────────────────────
function ResultCard({ dest, expanded, onToggle }: {
  dest: Destination; expanded: boolean; onToggle: () => void
}) {
  const dark = dest.rank === 1
  return (
    <div style={{
      background: dark ? C.navy : C.card,
      borderRadius: 14,
      overflow: 'hidden',
      boxShadow: dark ? '0 6px 24px rgba(13,27,75,0.24)' : '0 1px 3px rgba(0,0,0,0.06)',
    }}>
      <div style={{ padding: '14px 16px' }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 10 }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10, flex: 1 }}>
            <span style={{ fontSize: 10, fontWeight: 700, color: dark ? '#475569' : C.slateLight,
              letterSpacing: '0.06em', minWidth: 18, paddingTop: 3 }}>
              {String(dest.rank).padStart(2,'0')}
            </span>
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginBottom: 3 }}>
                <span style={{ fontSize: dark ? 20 : 18, fontWeight: 800,
                  color: dark ? '#F1F5F9' : C.navy, letterSpacing: '-0.04em' }}>
                  {dest.name}
                </span>
                <span style={{ fontSize: 12, color: dark ? '#475569' : C.slate }}>{dest.district}</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 14, fontWeight: 700, color: dark ? '#60A5FA' : C.cobalt, letterSpacing: '-0.02em' }}>
                  {dest.time}분
                </span>
                <span style={{ width: 3, height: 3, borderRadius: '50%', background: dark ? '#334155' : C.slateLight, flexShrink: 0 }} />
                <span style={{ fontSize: 12, color: dark ? '#475569' : C.slate }}>{dest.cost}</span>
              </div>
            </div>
          </div>
          <ScoreRing score={dest.score} dark={dark} />
        </div>

        {/* Tags */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, marginBottom: 9 }}>
          {dest.tags.map(t => (
            <span key={t} style={{
              padding: '3px 9px', borderRadius: 6, fontSize: 11, fontWeight: 500,
              background: dark ? 'rgba(99,118,255,0.22)' : C.cobaltLight,
              color: dark ? '#A5B4FC' : '#3730A3', letterSpacing: '-0.01em',
            }}>{t}</span>
          ))}
        </div>

        {/* Reason */}
        <p style={{ fontSize: 12, color: dark ? '#64748B' : C.labelSecondary,
          lineHeight: 1.65, letterSpacing: '-0.01em', marginBottom: 10 }}>
          {dest.reason}
        </p>

        {/* Expand toggle */}
        <button onClick={onToggle} style={{
          fontSize: 12, fontWeight: 600, color: dark ? '#60A5FA' : C.cobalt,
          background: 'none', border: 'none', cursor: 'pointer', padding: 0,
          fontFamily: "'Noto Sans KR', system-ui, sans-serif", letterSpacing: '-0.01em',
          display: 'flex', alignItems: 'center', gap: 4,
        }}>
          {expanded ? '추천 근거 접기 ↑' : '추천 근거 보기 ↓'}
        </button>
      </div>

      {expanded && (
        <div style={{ padding: '14px 16px', background: dark ? 'rgba(255,255,255,0.04)' : '#F8FAFC',
          borderTop: dark ? '1px solid rgba(255,255,255,0.07)' : `1px solid ${C.border}` }}>
          {[['사용 신호', dest.detail.signal], ['순위 방식', dest.detail.method], ['데이터 기준', dest.detail.vintage]].map(([k, v]) => (
            <div key={k} style={{ display: 'flex', gap: 8, marginBottom: 8, alignItems: 'flex-start' }}>
              <span style={{ fontSize: 10, fontWeight: 700, color: dark ? '#475569' : C.slate,
                minWidth: 72, flexShrink: 0, paddingTop: 1, letterSpacing: '0.02em' }}>{k}</span>
              <span style={{ fontSize: 11, color: dark ? '#64748B' : C.labelSecondary, lineHeight: 1.6 }}>{v}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ─── Results Screen ───────────────────────────────────────────────────────────
function ResultsScreen({ onBack, purpose }: { onBack: () => void; purpose: string }) {
  const [expanded, setExpanded] = useState<number|null>(null)
  const [showEmpty, setShowEmpty] = useState(false)
  const destinations = getDestinationsForPurpose(purpose)

  return (
    <div style={{ flex: 1, overflowY: 'auto', background: C.bg }}>
      <div style={{ padding: '8px 16px 32px', display: 'flex', flexDirection: 'column', gap: 14 }}>
        {/* Summary */}
        <div style={{ paddingTop: 4 }}>
          <h2 style={{ fontSize: 28, fontWeight: 800, color: C.navy, letterSpacing: '-0.04em', lineHeight: 1.2, marginBottom: 4 }}>
            추천 결과
          </h2>
          <p style={{ fontSize: 13, color: C.labelSecondary, letterSpacing: '-0.01em' }}>
            외대앞역 · 30분 이내 · 주말 저녁 · {purpose}
          </p>
        </div>

        {/* Filter chips */}
        <div style={{ display: 'flex', gap: 7, flexWrap: 'wrap' }}>
          {['주말', '18:00–21:00', purpose, '30분 이내'].map(chip => (
            <span key={chip} style={{
              padding: '5px 12px', background: C.cobaltLight, color: '#3730A3',
              fontSize: 12, fontWeight: 600, borderRadius: 100, border: '1px solid #C7D2FE', letterSpacing: '-0.01em',
            }}>{chip}</span>
          ))}
        </div>

        {/* Count bar */}
        <SectionCard>
          <div style={{ padding: '12px 16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <span style={{ fontSize: 13, color: C.labelSecondary, letterSpacing: '-0.01em' }}>도달 가능 후보 </span>
              <span style={{ fontSize: 13, fontWeight: 700, color: C.navy, letterSpacing: '-0.02em' }}>18개</span>
              <span style={{ fontSize: 13, color: C.labelSecondary, letterSpacing: '-0.01em' }}> 중 상위 </span>
              <span style={{ fontSize: 13, fontWeight: 700, color: C.cobalt, letterSpacing: '-0.02em' }}>5개</span>
            </div>
            <button onClick={() => setShowEmpty(!showEmpty)} style={{
              fontSize: 12, fontWeight: 600, color: C.cobalt, background: 'none', border: 'none',
              cursor: 'pointer', fontFamily: "'Noto Sans KR', system-ui, sans-serif", letterSpacing: '-0.01em',
            }}>비교 보기</button>
          </div>
        </SectionCard>

        {showEmpty ? (
          /* Empty state */
          <SectionCard>
            <div style={{ padding: '40px 24px', display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center' }}>
              <div style={{ width: 52, height: 52, borderRadius: '50%', background: C.bg,
                display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 14 }}>
                <svg viewBox="0 0 24 24" width="26" height="26" fill="none">
                  <circle cx="12" cy="12" r="9" stroke={C.slate} strokeWidth="1.5"/>
                  <path d="M9 15c0-1.657 1.343-3 3-3s3 1.343 3 3" stroke={C.slate} strokeWidth="1.5" strokeLinecap="round"/>
                  <circle cx="9" cy="9" r="1" fill={C.slate}/><circle cx="15" cy="9" r="1" fill={C.slate}/>
                </svg>
              </div>
              <p style={{ fontSize: 16, fontWeight: 700, color: C.navy, letterSpacing: '-0.03em', marginBottom: 6 }}>
                조건을 만족하는 후보가 없어요
              </p>
              <p style={{ fontSize: 13, color: C.labelSecondary, lineHeight: 1.6, letterSpacing: '-0.01em', marginBottom: 20 }}>
                설정한 이동시간 안에 도달 가능한<br />상권 후보를 찾지 못했습니다.
              </p>
              <div style={{ display: 'flex', gap: 8, width: '100%' }}>
                <button onClick={() => setShowEmpty(false)} style={{
                  flex: 1, padding: '12px', background: C.cobaltLight, color: '#3730A3',
                  border: '1px solid #C7D2FE', borderRadius: 10, fontSize: 14, fontWeight: 600,
                  cursor: 'pointer', fontFamily: "'Noto Sans KR', system-ui, sans-serif", letterSpacing: '-0.01em',
                }}>이동시간 늘리기</button>
                <button onClick={() => setShowEmpty(false)} style={{
                  flex: 1, padding: '12px', background: C.bg, color: C.labelSecondary,
                  border: `1px solid ${C.border}`, borderRadius: 10, fontSize: 14, fontWeight: 600,
                  cursor: 'pointer', fontFamily: "'Noto Sans KR', system-ui, sans-serif", letterSpacing: '-0.01em',
                }}>목적 변경하기</button>
              </div>
            </div>
          </SectionCard>
        ) : (
          /* Destination cards */
          <>
            {destinations.map(dest => (
              <ResultCard key={dest.rank} dest={dest}
                expanded={expanded === dest.rank}
                onToggle={() => setExpanded(expanded === dest.rank ? null : dest.rank)} />
            ))}

            {/* Comparison card */}
            <SectionCard>
              <div style={{ padding: '14px 16px' }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: C.slate, letterSpacing: '0.04em', marginBottom: 10 }}>
                  비교: 최단거리 vs 데이터 기반
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr', gap: 0 }}>
                  <div style={{ padding: '10px 0' }}>
                    <div style={{ fontSize: 11, fontWeight: 700, color: C.slate, letterSpacing: '0.04em', marginBottom: 4 }}>단순 최단거리</div>
                    <div style={{ fontSize: 15, fontWeight: 700, color: C.navy, marginBottom: 2 }}>건대입구</div>
                    <div style={{ fontSize: 12, color: C.slate }}>22분 · 시간 최단</div>
                    <div style={{ fontSize: 11, color: C.slateLight, marginTop: 4, lineHeight: 1.4 }}>맥락 미반영</div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', padding: '0 14px' }}>
                    <span style={{ fontSize: 11, fontWeight: 700, color: C.slateLight }}>VS</span>
                  </div>
                  <div style={{ padding: '10px 0' }}>
                    <div style={{ fontSize: 11, fontWeight: 700, color: C.cobalt, letterSpacing: '0.04em', marginBottom: 4 }}>데이터 기반</div>
                    <div style={{ fontSize: 15, fontWeight: 700, color: C.navy, marginBottom: 2 }}>성수동</div>
                    <div style={{ fontSize: 12, color: C.cobalt }}>27분 · 적합도 94</div>
                    <div style={{ fontSize: 11, color: C.cobalt, marginTop: 4, lineHeight: 1.4, opacity: 0.7 }}>주말 저녁·식사 반영</div>
                  </div>
                </div>
              </div>
              <div style={{ padding: '10px 16px', background: C.cobaltPale, borderTop: `1px solid ${C.border}` }}>
                <p style={{ fontSize: 11, color: '#3730A3', lineHeight: 1.55, letterSpacing: '-0.01em' }}>
                  단순히 가장 가까운 곳이 아닌, 조건에 맞게 도달 가능하고 맥락에 적합한 후보를 추천합니다.
                </p>
              </div>
            </SectionCard>
          </>
        )}
      </div>
    </div>
  )
}

// ─── Info Screen ──────────────────────────────────────────────────────────────
function InfoScreen() {
  return (
    <div style={{ flex: 1, overflowY: 'auto', background: C.bg }}>
      <div style={{ padding: '8px 16px 32px', display: 'flex', flexDirection: 'column', gap: 20 }}>
        <div style={{ paddingTop: 4 }}>
          <h2 style={{ fontSize: 28, fontWeight: 800, color: C.navy, letterSpacing: '-0.04em', marginBottom: 4 }}>정보</h2>
          <p style={{ fontSize: 14, color: C.labelSecondary, letterSpacing: '-0.02em' }}>추천 방식과 데이터 기준</p>
        </div>

        {/* How it works */}
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: C.labelSecondary, letterSpacing: '-0.01em',
            textTransform: 'uppercase', marginBottom: 8, paddingLeft: 4 }}>추천 방식</div>
          <SectionCard>
            {[
              { icon: '✓', color: C.cobalt, title: '도달 가능성 먼저', body: '최대 이동시간을 초과하는 후보를 순위 계산 전에 모두 제외합니다.' },
              { icon: '◎', color: C.emerald, title: '조건 적합성', body: '시간대·목적 조건에 맞는 과거 관측 유입 신호로 남은 후보를 순위화합니다.' },
              { icon: '≡', color: '#7C3AED', title: '설명 가능성', body: '추천 이유, 사용 데이터, 기준 시점, 한계를 결과에서 직접 확인할 수 있습니다.' },
            ].map((item, i, arr) => (
              <div key={item.title}>
                <div style={{ padding: '14px 16px', display: 'flex', gap: 12, alignItems: 'flex-start' }}>
                  <div style={{ width: 32, height: 32, borderRadius: 8, background: `${item.color}18`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                    fontSize: 14, color: item.color, fontWeight: 700 }}>{item.icon}</div>
                  <div>
                    <div style={{ fontSize: 15, fontWeight: 600, color: C.navy, letterSpacing: '-0.02em', marginBottom: 3 }}>{item.title}</div>
                    <div style={{ fontSize: 13, color: C.labelSecondary, lineHeight: 1.6, letterSpacing: '-0.01em' }}>{item.body}</div>
                  </div>
                </div>
                {i < arr.length - 1 && <Divider />}
              </div>
            ))}
          </SectionCard>
        </div>

        {/* Limitations */}
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: C.labelSecondary, letterSpacing: '-0.01em',
            textTransform: 'uppercase', marginBottom: 8, paddingLeft: 4 }}>한계 안내</div>
          <SectionCard>
            <div style={{ padding: '14px 16px', display: 'flex', gap: 10, alignItems: 'flex-start' }}>
              <span style={{ fontSize: 16, flexShrink: 0 }}>⚠️</span>
              <p style={{ fontSize: 13, color: C.labelSecondary, lineHeight: 1.7, letterSpacing: '-0.01em' }}>
                본 결과는 <strong style={{ color: C.navy, fontWeight: 600 }}>공개 데이터 기반의 규칙형 MVP</strong>입니다.
                실시간 교통·매장 영업 상태·개인 맞춤 추천을 보장하지 않습니다. 관측 데이터의 상관 패턴이 반영된 것이며, 인과 관계나 방문 결과를 예측하지 않습니다.
              </p>
            </div>
          </SectionCard>
        </div>

        {/* About */}
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: C.labelSecondary, letterSpacing: '-0.01em',
            textTransform: 'uppercase', marginBottom: 8, paddingLeft: 4 }}>프로젝트</div>
          <SectionCard>
            <FormRow label="팀" value="MAXIMUS" />
            <Divider />
            <FormRow label="단계" value="F0 Public Data MVP" />
            <Divider />
            <FormRow label="데이터" value="공개·공공 데이터" />
            <Divider />
            <FormRow label="순위 방식" value="F0-public-rule" />
            <Divider />
            <FormRow label="버전" value="0.1.0" />
          </SectionCard>
        </div>
      </div>
    </div>
  )
}

// ─── Tab Bar ──────────────────────────────────────────────────────────────────
const TAB_ICONS = {
  home: (active: boolean) => (
    <svg viewBox="0 0 24 24" width="24" height="24" fill="none">
      <path d="M3 9.5L12 3l9 6.5V20a1 1 0 01-1 1H5a1 1 0 01-1-1V9.5z"
        fill={active ? C.cobalt : 'none'} stroke={active ? C.cobalt : C.slateLight} strokeWidth="1.6" strokeLinejoin="round"/>
      <path d="M9 21V12h6v9" stroke={active ? 'white' : C.slateLight} strokeWidth="1.6" strokeLinecap="round"/>
    </svg>
  ),
  results: (active: boolean) => (
    <svg viewBox="0 0 24 24" width="24" height="24" fill="none">
      <path d="M12 2l2.4 7.4H22l-6.2 4.5 2.4 7.4L12 17l-6.2 4.3 2.4-7.4L2 9.4h7.6L12 2z"
        fill={active ? C.cobalt : 'none'} stroke={active ? C.cobalt : C.slateLight} strokeWidth="1.6" strokeLinejoin="round"/>
    </svg>
  ),
  info: (active: boolean) => (
    <svg viewBox="0 0 24 24" width="24" height="24" fill="none">
      <circle cx="12" cy="12" r="9" fill={active ? C.cobalt : 'none'} stroke={active ? C.cobalt : C.slateLight} strokeWidth="1.6"/>
      <path d="M12 11v6M12 8v.5" stroke={active ? 'white' : C.slateLight} strokeWidth="1.8" strokeLinecap="round"/>
    </svg>
  ),
}

function TabBar({ tab, onTabChange }: { tab: string; onTabChange: (t: string) => void }) {
  const tabs = [
    { id: 'home', label: '홈' },
    { id: 'results', label: '추천' },
    { id: 'info', label: '정보' },
  ]
  return (
    <div style={{
      height: 83, display: 'flex', flexShrink: 0,
      background: 'rgba(255,255,255,0.92)',
      backdropFilter: 'blur(20px)',
      borderTop: `1px solid ${C.border}`,
    }}>
      {tabs.map(t => (
        <button key={t.id} onClick={() => onTabChange(t.id)} style={{
          flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center',
          justifyContent: 'center', gap: 3, background: 'none', border: 'none', cursor: 'pointer',
          paddingBottom: 16,
        }}>
          {TAB_ICONS[t.id as keyof typeof TAB_ICONS](tab === t.id)}
          <span style={{
            fontSize: 10, fontWeight: tab === t.id ? 600 : 400,
            color: tab === t.id ? C.cobalt : C.slateLight,
            fontFamily: "'Noto Sans KR', system-ui, sans-serif", letterSpacing: '-0.01em',
          }}>{t.label}</span>
        </button>
      ))}
    </div>
  )
}

// ─── iOS Nav Bar ──────────────────────────────────────────────────────────────
function NavBar({ title, showBack, onBack }: { title: string; showBack?: boolean; onBack?: () => void }) {
  return (
    <div style={{
      height: 44, flexShrink: 0, display: 'flex', alignItems: 'center',
      justifyContent: 'center', position: 'relative',
      background: 'rgba(242,242,247,0.92)', backdropFilter: 'blur(20px)',
      borderBottom: `1px solid ${C.border}`,
    }}>
      {showBack && (
        <button onClick={onBack} style={{
          position: 'absolute', left: 8, padding: '6px 10px',
          background: 'none', border: 'none', cursor: 'pointer',
          display: 'flex', alignItems: 'center', gap: 3,
          color: C.cobalt, fontSize: 17, fontFamily: '-apple-system, "Noto Sans KR", sans-serif',
        }}>
          <svg viewBox="0 0 10 17" width="10" height="17" fill="none">
            <path d="M8.5 1.5L1.5 8.5l7 7" stroke={C.cobalt} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </button>
      )}
      <span style={{ fontSize: 17, fontWeight: 600, color: C.navy,
        letterSpacing: '-0.02em', fontFamily: "'Noto Sans KR', system-ui, sans-serif" }}>
        {title}
      </span>
    </div>
  )
}

// ─── Main App ─────────────────────────────────────────────────────────────────
type AppState = 'splash' | 'app'

export default function App() {
  const [appState, setAppState] = useState<AppState>('splash')
  const [tab, setTab] = useState('home')
  const [hasSearched, setHasSearched] = useState(false)
  const [searchedPurpose, setSearchedPurpose] = useState('식사')
  const [origin, setOrigin] = useState<LocationValue>({ name: '외대앞역', sub: '서울 동대문구 회기동' })
  const [showLocationSheet, setShowLocationSheet] = useState(false)
  const [showMapSheet, setShowMapSheet] = useState(false)
  const [pendingMapLoc, setPendingMapLoc] = useState<LocationValue | null>(null)
  const [showCalendarSheet, setShowCalendarSheet] = useState(false)
  const [dateTime, setDateTime] = useState<DateTimeValue>(() => {
    const now = new Date()
    return { date: now, slot: detectSlot(now) }
  })

  const handleSearch = (purpose: string, purposeDisplay: string) => { setSearchedPurpose(purposeDisplay || purpose); setHasSearched(true); setTab('results') }
  const handleTabChange = (t: string) => setTab(t)

  const S = 0.82, PW = 390, PH = 844

  return (
    <div style={{
      minHeight: '100vh',
      background: 'radial-gradient(ellipse at 60% 30%, #1E2D6B 0%, #0A0E1A 100%)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: '32px 20px',
      fontFamily: "'Noto Sans KR', system-ui, sans-serif",
    }}>
      <style>{`
        @keyframes logoIn  { from { opacity:0; transform:scale(0.85) } to { opacity:1; transform:scale(1) } }
        @keyframes fadeUp  { from { opacity:0; transform:translateY(16px) } to { opacity:1; transform:translateY(0) } }
        @keyframes sheetUp { from { transform:translateY(100%) } to { transform:translateY(0) } }
        @keyframes spin    { to { transform:rotate(360deg) } }
      `}</style>

      {/* iPhone frame wrapper */}
      <div style={{ width: PW * S, height: PH * S, position: 'relative', flexShrink: 0 }}>
        <div style={{
          width: PW, height: PH,
          position: 'absolute', top: 0, left: 0,
          transformOrigin: 'top left',
          transform: `scale(${S})`,
          background: '#FFFFFF',
          borderRadius: 54,
          boxShadow: '0 0 0 11px #1C1C1E, 0 0 0 12px #3A3A3C, 0 48px 120px rgba(0,0,0,0.7)',
          overflow: 'hidden',
          display: 'flex', flexDirection: 'column',
        }}>
          <DynamicIsland />

          {appState === 'splash' ? (
            <>
              <StatusBar />
              <SplashScreen onSignIn={() => setAppState('app')} />
              <HomeIndicator />
            </>
          ) : (
            <>
              <StatusBar />
              {tab === 'home' && <NavBar title="어디가지" />}
              {tab === 'results' && <NavBar title="추천 결과" showBack onBack={() => setTab('home')} />}
              {tab === 'info' && <NavBar title="정보" />}

              <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column',
                animation: 'fadeUp 0.3s ease both', position: 'relative' }} key={tab}>
                {tab === 'home' && <HomeScreen
                  onSearch={handleSearch}
                  onOpenLocation={() => setShowLocationSheet(true)}
                  onOpenCalendar={() => setShowCalendarSheet(true)}
                  origin={origin}
                  dateTime={dateTime}
                  setDateTime={setDateTime}
                />}
                {tab === 'results' && (
                  hasSearched
                    ? <ResultsScreen onBack={() => setTab('home')} purpose={searchedPurpose} />
                    : <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center',
                        justifyContent: 'center', background: C.bg, padding: '32px', gap: 12 }}>
                        <div style={{ width: 56, height: 56, borderRadius: '50%', background: C.cobaltLight,
                          display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                          <PinIcon size={32} />
                        </div>
                        <p style={{ fontSize: 16, fontWeight: 700, color: C.navy, letterSpacing: '-0.03em', textAlign: 'center' }}>
                          아직 검색 결과가 없어요
                        </p>
                        <p style={{ fontSize: 13, color: C.labelSecondary, textAlign: 'center', lineHeight: 1.6, letterSpacing: '-0.01em' }}>
                          홈에서 조건을 입력하고<br/>추천 보기를 눌러주세요
                        </p>
                        <button onClick={() => setTab('home')} style={{
                          marginTop: 4, padding: '12px 28px', background: C.navy, color: 'white',
                          border: 'none', borderRadius: 12, fontSize: 15, fontWeight: 700, cursor: 'pointer',
                          fontFamily: "'Noto Sans KR', system-ui, sans-serif", letterSpacing: '-0.02em',
                        }}>홈으로</button>
                      </div>
                )}
                {tab === 'info' && <InfoScreen />}
              </div>

              <TabBar tab={tab} onTabChange={handleTabChange} />
              <HomeIndicator />

              {/* Location sheet */}
              {showLocationSheet && (
                <div style={{ position: 'absolute', inset: 0, zIndex: 200 }}>
                  <LocationSheet
                    onClose={() => setShowLocationSheet(false)}
                    onSelect={loc => { setPendingMapLoc(loc); setShowMapSheet(true) }}
                  />
                  {showMapSheet && pendingMapLoc && (
                    <MapDetailSheet
                      initialLocation={pendingMapLoc}
                      onBack={() => setShowMapSheet(false)}
                      onConfirm={loc => {
                        setOrigin(loc)
                        setShowMapSheet(false)
                        setShowLocationSheet(false)
                        setPendingMapLoc(null)
                      }}
                    />
                  )}
                </div>
              )}

              {/* Calendar sheet */}
              {showCalendarSheet && (
                <div style={{ position: 'absolute', inset: 0, zIndex: 200 }}>
                  <CalendarSheet
                    value={dateTime}
                    onClose={() => setShowCalendarSheet(false)}
                    onSelect={v => { setDateTime(v); setShowCalendarSheet(false) }}
                  />
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
