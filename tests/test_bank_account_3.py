import unittest
from unittest.mock import patch
from decimal import Decimal
from src.bank import Bank
from src.bank import Client
from src.exceptions import (
    InvalidOperationError, AuthenticationError,
    ClientBlockedError, NightOperationError
)


class TestClient(unittest.TestCase):

    def test_create(self):
        c = Client("Иван", "Иванов", 30, phone="+79991234567")
        self.assertEqual(c.full_name, "Иван Иванов")
        self.assertEqual(c._status, "active")
        self.assertEqual(c._accounts, [])

    def test_underage(self):
        with self.assertRaises(InvalidOperationError): Client("Петя", "Петров", 17)

    def test_exactly_18(self):
        c = Client("Анна", "Смирнова", 18)
        self.assertEqual(c._age, 18)

    def test_set_pin(self):
        c = Client("Тест", "Тестов", 25)
        c.set_pin("1234")
        self.assertEqual(c._pin, "1234")

    def test_set_invalid_pin(self):
        c = Client("Тест", "Тестов", 25)
        with self.assertRaises(InvalidOperationError): c.set_pin("abc")
        with self.assertRaises(InvalidOperationError): c.set_pin("12345")

    def test_str(self):
        c = Client("Иван", "Иванов", 30)
        self.assertIn("Иван Иванов", str(c))


class TestBank(unittest.TestCase):

    def setUp(self):
        self.bank = Bank("TestBank")
        self.client = Client("Иван", "Иванов", 30)
        self.client.set_pin("1234")
        self.bank.add_client(self.client)

    def test_add_client(self):
        self.assertIn(self.client._id, self.bank._clients)

    def test_add_duplicate_client(self):
        with self.assertRaises(InvalidOperationError): self.bank.add_client(self.client)

    def test_open_account(self):
        acc = self.bank.open_account(self.client._id, "basic", "RUB")
        self.assertIn(acc._id, self.bank._accounts)
        self.assertIn(acc._id, self.client._accounts)

    def test_open_savings_account(self):
        acc = self.bank.open_account(self.client._id, "savings", "RUB", min_balance=500)
        self.assertEqual(acc._min_balance, Decimal("500"))

    def test_open_invalid_type(self):
        with self.assertRaises(InvalidOperationError):
            self.bank.open_account(self.client._id, "crypto", "USD")

    def test_close_account(self):
        acc = self.bank.open_account(self.client._id)
        self.bank.close_account(self.client._id, acc._id)
        self.assertEqual(acc._status, "closed")

    def test_freeze_unfreeze(self):
        acc = self.bank.open_account(self.client._id)
        self.bank.freeze_account(self.client._id, acc._id)
        self.assertEqual(acc._status, "frozen")
        self.bank.unfreeze_account(self.client._id, acc._id)
        self.assertEqual(acc._status, "active")


class TestAuthentication(unittest.TestCase):

    def setUp(self):
        self.bank = Bank("TestBank")
        self.client = Client("Борис", "Сидоров", 40)
        self.client.set_pin("5555")
        self.bank.add_client(self.client)

    def test_success(self):
        result = self.bank.authenticate_client(self.client._id, "5555")
        self.assertTrue(result)

    def test_wrong_pin(self):
        with self.assertRaises(AuthenticationError):
            self.bank.authenticate_client(self.client._id, "0000")

    def test_block_after_3_attempts(self):
        for _ in range(2):
            with self.assertRaises(AuthenticationError):
                self.bank.authenticate_client(self.client._id, "wrong")
        with self.assertRaises(ClientBlockedError):
            self.bank.authenticate_client(self.client._id, "wrong")
        self.assertEqual(self.client._status, "blocked")

    def test_blocked_client_cannot_login(self):
        self.client._status = "blocked"
        with self.assertRaises(ClientBlockedError):
            self.bank.authenticate_client(self.client._id, "5555")

    def test_blocked_client_cannot_open_account(self):
        self.client._status = "blocked"
        with self.assertRaises(ClientBlockedError):
            self.bank.open_account(self.client._id)

    def test_reset_attempts_on_success(self):
        with self.assertRaises(AuthenticationError):
            self.bank.authenticate_client(self.client._id, "wrong")
        self.bank.authenticate_client(self.client._id, "5555")
        self.assertEqual(self.client._failed_attempts, 0)


class TestNightRestriction(unittest.TestCase):

    def setUp(self):
        self.bank = Bank("TestBank")
        self.client = Client("Ночь", "Тестов", 25)
        self.bank.add_client(self.client)

    @patch("src.bank.datetime")
    def test_night_block(self, mock_dt):
        mock_dt.now.return_value.hour = 3  # 03:00 — ночь
        with self.assertRaises(NightOperationError):
            self.bank.open_account(self.client._id)

    @patch("src.bank.datetime")
    def test_day_ok(self, mock_dt):
        mock_dt.now.return_value.hour = 10  # 10:00 — день
        mock_dt.now.return_value.strftime = lambda fmt: "2025-01-01 10:00:00"
        acc = self.bank.open_account(self.client._id)
        self.assertIsNotNone(acc)


class TestSearchAndAnalytics(unittest.TestCase):

    def setUp(self):
        self.bank = Bank("TestBank")
        self.c1 = Client("Анна", "Петрова", 28)
        self.c2 = Client("Борис", "Козлов", 35)
        self.bank.add_client(self.c1)
        self.bank.add_client(self.c2)

        self.acc1 = self.bank.open_account(self.c1._id, "basic", "RUB")
        self.acc2 = self.bank.open_account(self.c1._id, "savings", "USD", min_balance=100)
        self.acc3 = self.bank.open_account(self.c2._id, "premium", "RUB")

        self.acc1.deposit(5000)
        self.acc2.deposit(3000)
        self.acc3.deposit(10000)

    def test_search_by_client(self):
        results = self.bank.search_accounts(client_id=self.c1._id)
        self.assertEqual(len(results), 2)

    def test_search_by_currency(self):
        results = self.bank.search_accounts(currency="RUB")
        self.assertEqual(len(results), 2)

    def test_search_by_type(self):
        results = self.bank.search_accounts(account_type="savings")
        self.assertEqual(len(results), 1)

    def test_search_combined(self):
        results = self.bank.search_accounts(client_id=self.c1._id, currency="RUB")
        self.assertEqual(len(results), 1)

    def test_total_balance_client(self):
        total = self.bank.get_total_balance(self.c1._id)
        self.assertEqual(total, Decimal("8000"))

    def test_total_balance_bank(self):
        total = self.bank.get_total_balance()
        self.assertEqual(total, Decimal("18000"))

    def test_clients_ranking(self):
        ranking = self.bank.get_clients_ranking()
        self.assertEqual(ranking[0][0]._id, self.c2._id)  # Борис: 10000
        self.assertEqual(ranking[1][0]._id, self.c1._id)  # Анна: 8000

    def test_str(self):
        self.assertIn("TestBank", str(self.bank))


if __name__ == "__main__":
    unittest.main()