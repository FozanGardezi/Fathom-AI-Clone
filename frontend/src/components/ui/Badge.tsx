import { cx } from '../../lib/cx'

type Tone = 'neutral' | 'brand' | 'positive'

const TONES: Record<Tone, string> = {
  neutral: 'bg-ink/[0.05] text-text-secondary',
  brand: 'bg-brand-soft text-brand',
  positive: 'bg-emerald-50 text-emerald-700',
}

export default function Badge({
  tone = 'neutral',
  children,
}: {
  tone?: Tone
  children: React.ReactNode
}) {
  return (
    <span
      className={cx(
        'inline-flex items-center rounded-md px-1.5 py-0.5 text-[11px] font-medium',
        TONES[tone],
      )}
    >
      {children}
    </span>
  )
}
