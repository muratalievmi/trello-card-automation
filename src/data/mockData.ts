export interface Account {
  id: string
  name: string
  type: string
  balance: number
  color: string
}

export interface Alert {
  id: string
  type: 'warning' | 'info'
  icon: string
  message: string
}

export interface Obligation {
  id: string
  name: string
  amount: number
  dueDate: string
  type: 'payable' | 'receivable'
}

export interface FixedCost {
  id: string
  name: string
  amount: number
  dueDate: string
  isPastDue: boolean
}

export const accounts: Account[] = [
  {
    id: 'mbank',
    name: 'МБАНК',
    type: 'Эквайринг',
    balance: 523_400,
    color: '#3b82f6',
  },
  {
    id: 'mbusiness',
    name: 'МБИЗНЕС',
    type: 'Расчетный',
    balance: 412_600,
    color: '#8b5cf6',
  },
  {
    id: 'bakai',
    name: 'БАКАЙ',
    type: 'Расчетный',
    balance: 298_000,
    color: '#06b6d4',
  },
  {
    id: 'cash',
    name: 'Касса',
    type: 'Наличные',
    balance: 216_000,
    color: '#22c55e',
  },
]

export const totalCash = accounts.reduce((sum, a) => sum + a.balance, 0)

export const alerts: Alert[] = [
  {
    id: 'gap',
    type: 'warning',
    icon: '⚠️',
    message: 'Кассовый разрыв 25.02. Нехватка средств для оплаты Поставщику «АзияСнаб» — дефицит 87 000 сом.',
  },
  {
    id: 'tax',
    type: 'info',
    icon: '🏦',
    message: 'Заморожено под налоги (15.03): 145 000 сом.',
  },
]

export const payables: Obligation[] = [
  {
    id: 'p1',
    name: 'АзияСнаб (товар)',
    amount: 210_000,
    dueDate: '25.02',
    type: 'payable',
  },
  {
    id: 'p2',
    name: 'Аренда офис + склад',
    amount: 85_000,
    dueDate: '01.03',
    type: 'payable',
  },
  {
    id: 'p3',
    name: 'Логистика «ТрансЛайн»',
    amount: 42_000,
    dueDate: '05.03',
    type: 'payable',
  },
  {
    id: 'p4',
    name: 'Маркетинг (Instagram)',
    amount: 35_000,
    dueDate: '10.03',
    type: 'payable',
  },
]

export const receivables: Obligation[] = [
  {
    id: 'r1',
    name: 'ООО «ГринМаркет»',
    amount: 180_000,
    dueDate: '22.02',
    type: 'receivable',
  },
  {
    id: 'r2',
    name: 'ИП Асанов (опт)',
    amount: 95_000,
    dueDate: '28.02',
    type: 'receivable',
  },
  {
    id: 'r3',
    name: 'Café «Жашыл»',
    amount: 48_000,
    dueDate: '03.03',
    type: 'receivable',
  },
]

export const totalPayable = payables.reduce((sum, p) => sum + p.amount, 0)
export const totalReceivable = receivables.reduce((sum, r) => sum + r.amount, 0)

export const fixedCosts: FixedCost[] = [
  {
    id: 'fc1',
    name: 'Интернет Homeline',
    amount: 2_310,
    dueDate: '20.02',
    isPastDue: true,
  },
  {
    id: 'fc2',
    name: 'Электроэнергия',
    amount: 3_389,
    dueDate: '10.02',
    isPastDue: true,
  },
  {
    id: 'fc3',
    name: 'Зарплата (5 сотр.)',
    amount: 175_000,
    dueDate: '01.03',
    isPastDue: false,
  },
  {
    id: 'fc4',
    name: 'Бухгалтер (аутсорс)',
    amount: 12_000,
    dueDate: '05.03',
    isPastDue: false,
  },
  {
    id: 'fc5',
    name: 'CRM подписка',
    amount: 4_500,
    dueDate: '15.03',
    isPastDue: false,
  },
  {
    id: 'fc6',
    name: 'Телефония (SIP)',
    amount: 1_800,
    dueDate: '20.03',
    isPastDue: false,
  },
]

export const totalFixedCosts = fixedCosts.reduce((sum, c) => sum + c.amount, 0)
