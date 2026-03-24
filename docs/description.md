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

Client
├── _id: str
├── _first_name, _last_name: str
├── _age: int (>= 18)
├── _phone, _email: str | None
├── _status: str (active / blocked)
├── _accounts: list[str]
├── _pin: str
├── _failed_attempts: int
├── _suspicious: bool
├── full_name [property]
├── add_account(account_id)
├── remove_account(account_id)
└── set_pin(pin)

Bank (фасад)
├── _name: str
├── _clients: dict[str, Client]
├── _accounts: dict[str, BankAccount]
├── _log: list[str]
├── add_client(client)
├── get_client(client_id)
├── authenticate_client(client_id, pin)
├── open_account(client_id, type, currency, **kwargs)
├── close_account(client_id, account_id)
├── freeze_account(client_id, account_id)
├── unfreeze_account(client_id, account_id)
├── search_accounts(client_id?, currency?, status?, type?)
├── get_total_balance(client_id?)
└── get_clients_ranking()
```

## Принципы

- **AbstractAccount** — контракт: определяет ЧТО должен уметь счёт
- **BankAccount** — базовая реализация: КАК это работает
- **SavingsAccount/PremiumAccount/InvestmentAccount** — специализации с переопределением `withdraw()`, `get_account_info()`, `__str__()`
- **Client** — клиент банка с аутентификацией и списком счетов
- **Bank** — фасад: управляет клиентами, счетами, безопасностью
- Полиморфизм: все счета обрабатываются через единый интерфейс
- Валидация и управление статусами наследуются от BankAccount
- `super().get_account_info()` — переиспользование базовой логики

## Безопасность

- 3 неверных PIN → блокировка клиента
- Пометка подозрительных действий (_suspicious)
- Запрет операций с 00:00 до 05:00
- Журнал всех действий (_log)

## Статусы счёта

```
active ──freeze()──▶ frozen
active ──close()───▶ closed
frozen ──active()──▶ active
closed ──(нельзя больше ничего)
```

## Статусы клиента

```
active ──(3 неверных PIN)──▶ blocked
```