from datetime import datetime
from decimal import Decimal
from uuid import uuid4
import sys
sys.tracebacklimit = 0

from src.models import Owner, BankAccount, SavingsAccount, PremiumAccount, InvestmentAccount
from src.exceptions import (
    AuthenticationError, ClientBlockedError,
    NightOperationError, InvalidOperationError
)

# Типы счетов — маппинг строки на класс
ACCOUNT_TYPES = {
    "basic": BankAccount,
    "savings": SavingsAccount,
    "premium": PremiumAccount,
    "investment": InvestmentAccount,
}


class Client:
    """Клиент банка: ФИО, id, список счетов, контакты, аутентификация"""

    def __init__(self, first_name: str, last_name: str, age: int, phone: str = None, email: str = None, client_id: str = None):
        if age < 18: raise InvalidOperationError("Клиент должен быть старше 18 лет")
        self._id = client_id or uuid4().hex[:8]
        self._first_name = first_name
        self._last_name = last_name
        self._age = age
        self._status = "active"  # active / blocked
        self._accounts: list[str] = []  # список id счетов
        self._pin = "0000"  # пин по умолчанию
        self._phone = phone
        self._email = email
        self._failed_attempts = 0
        self._suspicious = False  # пометка подозрительных действий

    @property
    def full_name(self) -> str: return f"{self._first_name} {self._last_name}"

    def add_account(self, account_id: str):
        if account_id not in self._accounts: self._accounts.append(account_id)

    def remove_account(self, account_id: str):
        if account_id in self._accounts: self._accounts.remove(account_id)

    def set_pin(self, pin: str):
        if len(pin) != 4 or not pin.isdigit(): raise InvalidOperationError("PIN должен быть 4 цифры")
        self._pin = pin

    def __str__(self): return (f"Client | {self.full_name}, {self._age} лет | "f"id: {self._id} | status: {self._status} | "f"accounts: {len(self._accounts)}")


class Bank:
    """Управляющий класс банка: клиенты, счета, безопасность"""

    NIGHT_START = 0   # 00:00
    NIGHT_END = 5     # 05:00
    MAX_ATTEMPTS = 3

    def __init__(self, name: str, time_provider=None):
        self._name = name
        self._clients: dict[str, Client] = {}     # client_id -> Client
        self._accounts: dict[str, BankAccount] = {}  # account_id -> BankAccount
        self._log: list[str] = []  # журнал действий
        # Инъекция зависимости: в тестах можно подменить на lambda: fake_datetime
        self._get_now = time_provider or datetime.now

    def _check_night(self):
        """Запрет операций с 00:00 до 05:00"""
        hour = self._get_now().hour
        if self.NIGHT_START <= hour < self.NIGHT_END: raise NightOperationError("Операции запрещены с 00:00 до 05:00")

    def _log_action(self, action: str):
        timestamp = self._get_now().strftime("%Y-%m-%d %H:%M:%S")
        self._log.append(f"[{timestamp}] {action}")

    # --- Клиенты ---
    def add_client(self, client: Client) -> Client:
        """Добавить клиента в банк"""
        if client._id in self._clients: raise InvalidOperationError("Клиент уже зарегистрирован")
        self._clients[client._id] = client
        self._log_action(f"Добавлен клиент: {client.full_name} ({client._id})")
        return client

    def get_client(self, client_id: str) -> Client:
        if client_id not in self._clients: raise InvalidOperationError("Клиент не найден")
        return self._clients[client_id]

    # --- Аутентификация ---

    def authenticate_client(self, client_id: str, pin: str) -> bool:
        """Аутентификация по PIN. 3 неудачи → блокировка"""
        client = self.get_client(client_id)
        if client._status == "blocked": raise ClientBlockedError("Клиент заблокирован")

        if client._pin != pin:
            client._failed_attempts += 1
            remaining = self.MAX_ATTEMPTS - client._failed_attempts
            self._log_action(f"Неудачная попытка входа: {client._id} (осталось: {remaining})")
            if client._failed_attempts >= self.MAX_ATTEMPTS:
                client._status = "blocked"
                client._suspicious = True
                self._log_action(f"Клиент заблокирован: {client._id}")
                raise ClientBlockedError("Клиент заблокирован после 3 неудачных попыток")
            raise AuthenticationError(f"Неверный PIN. Осталось попыток: {remaining}")

        client._failed_attempts = 0
        self._log_action(f"Успешная аутентификация: {client._id}")
        return True

    # --- Счета ---

    def open_account(self, client_id: str, account_type: str = "basic", currency: str = "RUB", **kwargs) -> BankAccount:
        """Открыть счёт для клиента"""
        self._check_night()
        client = self.get_client(client_id)
        if client._status == "blocked": raise ClientBlockedError("Клиент заблокирован")

        if account_type not in ACCOUNT_TYPES: raise InvalidOperationError(f"Тип счёта '{account_type}' не поддерживается")

        # Owner создаётся из Client для совместимости с BankAccount
        owner = Owner(client._first_name, client._last_name, client._age)
        account_class = ACCOUNT_TYPES[account_type]
        account = account_class(owner, currency, **kwargs)

        self._accounts[account._id] = account
        client.add_account(account._id)
        self._log_action(f"Открыт счёт {account_type}: {account._id} для клиента {client._id}")
        return account

    def close_account(self, client_id: str, account_id: str):
        """Закрыть счёт: проверяет нулевой баланс, удаляет из реестров"""
        self._check_night()
        client = self.get_client(client_id)
        account = self._get_account(account_id)
        if account_id not in client._accounts: raise InvalidOperationError("Счёт не принадлежит клиенту")
        if account._balance != Decimal("0"): raise InvalidOperationError("Нельзя закрыть счёт с ненулевым балансом")

        account.close()
        client.remove_account(account_id)
        del self._accounts[account_id]
        self._log_action(f"Закрыт счёт: {account_id} клиента {client._id}")

    def freeze_account(self, client_id: str, account_id: str):
        """Заморозить счёт"""
        self._check_night()
        client = self.get_client(client_id)
        account = self._get_account(account_id)
        if account_id not in client._accounts: raise InvalidOperationError("Счёт не принадлежит клиенту")

        account.freeze()
        self._log_action(f"Заморожен счёт: {account_id} клиента {client._id}")

    def unfreeze_account(self, client_id: str, account_id: str):
        """Разморозить счёт"""
        self._check_night()
        client = self.get_client(client_id)
        account = self._get_account(account_id)
        if account_id not in client._accounts: raise InvalidOperationError("Счёт не принадлежит клиенту")

        account.active()
        self._log_action(f"Разморожен счёт: {account_id} клиента {client._id}")

    def _get_account(self, account_id: str) -> BankAccount:
        if account_id not in self._accounts: raise InvalidOperationError("Счёт не найден")
        return self._accounts[account_id]

    # --- Поиск ---
    def search_accounts(self, client_id: str = None, currency: str = None, status: str = None, account_type: str = None) -> list[BankAccount]:
        """Поиск счетов по фильтрам"""
        results = list(self._accounts.values())

        if client_id:
            client = self.get_client(client_id)
            results = [a for a in results if a._id in client._accounts]
        if currency:
            results = [a for a in results if a._currency == currency]
        if status:
            results = [a for a in results if a._status == status]
        if account_type:
            cls = ACCOUNT_TYPES.get(account_type)
            if cls: results = [a for a in results if type(a) is cls]

        return results

    # --- Аналитика ---
    def get_total_balance(self, client_id: str = None) -> Decimal:
        """Суммарный баланс: по клиенту или всего банка"""
        if client_id:
            client = self.get_client(client_id)
            accounts = [self._accounts[aid] for aid in client._accounts if aid in self._accounts]
        else: accounts = list(self._accounts.values())
        return sum((a._balance for a in accounts), Decimal("0"))

    def get_clients_ranking(self) -> list[tuple[Client, Decimal]]:
        """Рейтинг клиентов по суммарному балансу (от большего к меньшему)"""
        ranking = []
        for client in self._clients.values():
            total = sum( (self._accounts[aid]._balance for aid in client._accounts if aid in self._accounts), Decimal("0"))
            ranking.append((client, total))
        # сортировка по второму элементу кортежа
        return sorted(ranking, key=lambda x: x[1], reverse=True)

    def __str__(self):
        return (f"Bank '{self._name}' | "
                f"clients: {len(self._clients)} | "
                f"accounts: {len(self._accounts)}")