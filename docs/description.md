# Архитектура проекта

## Диаграмма классов

```
AbstractAccount (ABC)
├── _id: str
├── _owner: Owner
├── _balance: Decimal
├── _status: str
├── _currency: str
├── deposit(summ) [abstract]
├── withdraw(summ) [abstract]
└── get_account_info() [abstract]
        │
        ▼
BankAccount(AbstractAccount)
├── CURRENCIES: tuple
├── _validate_amount(summ) [static]
├── _validate_currency(currency) [static]
├── _check_status()
├── deposit(summ)
├── withdraw(summ)
├── get_account_info() -> dict
├── active() / freeze() / close()
│
├───▶ SavingsAccount(BankAccount)
│     ├── _min_balance: Decimal
│     ├── _monthly_rate: Decimal
│     ├── withdraw(summ)          # проверка мин. остатка
│     ├── apply_monthly_interest()
│     ├── get_account_info()      # + type, min_balance, rate
│     └── __str__()
│
├───▶ PremiumAccount(BankAccount)
│     ├── _overdraft_limit: Decimal
│     ├── _withdraw_fee: Decimal
│     ├── withdraw(summ)          # овердрафт + комиссия
│     ├── get_account_info()      # + type, overdraft, fee
│     └── __str__()
│
└───▶ InvestmentAccount(BankAccount)
      ├── _portfolio: dict[str, Decimal]
      ├── ASSET_TYPES: tuple
      ├── GROWTH_RATES: dict
      ├── buy_asset(type, amount)
      ├── sell_asset(type, amount)
      ├── project_yearly_growth()
      ├── withdraw(summ)          # только свободные средства
      ├── get_account_info()      # + type, portfolio
      └── __str__()
```

## Принципы

- **AbstractAccount** — контракт: определяет ЧТО должен уметь счёт
- **BankAccount** — базовая реализация: КАК это работает
- **SavingsAccount/PremiumAccount/InvestmentAccount** — специализации с переопределением `withdraw()`, `get_account_info()`, `__str__()`
- Полиморфизм: все счета обрабатываются через единый интерфейс
- Валидация и управление статусами наследуются от BankAccount
- `super().get_account_info()` — переиспользование базовой логики

## Статусы счёта

```
active ──freeze()──▶ frozen
active ──close()───▶ closed
frozen ──active()──▶ active
closed ──(нельзя больше ничего)
```