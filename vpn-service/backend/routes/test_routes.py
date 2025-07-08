from fastapi import APIRouter
import structlog
from services.node_automation import NodeDeploymentConfig

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/test", tags=["test"])

@router.post("/reality-keys")
async def test_reality_keys():
    """Тестирование генерации Reality ключей"""
    try:
        # Создаем тестовый config
        config = NodeDeploymentConfig(
            ssh_host="test",
            ssh_password="test",
            name="Test Node"
        )
        
        # Тестируем fallback метод
        public_key, private_key = config._generate_fallback_keys()
        
        return {
            "success": True,
            "keys": {
                "public_key": public_key,
                "private_key": private_key,
                "public_key_length": len(public_key) if public_key else 0,
                "private_key_length": len(private_key) if private_key else 0
            },
            "message": "Reality keys generated successfully"
        }
    except Exception as e:
        logger.error("Error testing reality keys", error=str(e))
        return {
            "success": False,
            "error": str(e)
        }

@router.post("/xray-command")
async def test_xray_command():
    """Тестирование генерации Reality ключей через RealityKeyGenerator"""
    try:
        from services.reality_key_generator import RealityKeyGenerator
        
        # Генерируем ключи через новый генератор
        keys = RealityKeyGenerator.generate_keys()
        
        # Валидируем ключи
        is_valid = RealityKeyGenerator.validate_keys(keys.private_key, keys.public_key)
        
        return {
            "success": True,
            "generator_available": True,
            "method": keys.generation_method,
            "keys": {
                "public_key": keys.public_key,
                "private_key": keys.private_key,
                "public_key_length": len(keys.public_key),
                "private_key_length": len(keys.private_key)
            },
            "validation": {
                "keys_valid": is_valid,
                "public_key_valid_base64": len(keys.public_key) == 44,
                "private_key_valid_base64": len(keys.private_key) == 44
            },
            "message": f"Reality keys generated successfully via {keys.generation_method}"
        }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.post("/test-generate-client-url")
async def test_generate_client_url():
    """Тестовый эндпоинт для проверки generate_client_url без реального подключения к панели"""
    try:
        from services.x3ui_client import X3UIClient
        
        # Создаем X3UIClient с тестовыми данными
        x3ui_client = X3UIClient(
            base_url="https://78.40.193.142:2053/KZcdnNax4qgt1CY",
            username="admin",
            password="admin"
        )
        
        # Тестовые данные
        test_inbound_id = 1
        test_client_id = "test-uuid-12345"
        
        # Mock данные inbound для тестирования
        mock_inbounds = [{
            "id": 1,
            "port": 443,
            "protocol": "vless",
            "enable": True,
            "settings": '{"clients": [{"id": "test-uuid-12345", "email": "test@vpn.local", "flow": "xtls-rprx-vision"}]}',
            "streamSettings": '{"security": "reality", "realitySettings": {"publicKey": "xHPTLrfwDZK6WQ1DbLSyei5KEXIvP6_oxX5TYvqj5Xk", "shortIds": ["ffffffffff"], "serverNames": ["apple.com"]}}'
        }]
        
        # Monkey patch метод get_inbounds для возврата mock данных
        original_get_inbounds = x3ui_client.get_inbounds
        
        async def mock_get_inbounds():
            return mock_inbounds
        
        x3ui_client.get_inbounds = mock_get_inbounds
        
        # Тестируем generate_client_url
        result = await x3ui_client.generate_client_url(test_inbound_id, test_client_id)
        
        # Восстанавливаем оригинальный метод
        x3ui_client.get_inbounds = original_get_inbounds
        
        return {
            "success": True,
            "test_inbound_id": test_inbound_id,
            "test_client_id": test_client_id,
            "generated_url": result,
            "mock_data_used": True,
            "url_length": len(result) if result else 0
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "test_inbound_id": test_inbound_id if 'test_inbound_id' in locals() else None,
            "test_client_id": test_client_id if 'test_client_id' in locals() else None
        } 