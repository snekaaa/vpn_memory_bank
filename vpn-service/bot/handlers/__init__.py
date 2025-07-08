"""
Handlers package for VPN Telegram Bot
"""

# Import all routers for easy access
from .start import start_router
from .vpn_simplified import router as vpn_simplified_router

__all__ = [
    'start_router',
    'vpn_simplified_router'
] 