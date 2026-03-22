import unittest
from src.models import Owner, BankAccount
from src.exceptions import (
    AccountFrozenError, AccountClosedError,
    InvalidOperationError, InsufficientFundsError
)


class TestBankAccount(unittest.TestCase):

    def setUp(self):
        """Создаётся перед каждым тестом"""
        self.owner = Owner("Иван", "Иванов", 30)
        self.acc = BankAccount(self.owner, "USD")

    # --- Создание ---
    def test_create_account(self):
        self.assertEqual(self.acc._balance, 0.0)
        self.assertEqual(self.acc._status, "active")
        self.assertEqual(self.acc._currency, "USD")

    def test_invalid_currency(self):
        with self.assertRaises(InvalidOperationError): BankAccount(self.owner, "BTC")

    # --- Пополнение ---
    def test_deposit(self):
        self.acc.deposit(1000)
        self.assertEqual(self.acc._balance, 1000.0)

    def test_deposit_negative(self):
        with self.assertRaises(InvalidOperationError): self.acc.deposit(-100)

    def test_deposit_not_number(self):
        with self.assertRaises(InvalidOperationError): self.acc.deposit("сто")

    # --- Снятие ---
    def test_withdraw(self):
        self.acc.deposit(1000)
        self.acc.withdraw(300)
        self.assertEqual(self.acc._balance, 700.0)

    def test_withdraw_insufficient(self):
        self.acc.deposit(100)
        with self.assertRaises(InsufficientFundsError): self.acc.withdraw(9999)

    # --- Статусы ---
    def test_frozen_account(self):
        self.acc.freeze()
        with self.assertRaises(AccountFrozenError): self.acc.deposit(100)

    def test_closed_account(self):
        self.acc.close()
        with self.assertRaises(AccountClosedError): self.acc.withdraw(100)

    def test_reactivate_account(self):
        self.acc.deposit(500)
        self.acc.freeze()
        self.acc.active()
        self.acc.deposit(100)
        self.assertEqual(self.acc._balance, 600.0)

    # --- Инфо и строка ---
    def test_get_account_info(self):
        info = self.acc.get_account_info()
        self.assertIn("id", info)
        self.assertIn("balance", info)
        self.assertIn("currency", info)

    def test_str(self):
        result = str(self.acc)
        self.assertIn("BankAccount", result)
        self.assertIn("USD", result)

    # --- Owner ---
    def test_owner_str(self):
        self.assertEqual(str(self.owner), "Иван Иванов, 30 лет")


if __name__ == "__main__":
    unittest.main()
