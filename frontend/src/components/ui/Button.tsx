import { cx, focusRing } from '../../lib/cx'

type Variant = 'primary' | 'secondary' | 'ghost'
type Size = 'sm' | 'md'

const VARIANTS: Record<Variant, string> = {
  primary: 'bg-brand text-white hover:bg-brand-hover border border-transparent shadow-xs',
  secondary:
    'bg-surface text-ink border border-line-strong hover:bg-canvas hover:border-muted/40 shadow-xs',
  ghost: 'text-text-secondary hover:text-ink hover:bg-ink/[0.04] border border-transparent',
}

const SIZES: Record<Size, string> = {
  sm: 'h-8 gap-1.5 px-2.5 text-[13px]',
  md: 'h-9 gap-2 px-3.5 text-sm',
}

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant
  size?: Size
}

export default function Button({
  variant = 'secondary',
  size = 'md',
  className,
  ...props
}: ButtonProps) {
  return (
    <button
      className={cx(
        'inline-flex items-center justify-center rounded-lg font-medium',
        // 120ms is short enough to feel instant and long enough to not snap.
        'transition-colors duration-120',
        'disabled:pointer-events-none disabled:opacity-50',
        VARIANTS[variant],
        SIZES[size],
        focusRing,
        className,
      )}
      {...props}
    />
  )
}
