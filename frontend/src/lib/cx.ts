/** Join class names, dropping anything falsy. */
export function cx(...parts: Array<string | false | null | undefined>) {
  return parts.filter(Boolean).join(' ')
}

/** Shared focus treatment, so every interactive element rings identically. */
export const focusRing =
  'outline-none focus-visible:ring-2 focus-visible:ring-brand/35 focus-visible:ring-offset-1 focus-visible:ring-offset-surface'
