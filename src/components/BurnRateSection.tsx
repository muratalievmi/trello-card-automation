import { Flame, AlertCircle } from 'lucide-react'
import { fixedCosts, totalFixedCosts } from '../data/mockData'
import { formatCurrency } from '../utils'

export default function BurnRateSection() {
  return (
    <section className="flex-1 min-w-0">
      <div className="flex items-center gap-2 mb-3">
        <Flame size={16} className="text-text-muted" />
        <h2 className="text-xs font-medium text-text-muted uppercase tracking-wider">
          Постоянные расходы
        </h2>
      </div>

      <div className="bg-surface-card rounded-2xl p-4">
        <div className="flex items-center justify-between mb-4">
          <span className="text-xs text-text-muted">Итого в месяц</span>
          <span className="text-sm font-semibold font-mono text-text-primary">
            {formatCurrency(totalFixedCosts)}
          </span>
        </div>

        <ul className="space-y-2.5">
          {fixedCosts.map((cost) => (
            <li key={cost.id} className="flex items-center justify-between">
              <div className="flex items-center gap-2 min-w-0">
                {cost.isPastDue ? (
                  <AlertCircle size={12} className="text-accent-red shrink-0" />
                ) : (
                  <div className="w-1.5 h-1.5 rounded-full bg-text-muted shrink-0" />
                )}
                <span
                  className={`text-sm truncate ${
                    cost.isPastDue ? 'text-accent-red' : 'text-text-secondary'
                  }`}
                >
                  {cost.name}
                </span>
              </div>
              <div className="flex items-center gap-3 shrink-0 ml-2">
                <span className="text-sm font-mono text-text-primary">
                  {formatCurrency(cost.amount)}
                </span>
                <span
                  className={`text-xs ${
                    cost.isPastDue ? 'text-accent-red' : 'text-text-muted'
                  }`}
                >
                  {cost.isPastDue ? 'просрочен' : `до ${cost.dueDate}`}
                </span>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}
