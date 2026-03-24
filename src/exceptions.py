class AccountFrozenError(Exception): pass
class AccountClosedError(Exception): pass
class InvalidOperationError(Exception): pass
class InsufficientFundsError(Exception): pass
class AuthenticationError(Exception): pass
class ClientBlockedError(Exception): pass
class NightOperationError(Exception): pass