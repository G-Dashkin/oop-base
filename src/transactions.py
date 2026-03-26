from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from src.exceptions import InvalidOperationError, InsufficientFundsError
from src.models import PremiumAccount
from src.audit import AuditLog, RiskAnalyzer, LogLevel, RiskLevel


# Модель транзакции: deposit / withdraw / transfer
class Transaction:
    TYPES = ("deposit", "withdraw", "transfer")

    def __init__(self, transaction_type: str, amount, currency: str, sender_id: str = None, receiver_id: str = None):
        if transaction_type not in self.TYPES: raise InvalidOperationError(f"Неизвестный тип: {transaction_type}")
        self._id = uuid4().hex[:8]
        self._type = transaction_type
        self._amount = Decimal(str(amount))
        self._currency = currency
        self._commission = Decimal("0")
        self._sender_id = sender_id  # id счёта отправителя
        self._receiver_id = receiver_id  # id счёта получателя
        self._status = "pending"  # pending / completed / failed / cancelled
        self._failure_reason = None
        self._created_at = datetime.now()
        self._completed_at = None

    def complete(self):
        self._status = "completed"
        self._completed_at = datetime.now()

    def fail(self, reason: str):
        self._status = "failed"
        self._failure_reason = reason
        self._completed_at = datetime.now()

    def cancel(self):
        if self._status != "pending": raise InvalidOperationError("Можно отменить только pending транзакцию")
        self._status = "cancelled"

    def __str__(self): return (f"Transaction {self._id} | {self._type} | " f"{self._amount} {self._currency} | {self._status}")


# Очередь транзакций: приоритет, отложенные, отмена
class TransactionQueue:

    def __init__(self):
        self._queue: list[Transaction] = []
        self._deferred: list[Transaction] = []

    # Добавить в конец очереди
    def add(self, transaction: Transaction): self._queue.append(transaction)

    # Добавить в начало очереди (высокий приоритет)
    def add_priority(self, transaction: Transaction): self._queue.insert(0, transaction)

    # Отложить транзакцию (не будет обработана до release)
    def defer(self, transaction: Transaction): self._deferred.append(transaction)

    # Вернуть все отложенные в основную очередь
    def release_deferred(self):
        self._queue.extend(self._deferred)
        self._deferred.clear()

    # Отменить pending транзакцию по ID
    def cancel(self, transaction_id: str):
        for transaction in self._queue:
            if transaction._id == transaction_id and transaction._status == "pending":
                transaction.cancel()
                return
        raise InvalidOperationError("Транзакция не найдена или уже обработана")

    # Все pending транзакции (в порядке очереди)
    def get_pending(self) -> list[Transaction]: return [transaction for transaction in self._queue if transaction._status == "pending"]

    def __len__(self): return len(self._queue)

    def __str__(self):
        pending = len(self.get_pending())
        return f"Queue | total: {len(self._queue)} | pending: {pending} | deferred: {len(self._deferred)}"


# Обработчик: комиссии, конвертация, повторные попытки, лог ошибок
class TransactionProcessor:

    TRANSFER_COMMISSION = Decimal("0.01")  # 1% за перевод
    MAX_RETRIES = 3

    # Упрощённые курсы валют
    RATES = {
        ("USD", "RUB"): Decimal("90"),
        ("RUB", "USD"): Decimal("0.011"),
        ("EUR", "RUB"): Decimal("100"),
        ("RUB", "EUR"): Decimal("0.01"),
        ("USD", "EUR"): Decimal("0.92"),
        ("EUR", "USD"): Decimal("1.08"),
    }

    def __init__(self, bank, audit_log: AuditLog = None, risk_analyzer: RiskAnalyzer = None):
        self._bank = bank
        self._errors: list[str] = []
        self._audit = audit_log
        self._risk = risk_analyzer

    # Конвертация валюты по курсу
    def convert(self, amount: Decimal, from_cur: str, to_cur: str) -> Decimal:
        if from_cur == to_cur: return amount
        key = (from_cur, to_cur)
        if key not in self.RATES: raise InvalidOperationError(f"Нет курса {from_cur} → {to_cur}")
        return (amount * self.RATES[key]).quantize(Decimal("0.01"))

    # Обработать все pending транзакции из очереди
    def process_all(self, queue: TransactionQueue):
        for transaction in queue.get_pending(): self.process(transaction)

    # Обработать одну транзакцию с повторными попытками
    def process(self, transaction: Transaction):
        # Проверка риска перед выполнением
        if self._risk:
            receiver_id = transaction._receiver_id
            hour = self._bank._get_now().hour  # используем время банка (мокируемое в тестах)
            risk = self._risk.analyze(transaction._amount, receiver_id=receiver_id, hour=hour)
            if risk == RiskLevel.HIGH:
                transaction.fail(f"Заблокировано: высокий риск")
                if self._audit: self._audit.log(LogLevel.CRITICAL, f"Транзакция {transaction._id} заблокирована: высокий риск")
                self._errors.append(f"{transaction._id}: заблокировано — высокий риск")
                return
            if risk == RiskLevel.MEDIUM and self._audit:
                self._audit.log(LogLevel.WARNING, f"Транзакция {transaction._id}: средний риск ({transaction._amount})")

        for attempt in range(self.MAX_RETRIES):
            try:
                self._execute(transaction)
                if self._audit: self._audit.log(LogLevel.INFO, f"Транзакция {transaction._id} выполнена: {transaction._type} {transaction._amount}")
                return  # успех — выходим
            except Exception as e:
                if attempt == self.MAX_RETRIES - 1:
                    transaction.fail(str(e))
                    self._errors.append(f"{transaction._id}: {e}")
                    if self._audit: self._audit.log(LogLevel.WARNING, f"Транзакция {transaction._id} провалена: {e}")

    # Логика выполнения транзакции
    def _execute(self, transaction: Transaction):
        if transaction._type == "deposit":
            account = self._bank._get_account(transaction._receiver_id)
            account.deposit(transaction._amount)

        elif transaction._type == "withdraw":
            account = self._bank._get_account(transaction._sender_id)
            account.withdraw(transaction._amount)

        elif transaction._type == "transfer":
            sender_account = self._bank._get_account(transaction._sender_id)
            receiver_account = self._bank._get_account(transaction._receiver_id)

            # Запрет перевода при минусе (кроме премиум)
            if not isinstance(sender_account, PremiumAccount) and sender_account._balance < 0:
                raise InvalidOperationError("Перевод при отрицательном балансе запрещён")

            # Комиссия за перевод
            commission = (transaction._amount * self.TRANSFER_COMMISSION).quantize(Decimal("0.01"))
            transaction._commission = commission

            # Конвертация если валюты разные
            converted = self.convert(transaction._amount, sender_account._currency, receiver_account._currency)

            # Снятие (сумма + комиссия), зачисление
            sender_account.withdraw(transaction._amount + commission)
            receiver_account.deposit(converted)

        transaction.complete()