import { cn } from '@/utils/cn'
import { ASSET_TYPE_META, typeColor, typeLabel } from '@/utils/assetTypes'

interface Props {
  type: string
  showIcon?: boolean
  size?: 'sm' | 'md'
}

export default function AssetTypeBadge({ type, showIcon = true, size = 'md' }: Props) {
  const meta = ASSET_TYPE_META[type]
  const Icon = meta?.icon
  const color = typeColor(type)

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full font-medium border',
        size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-xs',
      )}
      style={{
        color,
        borderColor: `${color}40`,
        backgroundColor: `${color}15`,
      }}
    >
      {showIcon && Icon && (
        <Icon className={size === 'sm' ? 'h-3 w-3' : 'h-3.5 w-3.5'} strokeWidth={2} />
      )}
      {typeLabel(type)}
    </span>
  )
}
