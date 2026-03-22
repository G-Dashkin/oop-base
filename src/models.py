from abc import ABC, abstractmethod
from uuid import uuid4
from decimal import Decimal
from src.exceptions import (
    AccountFrozenError, AccountClosedError,
    InvalidOperationError, InsufficientFundsError
)
import sys
sys.tracebacklimit = 0

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
        "frozen": ("active", "closed"),
        "closed": (),  # из закрытого нельзя переоткрыться
    }

    def _change_status(self, new_status):
        allowed = self.TRANSITIONS.get(self._status, ())
        if new_status not in allowed: raise InvalidOperationError(f"Нельзя перейти из '{self._status}' в '{new_status}'")
        self._status = new_status

    def active(self): self._change_status("active")

    def freeze(self): self._change_status("frozen")

    def close(self): self._change_status("closed")


# Сберегательный счёт: минимальный остаток + ежемесячный процент
class SavingsAccount(BankAccount):
    def __init__(self,
                 owner: Owner,
                 currency: str,
                 min_balance: float = 1000,
                 monthly_rate: float = 0.5,
                 account_id: str = None):
        super().__init__(owner, currency, account_id)
        self._min_balance = Decimal(str(min_balance))
        self._monthly_rate = Decimal(str(monthly_rate))  # 0.5 = 0.5%

    def withdraw(self, summ):
        # Снятие с проверкой минимального остатка
        self._check_status()
        self._validate_amount(summ)
        new_balance = self._balance - summ
        # Защита от снятия с превышением минимального баланса
        if new_balance < self._min_balance: raise InsufficientFundsError(f"Остаток не может быть меньше {self._min_balance} {self._currency}")
        self._balance = new_balance

    def apply_monthly_interest(self):
        # Начислить ежемесячный процент
        self._check_status()
        interest = self._balance * self._monthly_rate / 100
        self._balance += interest
        return interest

    def get_account_info(self):
        info = super().get_account_info()
        info["type"] = "savings"
        info["min_balance"] = self._min_balance
        info["monthly_rate"] = f"{self._monthly_rate}%"
        return info

    def __str__(self):
        return (f"SavingsAccount | {self._owner} | "
                f"id: ***{self._id[-4:]} | status: {self._status} | "
                f"balance: {self._balance:.2f} {self._currency} | "
                f"rate: {self._monthly_rate}%/мес")


# Премиум счёт: овердрафт + фиксированная комиссия за снятие
class PremiumAccount(BankAccount):
    def __init__(self,
                 owner: Owner,
                 currency: str,
                 overdraft_limit: float = 5000,
                 withdraw_commission: float = 50,
                 account_id: str = None):
        super().__init__(owner, currency, account_id)
        self._overdraft_limit = Decimal(str(overdraft_limit))
        self._withdraw_commission = Decimal(str(withdraw_commission))

    def withdraw(self, summ):
        # Снятие с овердрафтом и комиссией
        self._check_status()
        self._validate_amount(summ)
        total_summ = Decimal(str(summ)) + self._withdraw_commission
        # Защита от снятия с превышением овердрафта
        if total_summ > self._balance + self._overdraft_limit: raise InsufficientFundsError("Превышен лимит овердрафта")
        self._balance -= total_summ

    def get_account_info(self):
        info = super().get_account_info()
        info["type"] = "premium"
        info["overdraft_limit"] = self._overdraft_limit
        info["withdraw_fee"] = self._withdraw_commission
        return info

    def __str__(self):
        return (f"PremiumAccount | {self._owner} | "
                f"id: ***{self._id[-4:]} | status: {self._status} | "
                f"balance: {self._balance:.2f} {self._currency} | "
                f"overdraft: {self._overdraft_limit}")


# Инвестиционный счёт: портфель виртуальных активов
class InvestmentAccount(BankAccount):
    ASSET_TYPES = ("stocks", "bonds", "etf")
    GROWTH_RATES = {
        "stocks": Decimal("0.12"),  # 12% годовых
        "bonds": Decimal("0.06"),   # 6%  годовых
        "etf": Decimal("0.09"),     # 9%  годовых
    }

    def __init__(self, owner: Owner, currency: str, account_id: str = None):
        super().__init__(owner, currency, account_id)
        self._portfolio: dict[str, Decimal] = {}

    def buy_asset(self, asset_type: str, amount):
        # Купить актив из баланса
        self._check_status()
        if asset_type not in self.ASSET_TYPES: raise InvalidOperationError(f"Тип актива '{asset_type}' не поддерживается")
        self._validate_amount(amount)
        amount = Decimal(str(amount))
        if amount > self._balance: raise InsufficientFundsError("Недостаточно средств для покупки")
        self._balance -= amount
        self._portfolio[asset_type] = self._portfolio.get(asset_type, Decimal("0")) + amount

    def sell_asset(self, asset_type: str, amount):
        # Продать актив, вернуть деньги на баланс
        self._check_status()
        if asset_type not in self._portfolio: raise InvalidOperationError(f"Актив '{asset_type}' отсутствует в портфеле")
        self._validate_amount(amount)
        amount = Decimal(str(amount))
        if amount > self._portfolio[asset_type]: raise InsufficientFundsError(f"Недостаточно актива '{asset_type}' для продажи")
        self._portfolio[asset_type] -= amount
        if self._portfolio[asset_type] == 0: del self._portfolio[asset_type]
        self._balance += amount

    def project_yearly_growth(self):
        # Прогноз годовой доходности портфеля
        total_growth = Decimal("0")
        details = {}
        for asset_type, amount in self._portfolio.items():
            rate = self.GROWTH_RATES[asset_type]
            growth = amount * rate
            details[asset_type] = {"amount": amount, "rate": f"{rate * 100}%", "growth": growth}
            total_growth += growth
        return {"total_growth": total_growth, "details": details}

    def withdraw(self, summ):
        # Снятие только свободных средств (не вложенных в активы)
        self._check_status()
        self._validate_amount(summ)
        if summ > self._balance: raise InsufficientFundsError("Недостаточно свободных средств")
        self._balance -= summ

    def get_account_info(self):
        info = super().get_account_info()
        info["type"] = "investment"
        info["portfolio"] = dict(self._portfolio)
        info["portfolio_value"] = sum(self._portfolio.values(), Decimal("0"))
        return info

    def __str__(self):
        portfolio_val = sum(self._portfolio.values(), Decimal("0"))
        return (f"InvestmentAccount | {self._owner} | "
                f"id: ***{self._id[-4:]} | status: {self._status} | "
                f"balance: {self._balance:.2f} {self._currency} | "
                f"portfolio: {portfolio_val:.2f}")