import { ShieldAlert } from 'lucide-react'
import { alerts } from '../data/mockData'

export default function AlertsSection() {
  return (
    <section className="px-4 md:px-6">
      <div className="flex items-center gap-2 mb-3">
        <ShieldAlert size={16} className="text-text-muted" />
        <h2 className="text-xs font-medium text-text-muted uppercase tracking-wider">
          Радар угроз
        </h2>
      </div>

      <div className="space-y-2">
        {alerts.map((alert) => (
          <div
            key={alert.id}
            className={`rounded-xl p-4 ${
              alert.type === 'warning'
                ? 'bg-red-950/40 border border-red-900/30'
                : 'bg-amber-950/30 border border-amber-900/20'
            }`}
          >
            <p
              className={`text-sm leading-relaxed ${
                alert.type === 'warning' ? 'text-red-200' : 'text-amber-200'
              }`}
            >
              <span className="mr-1.5">{alert.icon}</span>
              {alert.message}
            </p>
          </div>
        ))}
      </div>
    </section>
  )
}
