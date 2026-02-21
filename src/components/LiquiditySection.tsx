import { Wallet, TrendingUp } from 'lucide-react'
import { accounts, totalCash } from '../data/mockData'
import { formatNumber } from '../utils'

export default function LiquiditySection() {
  return (
    <section className="px-4 md:px-6">
      <div className="flex items-center gap-2 mb-3">
        <TrendingUp size={16} className="text-text-muted" />
        <h2 className="text-xs font-medium text-text-muted uppercase tracking-wider">
          Кровеносная система
        </h2>
      </div>

      {/* Total Cash Card */}
      <div className="bg-surface-card rounded-2xl p-5 md:p-6 mb-3">
        <div className="flex items-center gap-2 mb-1">
          <Wallet size={16} className="text-accent-green" />
          <span className="text-sm text-text-secondary">Доступный кэш</span>
        </div>
        <p className="text-3xl md:text-4xl font-bold font-mono text-text-primary tracking-tight">
          {formatNumber(totalCash)}
          <span className="text-lg md:text-xl text-text-secondary ml-2 font-sans font-medium">сом</span>
        </p>
      </div>

      {/* Account Cards Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 md:gap-3">
        {accounts.map((account) => (
          <div
            key={account.id}
            className="bg-surface-card rounded-xl p-3.5 md:p-4"
          >
            <div className="flex items-center gap-2 mb-2">
              <div
                className="w-2 h-2 rounded-full"
                style={{ backgroundColor: account.color }}
              />
              <span className="text-xs font-medium text-text-secondary truncate">
                {account.name}
              </span>
            </div>
            <p className="text-base md:text-lg font-semibold font-mono text-text-primary">
              {formatNumber(account.balance)}
            </p>
            <p className="text-xs text-text-muted mt-0.5">{account.type}</p>
          </div>
        ))}
      </div>
    </section>
  )
}
