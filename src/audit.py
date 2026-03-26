from enum import Enum
from datetime import datetime
from decimal import Decimal


class LogLevel(Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class LogEntry:
    def __init__(self, level: LogLevel, message: str, client_id: str = None):
        self.time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.level = level
        self.message = message
        self.client_id = client_id

    def __str__(self):
        prefix = f"[{self.time}] [{self.level.value}]"
        if self.client_id: return f"{prefix} [{self.client_id}] {self.message}"
        return f"{prefix} {self.message}"


class AuditLog:
    def __init__(self, filepath: str = "audit.log"):
        self._entries: list[LogEntry] = []
        self._filepath = filepath

    def log(self, level: LogLevel, message: str, client_id: str = None):
        entry = LogEntry(level, message, client_id)
        self._entries.append(entry)
        # дозапись в файл (режим "a" = append)
        with open(self._filepath, "a", encoding="utf-8") as f: f.write(str(entry) + "\n")

    def filter_by_level(self, level: LogLevel) -> list[LogEntry]: return [e for e in self._entries if e.level == level]
    def filter_by_client(self, client_id: str) -> list[LogEntry]: return [e for e in self._entries if e.client_id == client_id]
    def get_suspicious(self) -> list[LogEntry]: return [e for e in self._entries if e.level in (LogLevel.WARNING, LogLevel.CRITICAL)]

    def get_error_stats(self) -> dict:
        stats = {level: 0 for level in LogLevel}
        for e in self._entries: stats[e.level] += 1
        return stats

    def get_client_report(self, client_id: str) -> dict:
        entries = self.filter_by_client(client_id)
        return {
            "client_id": client_id,
            "total": len(entries),
            "warnings": len([e for e in entries if e.level == LogLevel.WARNING]),
            "critical": len([e for e in entries if e.level == LogLevel.CRITICAL]),
        }


class RiskAnalyzer:
    LARGE_AMOUNT = Decimal("50000")   # крупная сумма
    FREQUENT_LIMIT = 3                # частые операции: >= 3 за сессию

    def __init__(self):
        self._known_accounts: set[str] = set()        # известные счета
        self._client_ops: dict[str, int] = {}         # client_id -> кол-во операций

    # Зарегистрировать счёт как известный
    def register_account(self, account_id: str): self._known_accounts.add(account_id)

    # Зафиксировать операцию клиента
    def register_operation(self, client_id: str): self._client_ops[client_id] = self._client_ops.get(client_id, 0) + 1

    def analyze(self, amount: Decimal, client_id: str = None, receiver_id: str = None, hour: int = None) -> RiskLevel:
        # Анализ операции. Возвращает уровень риска.
        flags = []
        if amount >= self.LARGE_AMOUNT: flags.append("large_amount")
        if client_id and self._client_ops.get(client_id, 0) >= self.FREQUENT_LIMIT: flags.append("frequent")
        if receiver_id and receiver_id not in self._known_accounts: flags.append("new_account")
        if hour is not None and 0 <= hour < 5: flags.append("night")
        if "large_amount" in flags or len(flags) >= 2: return RiskLevel.HIGH
        if flags: return RiskLevel.MEDIUM
        return RiskLevel.LOW

    def get_client_risk_profile(self, client_id: str) -> dict:
        ops = self._client_ops.get(client_id, 0)
        if ops >= self.FREQUENT_LIMIT: risk = RiskLevel.HIGH
        elif ops >= 1: risk = RiskLevel.MEDIUM
        else: risk = RiskLevel.LOW
        return {"client_id": client_id, "total_operations": ops, "risk": risk}