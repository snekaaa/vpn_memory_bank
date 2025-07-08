"""
Модуль для импорта всех моделей базы данных
"""

from config.database import Base, init_database
from models.user import User
from models.subscription import Subscription, SubscriptionStatus, SubscriptionType
from models.payment import Payment, PaymentStatus, PaymentMethod
from models.vpn_key import VPNKey, VPNKeyStatus
from models.vpn_node import VPNNode
from models.user_node_assignment import UserNodeAssignment

__all__ = [
    "Base",
    "init_database",
    "User",
    "Subscription", "SubscriptionStatus", "SubscriptionType",
    "Payment", "PaymentStatus", "PaymentMethod",
    "VPNKey", "VPNKeyStatus",
    "VPNNode",
    "UserNodeAssignment"
] 