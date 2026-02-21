import Header from './components/Header'
import LiquiditySection from './components/LiquiditySection'
import AlertsSection from './components/AlertsSection'
import ObligationsSection from './components/ObligationsSection'
import BurnRateSection from './components/BurnRateSection'

export default function App() {
  return (
    <div className="min-h-screen bg-surface max-w-4xl mx-auto pb-8">
      <Header />

      <main className="space-y-5 mt-2">
        <LiquiditySection />
        <AlertsSection />

        <div className="px-4 md:px-6">
          <div className="flex flex-col lg:flex-row gap-5">
            <ObligationsSection />
            <BurnRateSection />
          </div>
        </div>
      </main>
    </div>
  )
}
