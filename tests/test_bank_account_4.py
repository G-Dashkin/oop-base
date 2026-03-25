import unittest
from datetime import datetime
from decimal import Decimal
from src.bank import Bank, Client
from src.transactions import Transaction, TransactionQueue, TransactionProcessor
from src.exceptions import InvalidOperationError, InsufficientFundsError


# Дневное время для банка
def day_time(): return datetime(2025, 6, 15, 12, 0, 0)


class TestTransaction(unittest.TestCase):

    def test_create(self):
        transaction = Transaction("deposit", 1000, "RUB", receiver_id="acc1")
        self.assertEqual(transaction._status, "pending")
        self.assertEqual(transaction._amount, Decimal("1000"))

    def test_invalid_type(self):
        with self.assertRaises(InvalidOperationError): Transaction("magic", 100, "RUB")

    def test_complete(self):
        transaction = Transaction("deposit", 500, "RUB")
        transaction.complete()
        self.assertEqual(transaction._status, "completed")
        self.assertIsNotNone(transaction._completed_at)

    def test_fail(self):
        transaction = Transaction("withdraw", 100, "USD")
        transaction.fail("Нет средств")
        self.assertEqual(transaction._status, "failed")
        self.assertEqual(transaction._failure_reason, "Нет средств")

    def test_cancel(self):
        transaction = Transaction("transfer", 200, "RUB")
        transaction.cancel()
        self.assertEqual(transaction._status, "cancelled")

    def test_cancel_completed_raises(self):
        transaction = Transaction("deposit", 100, "RUB")
        transaction.complete()
        with self.assertRaises(InvalidOperationError): transaction.cancel()

    def test_str(self):
        transaction = Transaction("deposit", 1000, "RUB")
        self.assertIn("deposit", str(transaction))
        self.assertIn("1000", str(transaction))


class TestTransactionQueue(unittest.TestCase):

    def test_add(self):
        transaction_queue = TransactionQueue()
        transaction = Transaction("deposit", 100, "RUB")
        transaction_queue.add(transaction)
        self.assertEqual(len(transaction_queue), 1)

    def test_add_priority(self):
        transaction_queue = TransactionQueue()
        transaction1 = Transaction("deposit", 100, "RUB")
        transaction2 = Transaction("deposit", 999, "RUB")
        transaction_queue.add(transaction1)
        transaction_queue.add_priority(transaction2)  # transaction2 первый в очереди
        pending = transaction_queue.get_pending()
        self.assertEqual(pending[0]._amount, Decimal("999"))

    def test_cancel(self):
        transaction_queue = TransactionQueue()
        transaction = Transaction("deposit", 100, "RUB")
        transaction_queue.add(transaction)
        transaction_queue.cancel(transaction._id)
        self.assertEqual(len(transaction_queue.get_pending()), 0)

    def test_cancel_nonexistent(self):
        transaction_queue = TransactionQueue()
        with self.assertRaises(InvalidOperationError): transaction_queue.cancel("fake_id")

    def test_defer_and_release(self):
        transaction_queue = TransactionQueue()
        transaction = Transaction("deposit", 100, "RUB")
        transaction_queue.defer(transaction)
        self.assertEqual(len(transaction_queue.get_pending()), 0)  # в основной очереди пусто
        transaction_queue.release_deferred()
        self.assertEqual(len(transaction_queue.get_pending()), 1)  # теперь есть

    def test_get_pending_skips_completed(self):
        transaction_queue = TransactionQueue()
        transaction1 = Transaction("deposit", 100, "RUB")
        transaction2 = Transaction("deposit", 200, "RUB")
        transaction1.complete()
        transaction_queue.add(transaction1)
        transaction_queue.add(transaction2)
        self.assertEqual(len(transaction_queue.get_pending()), 1)


class TestTransactionProcessor(unittest.TestCase):

    def setUp(self):
        self.bank = Bank("TestBank", time_provider=day_time)
        self.c1 = Client("Анна", "Петрова", 28)
        self.c2 = Client("Борис", "Козлов", 35)
        self.bank.add_client(self.c1)
        self.bank.add_client(self.c2)
        self.acc1 = self.bank.open_account(self.c1._id, "basic", "RUB")
        self.acc2 = self.bank.open_account(self.c2._id, "basic", "RUB")
        self.acc1.deposit(10000)
        self.processor = TransactionProcessor(self.bank)

    def test_deposit(self):
        transaction = Transaction("deposit", 500, "RUB", receiver_id=self.acc2._id)
        self.processor.process(transaction)
        self.assertEqual(transaction._status, "completed")
        self.assertEqual(self.acc2._balance, Decimal("500"))

    def test_withdraw(self):
        transaction = Transaction("withdraw", 300, "RUB", sender_id=self.acc1._id)
        self.processor.process(transaction)
        self.assertEqual(self.acc1._balance, Decimal("9700"))

    def test_transfer(self):
        transaction = Transaction("transfer", 1000, "RUB", sender_id=self.acc1._id, receiver_id=self.acc2._id)
        self.processor.process(transaction)
        self.assertEqual(transaction._status, "completed")
        # Отправитель: 10000 - 1000 - 10 (1% комиссия) = 8990
        self.assertEqual(self.acc1._balance, Decimal("8990"))
        # Получатель: 0 + 1000 = 1000
        self.assertEqual(self.acc2._balance, Decimal("1000"))
        self.assertEqual(transaction._commission, Decimal("10"))

    def test_transfer_insufficient_funds(self):
        transaction = Transaction("transfer", 99999, "RUB", sender_id=self.acc1._id, receiver_id=self.acc2._id)
        self.processor.process(transaction)
        self.assertEqual(transaction._status, "failed")
        self.assertIn("Недостаточно", transaction._failure_reason)

    def test_transfer_frozen_account(self):
        self.acc1.freeze()
        transaction = Transaction("transfer", 100, "RUB", sender_id=self.acc1._id, receiver_id=self.acc2._id)
        self.processor.process(transaction)
        self.assertEqual(transaction._status, "failed")

    def test_errors_logged(self):
        transaction = Transaction("withdraw", 99999, "RUB", sender_id=self.acc1._id)
        self.processor.process(transaction)
        self.assertEqual(len(self.processor._errors), 1)

    def test_process_all(self):
        transaction_queue = TransactionQueue()
        transaction_queue.add(Transaction("deposit", 100, "RUB", receiver_id=self.acc1._id))
        transaction_queue.add(Transaction("deposit", 200, "RUB", receiver_id=self.acc2._id))
        transaction_queue.add(Transaction("transfer", 500, "RUB", sender_id=self.acc1._id, receiver_id=self.acc2._id))
        self.processor.process_all(transaction_queue)
        completed = [transaction for transaction in transaction_queue._queue if transaction._status == "completed"]
        self.assertEqual(len(completed), 3)


class TestCurrencyConversion(unittest.TestCase):

    def setUp(self):
        self.bank = Bank("TestBank", time_provider=day_time)
        self.client = Client("Тест", "Тестов", 30)
        self.bank.add_client(self.client)
        self.account_rub = self.bank.open_account(self.client._id, "basic", "RUB")
        self.account_usd = self.bank.open_account(self.client._id, "basic", "USD")
        self.account_rub.deposit(100000)
        self.account_usd.deposit(1000)
        self.processor = TransactionProcessor(self.bank)

    def test_convert_same_currency(self):
        result = self.processor.convert(Decimal("100"), "RUB", "RUB")
        self.assertEqual(result, Decimal("100"))

    def test_convert_usd_to_rub(self):
        result = self.processor.convert(Decimal("100"), "USD", "RUB")
        self.assertEqual(result, Decimal("9000"))

    def test_convert_invalid_pair(self):
        with self.assertRaises(InvalidOperationError): self.processor.convert(Decimal("100"), "KZT", "CNY")

    def test_transfer_cross_currency(self):
        transaction = Transaction("transfer", 100, "USD", sender_id=self.account_usd._id, receiver_id=self.account_rub._id)
        self.processor.process(transaction)
        self.assertEqual(transaction._status, "completed")
        # Получатель получил 100 USD * 90 = 9000 RUB
        self.assertEqual(self.account_rub._balance, Decimal("109000"))


class TestPremiumTransfer(unittest.TestCase):

    def setUp(self):
        self.bank = Bank("TestBank", time_provider=day_time)
        self.client = Client("Премиум", "Клиент", 30)
        self.bank.add_client(self.client)
        self.premium = self.bank.open_account(self.client._id, "premium", "RUB", overdraft_limit=5000)
        self.basic = self.bank.open_account(self.client._id, "basic", "RUB")
        self.premium.deposit(100)
        self.processor = TransactionProcessor(self.bank)

    def test_premium_can_overdraft_transfer(self):
        """Премиум может уйти в минус при переводе (овердрафт)"""
        transaction = Transaction("transfer", 200, "RUB", sender_id=self.premium._id, receiver_id=self.basic._id)
        self.processor.process(transaction)
        self.assertEqual(transaction._status, "completed")
        # 100 - 200 - 2 (комиссия перевода) - 50 (комиссия премиум за снятие) = -152
        self.assertEqual(self.premium._balance, Decimal("-152"))


class TestFullScenario(unittest.TestCase):
    """Тест: 10 транзакций → очередь → выполнение"""

    def test_10_transactions(self):
        bank = Bank("TestBank", time_provider=day_time)
        client1 = Client("Алексей", "Смирнов", 35)
        client2 = Client("Мария", "Козлова", 28)
        bank.add_client(client1)
        bank.add_client(client2)

        acc1 = bank.open_account(client1._id, "basic", "RUB")
        acc2 = bank.open_account(client2._id, "basic", "RUB")
        acc3 = bank.open_account(client1._id, "savings", "USD", min_balance=100)

        transaction_queue = TransactionQueue()

        # 10 транзакций
        transaction_queue.add(Transaction("deposit", 50000, "RUB", receiver_id=acc1._id))  # 1
        transaction_queue.add(Transaction("deposit", 30000, "RUB", receiver_id=acc2._id))  # 2
        transaction_queue.add(Transaction("deposit", 5000, "USD", receiver_id=acc3._id))  # 3
        transaction_queue.add(Transaction("withdraw", 1000, "RUB", sender_id=acc1._id))  # 4
        transaction_queue.add(Transaction("transfer", 5000, "RUB", sender_id=acc1._id, receiver_id=acc2._id))  # 5
        transaction_queue.add(Transaction("transfer", 2000, "RUB", sender_id=acc2._id, receiver_id=acc1._id))  # 6
        transaction_cancel = Transaction("deposit", 999, "RUB", receiver_id=acc1._id)
        transaction_queue.add(transaction_cancel) # 7
        transaction_queue.cancel(transaction_cancel._id)  # отменяем 7-ю
        transaction_queue.add_priority(Transaction("deposit", 100, "RUB", receiver_id=acc2._id))  # 8 (приоритет)
        deferred = Transaction("deposit", 777, "RUB", receiver_id=acc1._id)
        transaction_queue.defer(deferred)  # 9 (отложена)
        transaction_queue.add(Transaction("withdraw", 500, "RUB", sender_id=acc2._id))  # 10

        # Обрабатываем
        processor = TransactionProcessor(bank)
        processor.process_all(transaction_queue)

        # 7-я отменена, 9-я отложена → обработано 8 из 10
        completed = [transaction for transaction in transaction_queue._queue if transaction._status == "completed"]
        cancelled = [transaction for transaction in transaction_queue._queue if transaction._status == "cancelled"]
        self.assertEqual(len(completed), 8)
        self.assertEqual(len(cancelled), 1)
        self.assertEqual(len(transaction_queue._deferred), 1)

        # Выпускаем отложенную и обрабатываем
        transaction_queue.release_deferred()
        processor.process_all(transaction_queue)
        all_completed = [transaction for transaction in transaction_queue._queue if transaction._status == "completed"]
        self.assertEqual(len(all_completed), 9)  # 8 + 1 отложенная


if __name__ == "__main__":
    unittest.main()