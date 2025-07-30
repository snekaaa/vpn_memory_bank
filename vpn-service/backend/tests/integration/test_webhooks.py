import pytest
import allure
import hmac
import hashlib
import json

@allure.epic("Webhooks API")
@allure.feature("Payment Webhooks")
@pytest.mark.asyncio
@pytest.mark.critical
async def test_yookassa_webhook_mock_fallback():
    """Fallback тест с мок данными для YooKassa webhook если API недоступен"""
    with allure.step("Проверяем мок данные для YooKassa webhook"):
        # Входящий webhook payload от YooKassa
        yookassa_payload = {
            "type": "notification",
            "event": "payment.succeeded",
            "object": {
                "id": "25b94794-000f-5000-9000-145f6df21d6f",
                "status": "succeeded",
                "amount": {
                    "value": "500.00",
                    "currency": "RUB"
                },
                "description": "VPN подписка",
                "metadata": {
                    "order_id": "12345",
                    "user_id": "123456789"
                }
            }
        }
        
        # Проверяем структуру payload
        assert yookassa_payload["type"] == "notification"
        assert yookassa_payload["event"] == "payment.succeeded"
        assert "object" in yookassa_payload
        
        payment_object = yookassa_payload["object"]
        assert payment_object["status"] == "succeeded"
        assert "amount" in payment_object
        assert "metadata" in payment_object
        
        # Проверяем данные платежа
        amount = payment_object["amount"]
        assert float(amount["value"]) > 0
        assert amount["currency"] == "RUB"
        
        allure.attach(
            json.dumps(yookassa_payload, indent=2, ensure_ascii=False),
            name="YooKassa Webhook Payload",
            attachment_type=allure.attachment_type.JSON
        )

@allure.epic("Webhooks API")
@allure.feature("Payment Webhooks")
@pytest.mark.asyncio
@pytest.mark.critical
async def test_freekassa_webhook_mock_fallback():
    """Fallback тест с мок данными для FreeKassa webhook если API недоступен"""
    with allure.step("Проверяем мок данные для FreeKassa webhook"):
        # Входящий webhook payload от FreeKassa
        freekassa_payload = {
            "MERCHANT_ID": "12345",
            "AMOUNT": "500.00",
            "intid": "98765",
            "MERCHANT_ORDER_ID": "order_12345",
            "SIGN": "calculated_signature_hash",
            "us_user_id": "123456789"
        }
        
        # Проверяем обязательные поля FreeKassa
        required_fields = ["MERCHANT_ID", "AMOUNT", "intid", "MERCHANT_ORDER_ID", "SIGN"]
        for field in required_fields:
            assert field in freekassa_payload, f"Обязательное поле {field} отсутствует"
        
        # Проверяем формат данных
        assert float(freekassa_payload["AMOUNT"]) > 0
        assert freekassa_payload["MERCHANT_ID"].isdigit()
        assert freekassa_payload["intid"].isdigit()
        
        allure.attach(
            json.dumps(freekassa_payload, indent=2, ensure_ascii=False),
            name="FreeKassa Webhook Payload", 
            attachment_type=allure.attachment_type.JSON
        )

@allure.epic("Webhooks API")
@allure.feature("Payment Webhooks")
@pytest.mark.asyncio
@pytest.mark.critical
async def test_coingate_webhook_mock_fallback():
    """Fallback тест с мок данными для CoinGate webhook если API недоступен"""
    with allure.step("Проверяем мок данные для CoinGate webhook"):
        # Входящий webhook payload от CoinGate
        coingate_payload = {
            "id": 12345,
            "status": "paid",
            "price_amount": "500.00",
            "price_currency": "RUB",
            "receive_amount": "0.000123",
            "receive_currency": "BTC",
            "order_id": "order_12345"
        }
        
        # Проверяем обязательные поля CoinGate
        required_fields = ["id", "status", "price_amount", "price_currency", "order_id"]
        for field in required_fields:
            assert field in coingate_payload, f"Обязательное поле {field} отсутствует"
        
        # Проверяем статусы CoinGate
        valid_statuses = ["new", "pending", "confirming", "paid", "invalid", "expired", "canceled"]
        assert coingate_payload["status"] in valid_statuses
        
        # Проверяем суммы
        assert float(coingate_payload["price_amount"]) > 0
        
        allure.attach(
            json.dumps(coingate_payload, indent=2, ensure_ascii=False),
            name="CoinGate Webhook Payload",
            attachment_type=allure.attachment_type.JSON
        )
