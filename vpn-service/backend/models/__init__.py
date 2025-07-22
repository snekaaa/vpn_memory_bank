# Import all models to ensure they are registered with SQLAlchemy
from .user import User
from .vpn_key import VPNKey
from .vpn_node import VPNNode
from .subscription import Subscription
from .payment import Payment
from .payment_provider import PaymentProvider
from .country import Country
from .user_server_assignment import UserServerAssignment
from .user_node_assignment import UserNodeAssignment
from .auto_payment import AutoPayment
from .payment_retry_attempt import PaymentRetryAttempt
from .user_notification_preferences import UserNotificationPreferences
from .server_switch_log import ServerSwitchLog
from .app_settings import AppSettings

__all__ = [
    "User",
    "VPNKey", 
    "VPNNode",
    "Subscription",
    "Payment",
    "PaymentProvider",
    "Country",
    "UserServerAssignment",
    "UserNodeAssignment",
    "AutoPayment",
    "PaymentRetryAttempt",
    "UserNotificationPreferences",
    "ServerSwitchLog",
    "AppSettings"
] 