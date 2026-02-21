export function formatCurrency(amount: number): string {
  return amount.toLocaleString('ru-RU').replace(/,/g, ' ') + ' сом'
}

export function formatNumber(amount: number): string {
  return amount.toLocaleString('ru-RU').replace(/,/g, ' ')
}
