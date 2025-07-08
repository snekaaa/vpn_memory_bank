"""
VLESS Generator Service
Генерация реальных VLESS конфигураций независимо от X3UI панели
"""

import uuid
import json
import base64
from typing import Dict, Any, List, Optional
from urllib.parse import quote, urlencode
from dataclasses import dataclass


@dataclass
class ServerConfig:
    """Конфигурация сервера для VLESS"""
    host: str
    port: int
    uuid: str
    security: str = "reality"
    flow: str = "xtls-rprx-vision"
    encryption: str = "none"
    sni: str = "www.cloudflare.com"
    fp: str = "chrome"
    pbk: str = "SbVKNfKKo3Vs0jMCge6FFQN1KdU8_yPGOQHIlLCLOUk"  # Публичный ключ Reality
    sid: str = ""
    spx: str = "/"
    type: str = "tcp"
    headertype: str = "none"
    alpn: str = "h2,http/1.1"


class VLESSGenerator:
    """Генератор VLESS конфигураций"""
    
    def __init__(self):
        # Хардкод серверов убран - используем динамические ноды из базы данных
        # Оставляем default_servers пустым для совместимости
        self.default_servers = {}
    
    def generate_uuid(self) -> str:
        """Генерация UUID для клиента"""
        return str(uuid.uuid4())
    
    def generate_vless_url(
        self, 
        server_config: ServerConfig, 
        client_uuid: str, 
        alias: Optional[str] = None
    ) -> str:
        """
        Генерация VLESS URL
        
        Args:
            server_config: Конфигурация сервера
            client_uuid: UUID клиента  
            alias: Алиас соединения
            
        Returns:
            VLESS URL строка
        """
        # Обновляем UUID в конфигурации сервера
        server_config.uuid = client_uuid
        
        # Параметры для Reality
        params = {
            "encryption": server_config.encryption,
            "flow": server_config.flow,
            "security": server_config.security,
            "sni": server_config.sni,
            "fp": server_config.fp,
            "pbk": server_config.pbk,
            "sid": server_config.sid,
            "spx": quote(server_config.spx),
            "type": server_config.type,
            "headerType": server_config.headertype,
            "alpn": server_config.alpn
        }
        
        # Формируем URL
        query_string = urlencode(params)
        
        # Создаем алиас если не передан
        if not alias:
            alias = f"VPN-{server_config.host}"
        
        vless_url = (
            f"vless://{client_uuid}@{server_config.host}:{server_config.port}"
            f"?{query_string}#{quote(alias)}"
        )
        
        return vless_url
    
    def generate_vless_for_node(
        self, 
        node_host: str, 
        node_port: int = 8080,
        client_uuid: Optional[str] = None,
        alias: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Генерация VLESS конфигурации для произвольной ноды
        
        Args:
            node_host: IP/хост ноды
            node_port: Порт ноды
            client_uuid: UUID клиента (генерируется если не указан)
            alias: Алиас соединения
            
        Returns:
            Словарь с UUID и VLESS URL
        """
        if not client_uuid:
            client_uuid = self.generate_uuid()
        
        # Создаем конфигурацию для ноды
        server_config = ServerConfig(
            host=node_host,
            port=node_port,
            uuid=client_uuid,
            sni="www.cloudflare.com",
            pbk="SbVKNfKKo3Vs0jMCge6FFQN1KdU8_yPGOQHIlLCLOUk"
        )
        
        if not alias:
            alias = f"VPN-Node-{node_host}"
        
        vless_url = self.generate_vless_url(server_config, client_uuid, alias)
        
        return {
            "uuid": client_uuid,
            "vless_url": vless_url,
            "host": node_host,
            "port": node_port,
            "alias": alias
        }
    
    def generate_vless_for_user(
        self, 
        telegram_id: int, 
        server_key: str = "vpn1",
        custom_alias: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Генерация VLESS конфигурации для пользователя
        
        Args:
            telegram_id: Telegram ID пользователя
            server_key: Ключ сервера из default_servers
            custom_alias: Пользовательский алиас
            
        Returns:
            Словарь с конфигурацией
        """
        if server_key not in self.default_servers:
            server_key = "vpn1"  # Fallback
        
        server_config = self.default_servers[server_key]
        client_uuid = self.generate_uuid()
        
        alias = custom_alias or f"VPN-User-{telegram_id}"
        
        vless_url = self.generate_vless_url(server_config, client_uuid, alias)
        
        return {
            "uuid": client_uuid,
            "vless_url": vless_url,
            "server": server_key,
            "host": server_config.host,
            "port": server_config.port,
            "telegram_id": telegram_id,
            "alias": alias
        }
    
    def get_all_servers(self) -> Dict[str, Dict[str, Any]]:
        """Получение списка всех доступных серверов"""
        servers = {}
        for key, config in self.default_servers.items():
            servers[key] = {
                "host": config.host,
                "port": config.port,
                "sni": config.sni,
                "security": config.security,
                "type": config.type
            }
        return servers
    
    def generate_config_json(
        self, 
        client_uuid: str, 
        server_config: ServerConfig
    ) -> Dict[str, Any]:
        """
        Генерация JSON конфигурации для V2Ray/Xray клиентов
        
        Args:
            client_uuid: UUID клиента
            server_config: Конфигурация сервера
            
        Returns:
            JSON конфигурация
        """
        config = {
            "log": {
                "access": "",
                "error": "",
                "loglevel": "warning"
            },
            "inbounds": [{
                "tag": "proxy",
                "port": 10808,
                "protocol": "socks",
                "settings": {
                    "auth": "noauth",
                    "udp": True,
                    "userLevel": 8
                },
                "sniffing": {
                    "enabled": True,
                    "destOverride": ["http", "tls"]
                }
            }],
            "outbounds": [{
                "tag": "proxy",
                "protocol": "vless",
                "settings": {
                    "vnext": [{
                        "address": server_config.host,
                        "port": server_config.port,
                        "users": [{
                            "id": client_uuid,
                            "encryption": server_config.encryption,
                            "flow": server_config.flow
                        }]
                    }]
                },
                "streamSettings": {
                    "network": server_config.type,
                    "security": server_config.security,
                    "realitySettings": {
                        "serverName": server_config.sni,
                        "fingerprint": server_config.fp,
                        "publicKey": server_config.pbk,
                        "shortId": server_config.sid,
                        "spiderX": server_config.spx
                    },
                    "tcpSettings": {
                        "header": {
                            "type": server_config.headertype
                        }
                    }
                }
            }],
            "routing": {
                "domainStrategy": "IPIfNonMatch",
                "rules": [{
                    "type": "field",
                    "inboundTag": ["proxy"],
                    "outboundTag": "proxy"
                }]
            }
        }
        
        return config


# Глобальный экземпляр генератора
vless_generator = VLESSGenerator() 