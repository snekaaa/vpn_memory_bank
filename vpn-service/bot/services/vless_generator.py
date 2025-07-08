import uuid
import json
import base64
import qrcode
from io import BytesIO
from typing import Dict, Any, Optional
import structlog

logger = structlog.get_logger(__name__)

class VLESSGenerator:
    """Генератор VLESS ключей с XTLS-Reality"""
    
    def __init__(self):
        # Список серверов VPN (на базе bezlagov.ru)
        self.servers = [
            {
                "name": "Bezlagov-Main",
                "address": "bezlagov.ru",
                "port": 443,
                "location": "Russia",
                "public_key": "cCnC7VZJyeYr7x6Kz5pvOhRyXyeFEPR8UVE95FKDjGM",
                "short_id": "a5e8c7d9"
            }
        ]
    
    def generate_uuid(self) -> str:
        """Генерация UUID для пользователя"""
        return str(uuid.uuid4())
    
    def get_random_server(self) -> Dict[str, Any]:
        """Получение случайного сервера"""
        import random
        return random.choice(self.servers)
    
    def generate_vless_config(self, user_uuid: str, server: Dict[str, Any]) -> str:
        """Генерация VLESS конфигурации"""
        vless_url = (
            f"vless://{user_uuid}@{server['address']}:{server['port']}"
            f"?encryption=none"
            f"&flow=xtls-rprx-vision"
            f"&security=reality"
            f"&sni=www.cloudflare.com"
            f"&fp=chrome"
            f"&pbk={server['public_key']}"
            f"&sid={server['short_id']}"
            f"&type=tcp"
            f"&headerType=none"
            f"#{server['name']}"
        )
        return vless_url
    
    def generate_sing_box_config(self, user_uuid: str, server: Dict[str, Any]) -> Dict[str, Any]:
        """Генерация конфигурации для Sing-Box"""
        config = {
            "log": {
                "level": "info"
            },
            "inbounds": [
                {
                    "type": "tun",
                    "tag": "tun-in",
                    "interface_name": "tun0",
                    "inet4_address": "172.19.0.1/30",
                    "auto_route": True,
                    "strict_route": True,
                    "sniff": True
                }
            ],
            "outbounds": [
                {
                    "type": "vless",
                    "tag": "proxy",
                    "server": server["address"],
                    "server_port": server["port"],
                    "uuid": user_uuid,
                    "flow": "xtls-rprx-vision",
                    "tls": {
                        "enabled": True,
                        "server_name": "www.cloudflare.com",
                        "reality": {
                            "enabled": True,
                            "public_key": server["public_key"],
                            "short_id": server["short_id"]
                        }
                    }
                },
                {
                    "type": "direct",
                    "tag": "direct"
                }
            ],
            "route": {
                "rules": [
                    {
                        "inbound": "tun-in",
                        "outbound": "proxy"
                    }
                ]
            }
        }
        return config
    
    def generate_v2ray_config(self, user_uuid: str, server: Dict[str, Any]) -> Dict[str, Any]:
        """Генерация конфигурации для V2Ray"""
        config = {
            "log": {
                "loglevel": "info"
            },
            "inbounds": [
                {
                    "port": 10808,
                    "protocol": "socks",
                    "settings": {
                        "auth": "noauth",
                        "udp": True
                    }
                }
            ],
            "outbounds": [
                {
                    "protocol": "vless",
                    "settings": {
                        "vnext": [
                            {
                                "address": server["address"],
                                "port": server["port"],
                                "users": [
                                    {
                                        "id": user_uuid,
                                        "flow": "xtls-rprx-vision",
                                        "encryption": "none"
                                    }
                                ]
                            }
                        ]
                    },
                    "streamSettings": {
                        "network": "tcp",
                        "security": "reality",
                        "realitySettings": {
                            "serverName": "www.cloudflare.com",
                            "fingerprint": "chrome",
                            "publicKey": server["public_key"],
                            "shortId": server["short_id"]
                        }
                    }
                }
            ]
        }
        return config
    
    def generate_qr_code(self, vless_url: str) -> bytes:
        """Генерация QR кода"""
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(vless_url)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Сохраняем в байты
            bio = BytesIO()
            img.save(bio, 'PNG')
            bio.seek(0)
            return bio.read()
            
        except Exception as e:
            logger.error("Failed to generate QR code", error=str(e))
            raise
    
    def create_vpn_key(self, telegram_id: int, subscription_type: str = "trial") -> Dict[str, Any]:
        """Создание VPN ключа для пользователя"""
        try:
            # Генерируем UUID и выбираем сервер
            user_uuid = self.generate_uuid()
            server = self.get_random_server()
            
            # Генерируем конфигурации
            vless_url = self.generate_vless_config(user_uuid, server)
            sing_box_config = self.generate_sing_box_config(user_uuid, server)
            v2ray_config = self.generate_v2ray_config(user_uuid, server)
            qr_code_data = self.generate_qr_code(vless_url)
            
            # Определяем лимиты трафика
            traffic_limits = {
                "trial": 10 * 1024 * 1024 * 1024,  # 10 GB
                "monthly": 100 * 1024 * 1024 * 1024,  # 100 GB
                "quarterly": 300 * 1024 * 1024 * 1024,  # 300 GB
                "yearly": 1200 * 1024 * 1024 * 1024,  # 1200 GB
            }
            
            vpn_key_id = hash(f"{telegram_id}_{user_uuid}") % 1000000
            vpn_key_data = {
                "id": vpn_key_id,
                "name": f"VPN-{vpn_key_id}",
                "telegram_id": telegram_id,
                "uuid": user_uuid,
                "server": server,
                "vless_url": vless_url,
                "sing_box_config": sing_box_config,
                "v2ray_config": v2ray_config,
                "qr_code": base64.b64encode(qr_code_data).decode(),
                "subscription_type": subscription_type,
                "traffic_limit_bytes": traffic_limits.get(subscription_type, traffic_limits["trial"]),
                "traffic_used_bytes": 0,
                "is_active": True,
                "created_at": "2024-01-15T10:00:00Z"
            }
            
            logger.info(
                "VPN key generated successfully",
                telegram_id=telegram_id,
                uuid=user_uuid,
                server_location=server["location"]
            )
            
            return vpn_key_data
            
        except Exception as e:
            logger.error("Failed to create VPN key", telegram_id=telegram_id, error=str(e))
            raise

# Глобальный экземпляр генератора
vless_generator = VLESSGenerator() 