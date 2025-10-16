from enum import Enum


class UserTypeEnum(str, Enum):
    ADMIN = "admin"
    USER = "user"
    # SUBUSER = "sub-user"


class Status(str, Enum):
    PENDING = "Pending"
    PAID = "Paid"
    CANCELLED  = "Cancelled"
    DRAFT  = "Draft"

class PaymentMode(str, Enum):
    CASH = "Cash"
    CHEQUE  = "Cheque"
    UPI  = "Upi"
    CARD  = "Card"
    NETBANKING  = "NetBanking"
    EMI  = "Emi"

class BalanceType(str, Enum):
    DEBIT = "Debit"
    CREDIT = "Credit"

class PlanNameEnum(str, Enum):
    basic = "Basic"
    plus = "Plus"
    pro = "Pro"
    premium = "Premium"
    elite = "Elite"