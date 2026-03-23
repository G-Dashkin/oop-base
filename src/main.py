import sys
sys.tracebacklimit = 0

from decimal import Decimal
from src.models import Owner, BankAccount, SavingsAccount, PremiumAccount, InvestmentAccount
from src.exceptions import (
    AccountFrozenError, AccountClosedError,
    InvalidOperationError, InsufficientFundsError
)

if __name__ == "__main__":
    # Создаём владельца и счёт
    owner = Owner("Иван", "Иванов", 30)
    account = BankAccount(owner, "RUB")

    # Проверяем что создалось
    print(f"account id: {account._id}")
    print(f"balance: {account._balance}")
    print(f"status: {account._status}")

    # Пополнение
    print(f"Пополняем на 1000 (метод .deposit())")
    account.deposit(1000)
    print(f"balance: {account._balance}")

    # Снятие
    print(f"Снимаем 300.45 (метод .withdraw())")
    account.withdraw(300.45)
    print(f"balance: {account._balance}")

    # Информация
    info = account.get_account_info()
    print("Информация об аккаунте (метод .get_account_info()):")
    for key, value in info.items():
        print(f"  {key}: {value}")
    print("--------------------------------------")

    # Ошибка: недостаточно средств
    print("Пробуем снять 99999")
    try: account.withdraw(99999)
    except InsufficientFundsError as e: print(f"InsufficientFundsError: {e}")

    # Ошибка: отрицательная сумма
    print("Пробуем снять отрицательную сумму -100")
    try: account.deposit(-100)
    except InvalidOperationError as e: print(f"InvalidOperationError: {e}")
    print("--------------------------------------")
    print(account)
    print("--------------------------------------")

    # Заморозка
    print("Тестируем заморозку счёта")
    account.freeze()
    print(f"Статус: {account._status}")
    try: account.deposit(100)
    except AccountFrozenError as e: print(f"AccountFrozenError: {e}")
    print("--------------------------------------")

    # Закрытие
    print("Тестируем закрытие счёта")
    account.close()
    print(f"Статус: {account._status}")
    try: account.deposit(100)
    except AccountClosedError as e: print(f"AccountClosedError: {e}")
    print("--------------------------------------")

    # Открытие
    print("Тестируем открытие счёта")
    try: account.active()
    except InvalidOperationError as e: print(f"InvalidOperationError: {e}")
    print(f"Статус: {account._status}")
    print("Добавляем 100")
    try: account.deposit(100)
    except Exception as e: print(f"{e}")
    print("---")
    print(account)
    print("--------------------------------------")

    # --- SavingsAccount ---
    print("\n=== SavingsAccount ===")
    savings = SavingsAccount(owner, "RUB", min_balance=1000, monthly_rate=0.5)
    savings.deposit(10000)
    print(f"Баланс: {savings._balance}")

    # float работает корректно после фикса _to_decimal
    savings.deposit(0.1)
    print(f"Баланс после deposit(0.1): {savings._balance}")

    interest = savings.apply_monthly_interest()
    print(f"Начислен процент: {interest}")
    print(savings)

    try: savings.withdraw(9500)
    except InsufficientFundsError as e: print(f"InsufficientFundsError: {e}")

    # --- PremiumAccount ---
    print("\n=== PremiumAccount ===")
    premium = PremiumAccount(owner, "USD", overdraft_limit=5000, withdraw_commission=50)
    premium.deposit(1000)
    premium.withdraw(500)  # 500 + 50 комиссия
    print(f"После снятия 500 (+ 50 комиссия): {premium._balance}")

    premium.withdraw(800)  # уходим в овердрафт
    print(f"Овердрафт: {premium._balance}")
    print(premium)

    # Валидация конструктора
    try: PremiumAccount(owner, "USD", withdraw_commission=-100)
    except InvalidOperationError as e: print(f"Валидация конструктора: {e}")

    # --- InvestmentAccount ---
    print("\n=== InvestmentAccount ===")
    invest = InvestmentAccount(owner, "USD")
    invest.deposit(20000)
    invest.buy_asset("stocks", 8000)
    invest.buy_asset("bonds", 5000)
    invest.buy_asset("etf", 3000)
    print(f"Свободный баланс: {invest._balance}")

    projection = invest.project_yearly_growth()
    print(f"Прогноз годовой доходности: {projection['total_growth']}")
    for asset, data in projection["details"].items():
        print(f"  {asset}: {data['amount']} × {data['rate']} = +{data['growth']}")

    invest.sell_asset("bonds", 2000)
    print(f"Продал bonds на 2000, баланс: {invest._balance}")
    print(invest)

    # --- Полиморфизм ---
    print("\n=== Полиморфизм ===")
    accounts = [account, savings, premium, invest]
    for acc in accounts:
        info = acc.get_account_info()
        print(f"{type(acc).__name__}: balance={info['balance']}, status={info['status']}")