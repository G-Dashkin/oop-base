import unittest
from decimal import Decimal
from src.models import Owner, SavingsAccount, PremiumAccount, InvestmentAccount
from src.exceptions import (
    AccountFrozenError, InvalidOperationError, InsufficientFundsError
)


class TestSavingsAccount(unittest.TestCase):

    def setUp(self):
        self.owner = Owner("Анна", "Петрова", 28)
        self.acc = SavingsAccount(self.owner, "RUB", min_balance=1000, monthly_rate=0.5)

    def test_create(self):
        self.assertEqual(self.acc._min_balance, Decimal("1000"))
        self.assertEqual(self.acc._monthly_rate, Decimal("0.5"))

    def test_withdraw_respects_min_balance(self):
        self.acc.deposit(5000)
        self.acc.withdraw(3000)  # остаётся 2000 > 1000
        self.assertEqual(self.acc._balance, Decimal("2000"))

    def test_withdraw_below_min_balance(self):
        self.acc.deposit(2000)
        with self.assertRaises(InsufficientFundsError): self.acc.withdraw(1500)

    def test_apply_monthly_interest(self):
        self.acc.deposit(10000)
        interest = self.acc.apply_monthly_interest()  # 10000 * 0.5% = 50
        self.assertEqual(interest, Decimal("50.0"))
        self.assertEqual(self.acc._balance, Decimal("10050.0"))

    def test_interest_on_frozen(self):
        self.acc.deposit(5000)
        self.acc.freeze()
        with self.assertRaises(AccountFrozenError): self.acc.apply_monthly_interest()

    def test_str(self):
        result = str(self.acc)
        self.assertIn("SavingsAccount", result)
        self.assertIn("0.5%", result)

    def test_get_account_info(self):
        info = self.acc.get_account_info()
        self.assertEqual(info["type"], "savings")
        self.assertIn("min_balance", info)


class TestPremiumAccount(unittest.TestCase):

    def setUp(self):
        self.owner = Owner("Борис", "Сидоров", 45)
        self.acc = PremiumAccount(self.owner, "USD", overdraft_limit=5000, withdraw_commission=50)

    def test_create(self):
        self.assertEqual(self.acc._overdraft_limit, Decimal("5000"))
        self.assertEqual(self.acc._withdraw_commission, Decimal("50"))

    def test_withdraw_with_commission(self):
        self.acc.deposit(1000)
        self.acc.withdraw(500)  # снимает 500 + 50 комиссия = 550
        self.assertEqual(self.acc._balance, Decimal("450"))

    def test_withdraw_with_overdraft(self):
        self.acc.deposit(100)
        self.acc.withdraw(200)  # 200 + 50 = 250, но есть овердрафт 5000
        self.assertEqual(self.acc._balance, Decimal("-150"))  # 100 - 250

    def test_withdraw_exceeds_overdraft(self):
        self.acc.deposit(100)
        with self.assertRaises(InsufficientFundsError): self.acc.withdraw(6000)

    def test_str(self):
        result = str(self.acc)
        self.assertIn("PremiumAccount", result)
        self.assertIn("overdraft", result)

    def test_get_account_info(self):
        info = self.acc.get_account_info()
        self.assertEqual(info["type"], "premium")
        self.assertIn("overdraft_limit", info)


class TestInvestmentAccount(unittest.TestCase):

    def setUp(self):
        self.owner = Owner("Елена", "Козлова", 35)
        self.acc = InvestmentAccount(self.owner, "USD")

    def test_buy_asset(self):
        self.acc.deposit(10000)
        self.acc.buy_asset("stocks", 3000)
        self.assertEqual(self.acc._balance, Decimal("7000"))
        self.assertEqual(self.acc._portfolio["stocks"], Decimal("3000"))

    def test_buy_invalid_asset(self):
        self.acc.deposit(5000)
        with self.assertRaises(InvalidOperationError): self.acc.buy_asset("crypto", 1000)

    def test_buy_insufficient_funds(self):
        self.acc.deposit(500)
        with self.assertRaises(InsufficientFundsError): self.acc.buy_asset("bonds", 1000)

    def test_sell_asset(self):
        self.acc.deposit(5000)
        self.acc.buy_asset("etf", 3000)
        self.acc.sell_asset("etf", 1000)
        self.assertEqual(self.acc._portfolio["etf"], Decimal("2000"))
        self.assertEqual(self.acc._balance, Decimal("3000"))

    def test_sell_all_removes_from_portfolio(self):
        self.acc.deposit(5000)
        self.acc.buy_asset("bonds", 2000)
        self.acc.sell_asset("bonds", 2000)
        self.assertNotIn("bonds", self.acc._portfolio)

    def test_sell_nonexistent_asset(self):
        with self.assertRaises(InvalidOperationError): self.acc.sell_asset("stocks", 100)

    def test_project_yearly_growth(self):
        self.acc.deposit(10000)
        self.acc.buy_asset("stocks", 5000)  # 12% = 600
        self.acc.buy_asset("bonds", 3000)   # 6% = 180
        projection = self.acc.project_yearly_growth()
        self.assertEqual(projection["total_growth"], Decimal("780"))

    def test_withdraw_only_free_balance(self):
        self.acc.deposit(10000)
        self.acc.buy_asset("stocks", 7000)
        with self.assertRaises(InsufficientFundsError): self.acc.withdraw(5000)
        self.acc.withdraw(3000)  # свободных 3000
        self.assertEqual(self.acc._balance, Decimal("0"))

    def test_str(self):
        result = str(self.acc)
        self.assertIn("InvestmentAccount", result)
        self.assertIn("portfolio", result)

    def test_get_account_info(self):
        self.acc.deposit(5000)
        self.acc.buy_asset("etf", 2000)
        info = self.acc.get_account_info()
        self.assertEqual(info["type"], "investment")
        self.assertEqual(info["portfolio_value"], Decimal("2000"))


class TestPolymorphism(unittest.TestCase):
    """Тест полиморфизма: все типы счетов через единый интерфейс"""

    def test_all_accounts_have_withdraw(self):
        owner = Owner("Тест", "Тестов", 25)
        accounts = [
            SavingsAccount(owner, "RUB"),
            PremiumAccount(owner, "USD"),
            InvestmentAccount(owner, "EUR"),
        ]
        for acc in accounts:
            acc.deposit(50000)
            acc.withdraw(100)
            info = acc.get_account_info()
            self.assertIn("id", info)
            self.assertIsInstance(str(acc), str)


if __name__ == "__main__":
    unittest.main()