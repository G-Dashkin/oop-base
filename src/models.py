from abc import ABC, abstractmethod
from uuid import uuid4
from decimal import Decimal
from src.exceptions import (
    AccountFrozenError, AccountClosedError,
    InvalidOperationError, InsufficientFundsError
)


class Owner:
    def __init__(self, first_name, last_name, age):
        self._first_name = first_name
        self._last_name = last_name
        self._age = age

    def __str__(self):
        return f"{self._first_name} {self._last_name}, {self._age} лет"


class AbstractAccount(ABC):
    COUNT_STATUS = ("active", "frozen", "closed")

    def __init__(self, owner: Owner, currency: str, account_id: str = None):
        self._id = account_id
        self._owner = owner
        self._balance = Decimal("0.0")
        self._status = self.COUNT_STATUS[0]
        self._currency = currency

    @abstractmethod
    def deposit(self, summ): ...

    @abstractmethod
    def withdraw(self, summ): ...

    @abstractmethod
    def get_account_info(self): ...


class BankAccount(AbstractAccount):
    CURRENCIES = ("RUB", "USD", "EUR", "KZT", "CNY")

    def __init__(self, owner: Owner, currency: str, account_id: str = None):
        self._validate_currency(currency)
        generated_id = account_id or uuid4().hex[:8]
        super().__init__(owner, currency, generated_id)

    def __str__(self):
        return (f"BankAccount | {self._owner} | "
                f"id: ***{self._id[-4:]} | status: {self._status} | "
                f"balance: {self._balance:.2f} {self._currency}")

    @staticmethod
    def _validate_amount(summ):
        if isinstance(summ, bool): raise InvalidOperationError("Сумма должна быть числом")
        if not isinstance(summ, (int, float, Decimal)): raise InvalidOperationError("Сумма должна быть числом")
        if summ <= 0: raise InvalidOperationError("Сумма должна быть положительной")

    def _check_status(self):
        if self._status == "frozen": raise AccountFrozenError("Счёт заморожен")
        if self._status == "closed": raise AccountClosedError("Счёт закрыт")

    @staticmethod
    def _validate_currency(currency):
        if currency not in BankAccount.CURRENCIES: raise InvalidOperationError("Валюта " + currency + " не принимается")

    def deposit(self, summ):
        self._check_status()
        self._validate_amount(summ)
        self._balance += summ

    def withdraw(self, summ):
        self._check_status()
        self._validate_amount(summ)
        if summ > self._balance: raise InsufficientFundsError("Недостаточно средств")
        self._balance -= summ

    def get_account_info(self):
        return {
            "id": self._id,
            "owner": self._owner,
            "balance": self._balance,
            "currency": self._currency,
            "status": self._status,
        }

    TRANSITIONS = {
        "active": ("frozen", "closed"),
        "frozen": ("active",),
        "closed": (),  # из закрытого никуда
    }

    def _change_status(self, new_status):
        allowed = self.TRANSITIONS.get(self._status, ())
        if new_status not in allowed: raise InvalidOperationError(f"Нельзя перейти из '{self._status}' в '{new_status}'")
        self._status = new_status

    def active(self): self._change_status("active")

    def freeze(self): self._change_status("frozen")

    def close(self): self._change_status("closed")
