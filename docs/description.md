# Архитектура проекта

## Диаграмма классов

```
AbstractAccount (ABC)
├── _id: str
├── _owner: Owner
├── _balance: float
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
├── active()
├── freeze()
└── close()
```

## Принципы

- **AbstractAccount** — контракт: определяет ЧТО должен уметь счёт
- **BankAccount** — реализация: определяет КАК это работает
- Валидация вынесена в статические методы
- UUID генерируется в BankAccount, не в абстрактном классе
- Исключения вынесены в отдельный модуль

## Статусы счёта

```
active ──freeze()──▶ frozen
active ──close()───▶ closed
frozen ──active()──▶ active
closed ──active()──▶ active # можно переоткрыть
```
