import { Scale, ArrowUpRight, ArrowDownRight } from 'lucide-react'
import {
  payables,
  receivables,
  totalPayable,
  totalReceivable,
} from '../data/mockData'
import { formatCurrency } from '../utils'

export default function ObligationsSection() {
  return (
    <section className="flex-1 min-w-0">
      <div className="flex items-center gap-2 mb-3">
        <Scale size={16} className="text-text-muted" />
        <h2 className="text-xs font-medium text-text-muted uppercase tracking-wider">
          Весы обязательств
        </h2>
      </div>

      <div className="bg-surface-card rounded-2xl overflow-hidden">
        {/* Payables */}
        <div className="p-4 border-b border-surface-elevated">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-1.5">
              <ArrowUpRight size={14} className="text-accent-red" />
              <span className="text-xs font-medium text-accent-red">
                Кому мы должны
              </span>
            </div>
            <span className="text-sm font-semibold font-mono text-accent-red">
              {formatCurrency(totalPayable)}
            </span>
          </div>
          <ul className="space-y-2.5">
            {payables.map((item) => (
              <li key={item.id} className="flex items-center justify-between">
                <div className="flex items-center gap-2 min-w-0">
                  <div className="w-1.5 h-1.5 rounded-full bg-accent-red shrink-0" />
                  <span className="text-sm text-text-secondary truncate">
                    {item.name}
                  </span>
                </div>
                <div className="flex items-center gap-3 shrink-0 ml-2">
                  <span className="text-sm font-mono text-text-primary">
                    {formatCurrency(item.amount)}
                  </span>
                  <span className="text-xs text-text-muted">{item.dueDate}</span>
                </div>
              </li>
            ))}
          </ul>
        </div>

        {/* Receivables */}
        <div className="p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-1.5">
              <ArrowDownRight size={14} className="text-accent-green" />
              <span className="text-xs font-medium text-accent-green">
                Кто должен нам
              </span>
            </div>
            <span className="text-sm font-semibold font-mono text-accent-green">
              {formatCurrency(totalReceivable)}
            </span>
          </div>
          <ul className="space-y-2.5">
            {receivables.map((item) => (
              <li key={item.id} className="flex items-center justify-between">
                <div className="flex items-center gap-2 min-w-0">
                  <div className="w-1.5 h-1.5 rounded-full bg-accent-green shrink-0" />
                  <span className="text-sm text-text-secondary truncate">
                    {item.name}
                  </span>
                </div>
                <div className="flex items-center gap-3 shrink-0 ml-2">
                  <span className="text-sm font-mono text-text-primary">
                    {formatCurrency(item.amount)}
                  </span>
                  <span className="text-xs text-text-muted">{item.dueDate}</span>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  )
}
