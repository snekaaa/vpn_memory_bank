"""
Тест обновленных VPN handlers с проверкой подписки
Проверяем интеграцию VPNAccessControlService с bot handlers
"""

import asyncio
import sys
import os
from unittest.mock import Mock, AsyncMock, patch

# Добавляем пути к модулям
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '../backend'))

print("🔍 Starting VPN Handlers Test")

# Проверяем доступность импортов
try:
    from handlers.vpn_simplified import check_vpn_access, show_subscription_required_message
    print("✅ VPN handlers imported successfully")
except ImportError as e:
    print(f"❌ Failed to import VPN handlers: {e}")
    sys.exit(1)

# Создаем мок объекты для тестирования
class MockMessage:
    """Мок сообщения для тестирования"""
    
    def __init__(self):
        self.text = ""
        self.parse_mode = None
        self.reply_markup = None
        
    async def edit_text(self, text, parse_mode=None, reply_markup=None, **kwargs):
        self.text = text
        self.parse_mode = parse_mode
        self.reply_markup = reply_markup
        print(f"📝 Message updated: {text[:100]}...")

class MockCallbackQuery:
    """Мок callback query для тестирования"""
    
    def __init__(self, telegram_id: int):
        self.from_user = Mock()
        self.from_user.id = telegram_id
        self.from_user.username = "testuser"
        self.from_user.first_name = "Test"
        self.message = MockMessage()
        
    async def answer(self, text=None):
        pass

class VPNHandlersTestSuite:
    """Тестовый набор для VPN handlers"""
    
    def __init__(self):
        self.test_results = []
        
    async def log_test(self, test_name: str, success: bool, message: str):
        """Логирование результатов тестов"""
        self.test_results.append({
            "test": test_name,
            "success": success,
            "message": message
        })
        
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}: {message}")
    
    async def test_check_vpn_access_with_mocked_db(self):
        """Тест функции check_vpn_access с мокированной БД"""
        try:
            # Мокаем access control
            with patch('handlers.vpn_simplified.VPN_ACCESS_CONTROL_AVAILABLE', True):
                with patch('handlers.vpn_simplified.get_db') as mock_get_db:
                    with patch('handlers.vpn_simplified.check_user_vpn_access') as mock_check:
                        
                        # Настраиваем моки
                        mock_session = AsyncMock()
                        mock_get_db.return_value.__aiter__ = AsyncMock(return_value=[mock_session])
                        mock_check.return_value = {
                            "has_access": False,
                            "reason": "no_subscription",
                            "message": "Нет активной подписки"
                        }
                        
                        # Тестируем функцию
                        result = await check_vpn_access(12345)
                        
                        # Проверяем результат
                        success = (
                            result.get("has_access") == False and
                            result.get("reason") == "no_subscription"
                        )
                        
                        await self.log_test(
                            "VPN Access Check",
                            success,
                            f"Access check returned: {result}"
                        )
                        
                        return success
                        
        except Exception as e:
            await self.log_test(
                "VPN Access Check",
                False,
                f"Error testing VPN access check: {str(e)}"
            )
            return False
    
    async def test_show_subscription_required_message(self):
        """Тест функции show_subscription_required_message"""
        try:
            # Создаем мок сообщения
            message = MockMessage()
            
            # Создаем тестовые данные
            access_result = {
                "has_access": False,
                "reason": "no_subscription",
                "message": "Нет активной подписки",
                "days_remaining": 0
            }
            
            # Мокаем клавиатуру
            with patch('handlers.vpn_simplified.get_subscription_keyboard_with_autopay') as mock_keyboard:
                mock_keyboard.return_value = Mock()
                
                # Тестируем функцию
                await show_subscription_required_message(message, access_result)
                
                # Проверяем результат
                success = (
                    "подписк" in message.text.lower() and
                    message.parse_mode == "Markdown"
                )
                
                await self.log_test(
                    "Subscription Required Message",
                    success,
                    f"Message displayed correctly with subscription prompt"
                )
                
                return success
                
        except Exception as e:
            await self.log_test(
                "Subscription Required Message",
                False,
                f"Error testing subscription message: {str(e)}"
            )
            return False
    
    async def test_full_handler_flow_no_access(self):
        """Тест полного потока handler'а для пользователя без доступа"""
        try:
            # Импортируем handler
            from handlers.vpn_simplified import handle_create_or_remind_key
            
            # Создаем мок callback
            callback = MockCallbackQuery(telegram_id=99999)
            
            # Мокаем все зависимости
            with patch('handlers.vpn_simplified.check_vpn_access') as mock_check:
                with patch('handlers.vpn_simplified.show_subscription_required_message') as mock_show:
                    
                    # Настраиваем мок - нет доступа
                    mock_check.return_value = {
                        "has_access": False,
                        "reason": "no_subscription"
                    }
                    mock_show.return_value = None
                    
                    # Тестируем handler
                    await handle_create_or_remind_key(callback)
                    
                    # Проверяем что показано сообщение о проверке доступа
                    access_check_shown = "проверяем доступ" in callback.message.text.lower()
                    
                    # Проверяем что вызвано отображение подписки
                    subscription_shown = mock_show.called
                    
                    success = access_check_shown and subscription_shown
                    
                    await self.log_test(
                        "Full Handler Flow (No Access)",
                        success,
                        f"Handler correctly blocked access and showed subscription"
                    )
                    
                    return success
                    
        except Exception as e:
            await self.log_test(
                "Full Handler Flow (No Access)",
                False,
                f"Error testing full handler flow: {str(e)}"
            )
            return False
    
    async def test_full_handler_flow_with_access(self):
        """Тест полного потока handler'а для пользователя с доступом"""
        try:
            from handlers.vpn_simplified import handle_create_or_remind_key
            
            callback = MockCallbackQuery(telegram_id=12345)
            
            # Мокаем все зависимости
            with patch('handlers.vpn_simplified.check_vpn_access') as mock_check:
                with patch('handlers.vpn_simplified.vpn_manager') as mock_vpn_manager:
                    
                    # Настраиваем моки - есть доступ
                    mock_check.return_value = {
                        "has_access": True,
                        "reason": "active_subscription"
                    }
                    
                    mock_vpn_manager.get_or_create_user_key.return_value = {
                        "vless_url": "vless://test-key@server:443",
                        "id": 123
                    }
                    
                    # Тестируем handler
                    await handle_create_or_remind_key(callback)
                    
                    # Проверяем что ключ был запрошен
                    vpn_key_requested = mock_vpn_manager.get_or_create_user_key.called
                    
                    success = vpn_key_requested
                    
                    await self.log_test(
                        "Full Handler Flow (With Access)",
                        success,
                        f"Handler correctly provided VPN key for authorized user"
                    )
                    
                    return success
                    
        except Exception as e:
            await self.log_test(
                "Full Handler Flow (With Access)",
                False,
                f"Error testing handler with access: {str(e)}"
            )
            return False
    
    async def run_all_tests(self):
        """Запуск всех тестов"""
        print("\n🧪 Starting VPN Handlers Integration Tests...")
        print("=" * 60)
        
        # Запускаем тесты
        await self.test_check_vpn_access_with_mocked_db()
        await self.test_show_subscription_required_message()
        await self.test_full_handler_flow_no_access()
        await self.test_full_handler_flow_with_access()
        
        # Выводим отчет
        await self.print_test_report()
    
    async def print_test_report(self):
        """Вывод итогового отчета"""
        print("\n" + "=" * 60)
        print("📊 VPN HANDLERS TEST REPORT")
        print("=" * 60)
        
        total_tests = len(self.test_results)
        passed_tests = len([r for r in self.test_results if r["success"]])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests*100):.1f}%" if total_tests > 0 else "N/A")
        
        print("\n📋 DETAILED RESULTS:")
        for result in self.test_results:
            status = "✅" if result["success"] else "❌"
            print(f"{status} {result['test']}: {result['message']}")
        
        print("\n💡 RECOMMENDATIONS:")
        if failed_tests == 0:
            print("✅ All VPN handler tests passed!")
            print("🚀 VPN handlers are correctly integrated with subscription checking")
            print("🚀 Ready to proceed to Step 5: VPNKeyLifecycleService")
        else:
            print("⚠️ Some VPN handler tests failed. Issues to address:")
            for result in self.test_results:
                if not result["success"]:
                    print(f"   - {result['test']}: {result['message']}")
        
        print("\n🔧 NEXT STEPS:")
        if failed_tests == 0:
            print("1. ✅ VPN handlers updated with subscription checking")
            print("2. ✅ Integration between bot and access control working")
            print("3. 🚀 Ready to implement VPNKeyLifecycleService (Step 5)")
            print("4. 🚀 Continue with automatic key deactivation/reactivation")
        else:
            print("1. 🔧 Fix failing VPN handler integration")
            print("2. 🔧 Verify imports and dependencies")
            print("3. ⏸️ Hold on lifecycle service until handlers are stable")

async def main():
    """Точка входа для тестирования"""
    tester = VPNHandlersTestSuite()
    await tester.run_all_tests()

if __name__ == "__main__":
    print("🚀 VPN Handlers Integration Testing Suite")
    print("=" * 60)
    print("ℹ️ Testing VPN handlers with subscription access control")
    print("=" * 60)
    
    asyncio.run(main()) 