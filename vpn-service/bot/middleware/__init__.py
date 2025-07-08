"""
Middleware package for VPN Telegram Bot
"""

from .auth import AuthMiddleware

__all__ = ['AuthMiddleware'] 