from src.models import Owner, BankAccount
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
    account.active()
    print(f"Статус: {account._status}")
    print("Добавляем 100")
    try: account.deposit(100)
    except Exception as e: print(f"{e}")
    print("---")
    print(account)
    print("--------------------------------------")
