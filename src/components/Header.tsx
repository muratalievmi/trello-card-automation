import { User, Clock } from 'lucide-react'

export default function Header() {
  const now = new Date()
  const dateStr = now.toLocaleDateString('ru-RU', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })
  const timeStr = now.toLocaleTimeString('ru-RU', {
    hour: '2-digit',
    minute: '2-digit',
  })

  return (
    <header className="flex items-center justify-between px-4 py-3 md:px-6 md:py-4">
      <div className="flex items-center gap-2">
        <div className="w-8 h-8 rounded-lg bg-accent-green flex items-center justify-center">
          <span className="text-surface font-bold text-sm">A</span>
        </div>
        <span className="text-lg font-semibold text-text-primary tracking-tight">
          akcha.kg
        </span>
      </div>
      <div className="flex items-center gap-4">
        <div className="hidden sm:flex items-center gap-1.5 text-text-muted text-sm">
          <Clock size={14} />
          <span>{dateStr}, {timeStr}</span>
        </div>
        <button className="w-8 h-8 rounded-full bg-surface-elevated flex items-center justify-center text-text-secondary hover:text-text-primary transition-colors">
          <User size={18} />
        </button>
      </div>
    </header>
  )
}
