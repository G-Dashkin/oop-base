import sys

from src.bank import Client

sys.tracebacklimit = 0

from decimal import Decimal
from src.models import Owner, BankAccount, SavingsAccount, PremiumAccount, InvestmentAccount
from src.bank import Bank
from src.exceptions import (
    AccountFrozenError, AccountClosedError,
    InvalidOperationError, InsufficientFundsError,
    AuthenticationError, ClientBlockedError
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

    # === DAY 3: Система Bank ===
    print("\n\n========== DAY 3: Система Bank ==========")

    bank = Bank("СуперБанк")
    print(bank)

    # Создаём клиентов
    print("\n--- Клиенты ---")
    client1 = Client("Алексей", "Смирнов", 35, phone="+79001112233")
    client1.set_pin("1111")
    client2 = Client("Мария", "Козлова", 28, email="maria@mail.ru")
    client2.set_pin("2222")

    bank.add_client(client1)
    bank.add_client(client2)
    print(client1)
    print(client2)

    # Возраст < 18
    try: Client("Петя", "Малой", 16)
    except InvalidOperationError as e: print(f"Несовершеннолетний: {e}")

    # Аутентификация
    print("\n--- Аутентификация ---")
    bank.authenticate_client(client1._id, "1111")
    print(f"Алексей: вход успешен")

    # Неверный PIN
    try: bank.authenticate_client(client2._id, "9999")
    except AuthenticationError as e: print(f"Мария: {e}")

    # Блокировка после 3 попыток
    print("\n--- Блокировка ---")
    hacker = Client("Хакер", "Хакеров", 20)
    hacker.set_pin("7777")
    bank.add_client(hacker)

    for i in range(3):
        try: bank.authenticate_client(hacker._id, "wrong")
        except (AuthenticationError, ClientBlockedError) as e: print(f"  Попытка {i+1}: {e}")
    print(f"Статус хакера: {hacker._status}")

    # Заблокированный не может открыть счёт
    try: bank.open_account(hacker._id)
    except ClientBlockedError as e: print(f"Открытие счёта: {e}")

    # Открываем счета
    print("\n--- Счета ---")
    acc1 = bank.open_account(client1._id, "basic", "RUB")
    acc2 = bank.open_account(client1._id, "savings", "USD", min_balance=500, monthly_rate=1.0)
    acc3 = bank.open_account(client2._id, "premium", "RUB", overdraft_limit=10000)

    acc1.deposit(50000)
    acc2.deposit(10000)
    acc3.deposit(75000)

    print(f"Алексей: {len(client1._accounts)} счетов")
    print(f"Мария: {len(client2._accounts)} счетов")

    # Заморозка/разморозка через банк
    print("\n--- Заморозка ---")
    bank.freeze_account(client1._id, acc1._id)
    print(f"Счёт {acc1._id}: {acc1._status}")
    bank.unfreeze_account(client1._id, acc1._id)
    print(f"Счёт {acc1._id}: {acc1._status}")

    # Поиск
    print("\n--- Поиск ---")
    rub_accounts = bank.search_accounts(currency="RUB")
    print(f"Счетов в RUB: {len(rub_accounts)}")

    client1_accounts = bank.search_accounts(client_id=client1._id)
    print(f"Счетов у Алексея: {len(client1_accounts)}")

    # Аналитика
    print("\n--- Аналитика ---")
    print(f"Баланс Алексея: {bank.get_total_balance(client1._id)}")
    print(f"Баланс всего банка: {bank.get_total_balance()}")

    ranking = bank.get_clients_ranking()
    print("Рейтинг клиентов:")
    for i, (client, total) in enumerate(ranking, 1):
        print(f"  {i}. {client.full_name}: {total}")

    # Журнал
    print("\n--- Журнал (последние 5 записей) ---")
    for entry in bank._log[-5:]:
        print(f"  {entry}")

    print(f"\n{bank}")