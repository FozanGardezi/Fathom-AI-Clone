import type { Participant } from '../../../lib/api'
import { initials } from '../../../lib/format'
import { cx } from '../../../lib/cx'

/**
 * Overlapping initial avatars.
 *
 * There are no profile images in the data model, so initials on a tinted disc
 * are the honest version - a generic silhouette would carry less information
 * than the letters do.
 */
export default function ParticipantAvatars({
  participants,
  max = 5,
}: {
  participants: Participant[]
  max?: number
}) {
  const shown = participants.slice(0, max)
  const overflow = participants.length - shown.length

  return (
    <div className="flex items-center">
      <div className="flex -space-x-1.5">
        {shown.map((participant) => (
          <span
            key={participant.id}
            title={`${participant.display_name}${participant.is_host ? ' (host)' : ''}`}
            className={cx(
              'flex size-7 items-center justify-center rounded-full text-[10px] font-semibold',
              'ring-2 ring-surface',
              participant.is_host
                ? 'bg-brand text-white'
                : 'bg-ink/[0.06] text-text-secondary',
            )}
          >
            {initials(participant.display_name)}
          </span>
        ))}
        {overflow > 0 && (
          <span className="flex size-7 items-center justify-center rounded-full bg-ink/[0.04] text-[10px] font-semibold text-text-tertiary ring-2 ring-surface">
            +{overflow}
          </span>
        )}
      </div>
    </div>
  )
}
