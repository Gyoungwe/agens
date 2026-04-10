import { cn } from '@/lib/utils'

interface StatusBadgeProps {
  status: 'idle' | 'running' | 'waiting' | 'pending' | 'approved' | 'rejected'
  className?: string
}

const statusConfig = {
  idle: { label: 'Idle', className: 'bg-muted text-muted-foreground' },
  running: { label: 'Running', className: 'bg-green-500/10 text-green-600' },
  waiting: { label: 'Waiting', className: 'bg-yellow-500/10 text-yellow-600' },
  pending: { label: 'Pending', className: 'bg-yellow-500/10 text-yellow-600' },
  approved: { label: 'Approved', className: 'bg-green-500/10 text-green-600' },
  rejected: { label: 'Rejected', className: 'bg-red-500/10 text-red-600' },
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const config = statusConfig[status]

  return (
    <span
      className={cn(
        'inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium',
        config.className,
        className
      )}
    >
      {config.label}
    </span>
  )
}
