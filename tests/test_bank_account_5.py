import unittest
from datetime import datetime
from decimal import Decimal
from src.audit import AuditLog, RiskAnalyzer, LogLevel, RiskLevel
from src.bank import Bank, Client
from src.transactions import Transaction, TransactionQueue, TransactionProcessor
from src.exceptions import InvalidOperationError


def day_time(): return datetime(2025, 6, 15, 12, 0, 0)


class TestAuditLog(unittest.TestCase):

    def setUp(self): self.log = AuditLog(filepath="/tmp/test_audit.log")

    def test_log_entry(self):
        self.log.log(LogLevel.INFO, "Тест", client_id="abc")
        self.assertEqual(len(self.log._entries), 1)
        self.assertEqual(self.log._entries[0].level, LogLevel.INFO)

    def test_filter_by_level(self):
        self.log.log(LogLevel.INFO, "info msg")
        self.log.log(LogLevel.WARNING, "warn msg")
        self.log.log(LogLevel.CRITICAL, "critical msg")
        self.assertEqual(len(self.log.filter_by_level(LogLevel.WARNING)), 1)
        self.assertEqual(len(self.log.filter_by_level(LogLevel.INFO)), 1)

    def test_filter_by_client(self):
        self.log.log(LogLevel.INFO, "msg1", client_id="client_1")
        self.log.log(LogLevel.INFO, "msg2", client_id="client_2")
        self.log.log(LogLevel.WARNING, "msg3", client_id="client_1")
        self.assertEqual(len(self.log.filter_by_client("client_1")), 2)
        self.assertEqual(len(self.log.filter_by_client("client_2")), 1)

    def test_get_suspicious(self):
        self.log.log(LogLevel.INFO, "нормально")
        self.log.log(LogLevel.WARNING, "подозрительно")
        self.log.log(LogLevel.CRITICAL, "критично")
        suspicious = self.log.get_suspicious()
        self.assertEqual(len(suspicious), 2)

    def test_get_error_stats(self):
        self.log.log(LogLevel.INFO, "a")
        self.log.log(LogLevel.INFO, "b")
        self.log.log(LogLevel.WARNING, "c")
        stats = self.log.get_error_stats()
        self.assertEqual(stats[LogLevel.INFO], 2)
        self.assertEqual(stats[LogLevel.WARNING], 1)
        self.assertEqual(stats[LogLevel.CRITICAL], 0)

    def test_client_report(self):
        self.log.log(LogLevel.WARNING, "warn", client_id="c1")
        self.log.log(LogLevel.CRITICAL, "crit", client_id="c1")
        self.log.log(LogLevel.INFO, "info", client_id="c1")
        report = self.log.get_client_report("c1")
        self.assertEqual(report["total"], 3)
        self.assertEqual(report["warnings"], 1)
        self.assertEqual(report["critical"], 1)

    def test_str_entry(self):
        self.log.log(LogLevel.WARNING, "тест", client_id="abc")
        s = str(self.log._entries[0])
        self.assertIn("WARNING", s)
        self.assertIn("abc", s)
        self.assertIn("тест", s)

    def test_write_to_file(self):
        self.log.log(LogLevel.INFO, "запись в файл")
        with open("/tmp/test_audit.log", encoding="utf-8") as f: content = f.read()
        self.assertIn("запись в файл", content)


class TestRiskAnalyzer(unittest.TestCase):

    def setUp(self):
        self.risk = RiskAnalyzer()
        self.risk.register_account("known_acc")

    def test_low_risk(self):
        level = self.risk.analyze(Decimal("1000"), receiver_id="known_acc")
        self.assertEqual(level, RiskLevel.LOW)

    def test_large_amount_is_high(self):
        level = self.risk.analyze(Decimal("100000"), receiver_id="known_acc")
        self.assertEqual(level, RiskLevel.HIGH)

    def test_new_account_is_medium(self):
        level = self.risk.analyze(Decimal("1000"), receiver_id="new_unknown_acc")
        self.assertEqual(level, RiskLevel.MEDIUM)

    def test_night_operation_is_medium(self):
        level = self.risk.analyze(Decimal("100"), receiver_id="known_acc", hour=3)
        self.assertEqual(level, RiskLevel.MEDIUM)

    def test_frequent_operations_is_medium(self):
        client_id = "client_1"
        for _ in range(3): self.risk.register_operation(client_id)
        level = self.risk.analyze(Decimal("100"), client_id=client_id, receiver_id="known_acc")
        self.assertEqual(level, RiskLevel.MEDIUM)

    def test_two_medium_flags_is_high(self):
        # ночь + новый счёт = 2 флага → HIGH
        level = self.risk.analyze(Decimal("1000"), receiver_id="unknown", hour=2)
        self.assertEqual(level, RiskLevel.HIGH)

    def test_client_risk_profile_low(self):
        profile = self.risk.get_client_risk_profile("new_client")
        self.assertEqual(profile["risk"], RiskLevel.LOW)
        self.assertEqual(profile["total_operations"], 0)

    def test_client_risk_profile_high(self):
        for _ in range(3): self.risk.register_operation("heavy_client")
        profile = self.risk.get_client_risk_profile("heavy_client")
        self.assertEqual(profile["risk"], RiskLevel.HIGH)

    def test_register_account(self):
        self.risk.register_account("acc_new")
        level = self.risk.analyze(Decimal("1000"), receiver_id="acc_new")
        self.assertEqual(level, RiskLevel.LOW)

    def test_day_boundary_not_night(self):
        # 5:00 не ночь
        level = self.risk.analyze(Decimal("100"), receiver_id="known_acc", hour=5)
        self.assertEqual(level, RiskLevel.LOW)


class TestBankWithAudit(unittest.TestCase):

    def setUp(self):
        self.audit = AuditLog(filepath="/tmp/test_bank_audit.log")
        self.risk = RiskAnalyzer()
        self.bank = Bank("AuditBank", time_provider=day_time, audit_log=self.audit, risk_analyzer=self.risk)
        self.client = Client("Тест", "Тестов", 30)
        self.client.set_pin("1234")
        self.bank.add_client(self.client)

    def test_open_account_logged(self):
        self.bank.open_account(self.client._id, "basic", "RUB")
        info_logs = self.audit.filter_by_level(LogLevel.INFO)
        self.assertTrue(any("Открыт счёт" in e.message for e in info_logs))

    def test_open_account_registers_in_risk(self):
        account = self.bank.open_account(self.client._id, "basic", "RUB")
        self.assertIn(account._id, self.risk._known_accounts)

    def test_failed_auth_logged(self):
        try: self.bank.authenticate_client(self.client._id, "wrong")
        except Exception: pass
        warnings = self.audit.filter_by_level(LogLevel.WARNING)
        self.assertEqual(len(warnings), 1)

    def test_block_after_3_attempts_logged(self):
        for _ in range(2):
            try: self.bank.authenticate_client(self.client._id, "wrong")
            except Exception: pass
        try: self.bank.authenticate_client(self.client._id, "wrong")
        except Exception: pass
        critical = self.audit.filter_by_level(LogLevel.CRITICAL)
        self.assertTrue(any("заблокирован" in e.message for e in critical))


class TestProcessorWithRisk(unittest.TestCase):

    def setUp(self):
        self.audit = AuditLog(filepath="/tmp/test_proc_audit.log")
        self.risk = RiskAnalyzer()
        self.bank = Bank("RiskBank", time_provider=day_time)
        self.client = Client("Риск", "Клиент", 30)
        self.bank.add_client(self.client)
        self.acc = self.bank.open_account(self.client._id, "basic", "RUB")
        self.acc.deposit(200000)
        # регистрируем счёт как известный в risk
        self.risk.register_account(self.acc._id)
        self.processor = TransactionProcessor(self.bank, audit_log=self.audit, risk_analyzer=self.risk)

    def test_normal_transaction_passes(self):
        transaction = Transaction("deposit", 1000, "RUB", receiver_id=self.acc._id)
        self.processor.process(transaction)
        self.assertEqual(transaction._status, "completed")

    def test_large_amount_blocked(self):
        # крупная сумма с неизвестного счёта → HIGH риск → блокировка
        transaction = Transaction("deposit", 100000, "RUB", receiver_id="unknown_acc")
        self.processor.process(transaction)
        self.assertEqual(transaction._status, "failed")
        self.assertIn("высокий риск", transaction._failure_reason)

    def test_blocked_transaction_logged(self):
        transaction = Transaction("deposit", 100000, "RUB", receiver_id="unknown_acc")
        self.processor.process(transaction)
        critical = self.audit.filter_by_level(LogLevel.CRITICAL)
        self.assertTrue(any("заблокирована" in e.message for e in critical))

    def test_medium_risk_logged_not_blocked(self):
        # Создаём отдельный risk-анализатор для процессора — он не знает ни одного счёта
        fresh_risk = RiskAnalyzer()
        proc = TransactionProcessor(self.bank, audit_log=self.audit, risk_analyzer=fresh_risk)

        # receiver_id неизвестен fresh_risk → MEDIUM → предупреждение, но не блок
        transaction = Transaction("deposit", 500, "RUB", receiver_id=self.acc._id)
        proc.process(transaction)
        self.assertEqual(transaction._status, "completed")
        warnings = self.audit.filter_by_level(LogLevel.WARNING)
        self.assertTrue(len(warnings) >= 1)

    def test_successful_transaction_logged(self):
        tx = Transaction("deposit", 500, "RUB", receiver_id=self.acc._id)
        self.processor.process(tx)
        info_logs = self.audit.filter_by_level(LogLevel.INFO)
        self.assertTrue(any("выполнена" in e.message for e in info_logs))


class TestFullScenarioWithAudit(unittest.TestCase):
    # 10 транзакций: обычные + подозрительные

    def test_mixed_transactions(self):
        audit = AuditLog(filepath="/tmp/test_full_audit.log")
        risk = RiskAnalyzer()
        bank = Bank("FullBank", time_provider=day_time)
        client = Client("Полный", "Сценарий", 30)
        bank.add_client(client)

        acc1 = bank.open_account(client._id, "basic", "RUB")
        acc2 = bank.open_account(client._id, "basic", "RUB")
        acc1.deposit(500000)

        risk.register_account(acc1._id)
        risk.register_account(acc2._id)
        processor = TransactionProcessor(bank, audit_log=audit, risk_analyzer=risk)
        queue = TransactionQueue()

        # Обычные транзакции
        queue.add(Transaction("deposit", 1000, "RUB", receiver_id=acc1._id))    # 1 ok
        queue.add(Transaction("deposit", 5000, "RUB", receiver_id=acc2._id))    # 2 ok
        queue.add(Transaction("withdraw", 500, "RUB", sender_id=acc1._id))      # 3 ok
        queue.add(Transaction("transfer", 2000, "RUB", sender_id=acc1._id, receiver_id=acc2._id))        # 4 ok

        # Подозрительные
        queue.add(Transaction("deposit", 100000, "RUB", receiver_id="unknown")) # 5 HIGH → блок
        queue.add(Transaction("deposit", 200000, "RUB", receiver_id="unknown")) # 6 HIGH → блок

        # Частые операции (регистрируем 3 операции клиента)
        for _ in range(3): risk.register_operation(client._id)

        queue.add(Transaction("deposit", 1000, "RUB", receiver_id=acc1._id))    # 7 MEDIUM (frequent)
        queue.add(Transaction("deposit", 2000, "RUB", receiver_id=acc2._id))    # 8 MEDIUM
        queue.add(Transaction("withdraw", 300, "RUB", sender_id=acc2._id))      # 9 ok
        queue.add(Transaction("deposit", 100, "RUB", receiver_id=acc1._id))     # 10 ok

        processor.process_all(queue)

        completed = [t for t in queue._queue if t._status == "completed"]
        failed = [t for t in queue._queue if t._status == "failed"]

        self.assertEqual(len(completed), 8)  # 4 обычных + 4 с риском MEDIUM (не блокируются)
        self.assertEqual(len(failed), 2)     # 2 HIGH → заблокированы
        self.assertTrue(len(audit.get_suspicious()) > 0)


if __name__ == "__main__":
    unittest.main()