"""
Тест VPNKeyLifecycleService с мокированными данными
Проверяем деактивацию и реактивацию VPN ключей
"""

import asyncio
import sys
import os
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock

# Добавляем путь к корневой директории
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from services.vpn_key_lifecycle_service import VPNKeyLifecycleService, deactivate_user_vpn_keys, reactivate_user_vpn_keys

class MockVPNKey:
    """Мок VPN ключа для тестирования"""
    
    def __init__(self, key_id: int, user_id: int, email: str, status: str, node_name: str = "test-node"):
        self.id = key_id
        self.user_id = user_id
        self.xui_email = email  # Используем xui_email вместо email
        self.status = status
        self.node_id = 1
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)
        
        # Мок ноды
        self.node = Mock()
        self.node.id = 1
        self.node.name = node_name
        self.node.x3ui_url = "https://test-panel.com"
        self.node.x3ui_username = "admin"
        self.node.x3ui_password = "password"

class VPNKeyLifecycleTester:
    """Тестер для VPNKeyLifecycleService"""
    
    def __init__(self):
        self.test_results = []
        
    async def log_test(self, test_name: str, success: bool, message: str, details: dict = None):
        """Логирование результатов тестов"""
        result = {
            "test": test_name,
            "success": success,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "details": details or {}
        }
        self.test_results.append(result)
        
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}: {message}")
        if details:
            for key, value in details.items():
                print(f"   {key}: {value}")
    
    async def test_deactivate_user_keys(self):
        """Тест деактивации ключей пользователя"""
        try:
            # Создаем мок сессии БД
            mock_session = AsyncMock()
            
            # Создаем тестовые ключи
            active_keys = [
                MockVPNKey(1, 100, "user1_key1@test.com", "active"),
                MockVPNKey(2, 100, "user1_key2@test.com", "active"),
                MockVPNKey(3, 100, "user1_key3@test.com", "ACTIVE")
            ]
            
            # Мокаем запрос к БД
            mock_result = Mock()
            mock_result.scalars.return_value.all.return_value = active_keys
            mock_session.execute.return_value = mock_result
            
            # Создаем сервис
            service = VPNKeyLifecycleService(mock_session)
            
            # Мокаем методы деактивации
            service._disable_key_in_x3ui = AsyncMock(return_value=True)
            service._update_key_status = AsyncMock(return_value=True)
            
            # Тестируем деактивацию
            result = await service.deactivate_user_keys(100)
            
            # Проверяем результат
            success = (
                result.get("success") == True and
                result.get("deactivated_count") == 3 and
                result.get("total_keys") == 3
            )
            
            await self.log_test(
                "Deactivate User Keys",
                success,
                f"Deactivated {result.get('deactivated_count')} keys successfully",
                {
                    "success": result.get("success"),
                    "deactivated_count": result.get("deactivated_count"),
                    "total_keys": result.get("total_keys"),
                    "errors_count": len(result.get("errors", []))
                }
            )
            
            # Проверяем что методы вызывались правильное количество раз
            assert service._disable_key_in_x3ui.call_count == 3
            assert service._update_key_status.call_count == 3
            
            return success
            
        except Exception as e:
            await self.log_test(
                "Deactivate User Keys",
                False,
                f"Error testing key deactivation: {str(e)}"
            )
            return False
    
    async def test_reactivate_user_keys(self):
        """Тест реактивации ключей пользователя"""
        try:
            # Создаем мок сессии БД
            mock_session = AsyncMock()
            
            # Создаем тестовые приостановленные ключи
            suspended_keys = [
                MockVPNKey(1, 100, "user1_key1@test.com", "suspended"),
                MockVPNKey(2, 100, "user1_key2@test.com", "SUSPENDED")
            ]
            
            # Мокаем запрос к БД
            mock_result = Mock()
            mock_result.scalars.return_value.all.return_value = suspended_keys
            mock_session.execute.return_value = mock_result
            
            # Создаем сервис
            service = VPNKeyLifecycleService(mock_session)
            
            # Мокаем методы реактивации
            service._enable_key_in_x3ui = AsyncMock(return_value=True)
            service._update_key_status = AsyncMock(return_value=True)
            
            # Тестируем реактивацию
            result = await service.reactivate_user_keys(100)
            
            # Проверяем результат
            success = (
                result.get("success") == True and
                result.get("reactivated_count") == 2 and
                result.get("total_keys") == 2
            )
            
            await self.log_test(
                "Reactivate User Keys",
                success,
                f"Reactivated {result.get('reactivated_count')} keys successfully",
                {
                    "success": result.get("success"),
                    "reactivated_count": result.get("reactivated_count"),
                    "total_keys": result.get("total_keys"),
                    "errors_count": len(result.get("errors", []))
                }
            )
            
            # Проверяем что методы вызывались правильное количество раз
            assert service._enable_key_in_x3ui.call_count == 2
            assert service._update_key_status.call_count == 2
            
            return success
            
        except Exception as e:
            await self.log_test(
                "Reactivate User Keys",
                False,
                f"Error testing key reactivation: {str(e)}"
            )
            return False
    
    async def test_get_user_keys_status(self):
        """Тест получения статуса ключей пользователя"""
        try:
            # Создаем мок сессии БД
            mock_session = AsyncMock()
            
            # Создаем тестовые ключи с разными статусами
            user_keys = [
                MockVPNKey(1, 100, "key1@test.com", "active"),
                MockVPNKey(2, 100, "key2@test.com", "suspended"),
                MockVPNKey(3, 100, "key3@test.com", "active"),
                MockVPNKey(4, 100, "key4@test.com", "expired"),
                MockVPNKey(5, 100, "key5@test.com", "revoked")
            ]
            
            # Мокаем запрос к БД
            mock_result = Mock()
            mock_result.scalars.return_value.all.return_value = user_keys
            mock_session.execute.return_value = mock_result
            
            # Создаем сервис
            service = VPNKeyLifecycleService(mock_session)
            
            # Тестируем получение статуса
            result = await service.get_user_keys_status(100)
            
            # Проверяем результат
            status_counts = result.get("status_counts", {})
            success = (
                result.get("success") == True and
                status_counts.get("total") == 5 and
                status_counts.get("active") == 2 and
                status_counts.get("suspended") == 1 and
                status_counts.get("expired") == 1 and
                status_counts.get("revoked") == 1
            )
            
            await self.log_test(
                "Get User Keys Status",
                success,
                f"Retrieved status for {status_counts.get('total')} keys",
                {
                    "success": result.get("success"),
                    "status_counts": status_counts,
                    "keys_count": len(result.get("keys", []))
                }
            )
            
            return success
            
        except Exception as e:
            await self.log_test(
                "Get User Keys Status",
                False,
                f"Error testing keys status: {str(e)}"
            )
            return False
    
    async def test_helper_functions(self):
        """Тест функций-хелперов"""
        try:
            mock_session = AsyncMock()
            
            # Мокаем создание сервиса через патчинг
            from unittest.mock import patch
            
            with patch('services.vpn_key_lifecycle_service.VPNKeyLifecycleService') as mock_service_class:
                mock_service = AsyncMock()
                mock_service_class.return_value = mock_service
                
                # Настраиваем возвращаемые значения
                mock_service.deactivate_user_keys.return_value = {
                    "success": True,
                    "deactivated_count": 2
                }
                mock_service.reactivate_user_keys.return_value = {
                    "success": True,
                    "reactivated_count": 1
                }
                
                # Тестируем функции-хелперы
                deactivate_result = await deactivate_user_vpn_keys(mock_session, 100)
                reactivate_result = await reactivate_user_vpn_keys(mock_session, 100)
                
                # Проверяем результаты
                success = (
                    deactivate_result.get("success") == True and
                    reactivate_result.get("success") == True and
                    mock_service.deactivate_user_keys.called and
                    mock_service.reactivate_user_keys.called
                )
                
                await self.log_test(
                    "Helper Functions",
                    success,
                    "Helper functions work correctly",
                    {
                        "deactivate_success": deactivate_result.get("success"),
                        "reactivate_success": reactivate_result.get("success")
                    }
                )
                
                return success
                
        except Exception as e:
            await self.log_test(
                "Helper Functions",
                False,
                f"Error testing helper functions: {str(e)}"
            )
            return False
    
    async def test_no_keys_scenario(self):
        """Тест сценария когда у пользователя нет ключей"""
        try:
            # Создаем мок сессии БД
            mock_session = AsyncMock()
            
            # Мокаем пустой результат
            mock_result = Mock()
            mock_result.scalars.return_value.all.return_value = []
            mock_session.execute.return_value = mock_result
            
            # Создаем сервис
            service = VPNKeyLifecycleService(mock_session)
            
            # Тестируем деактивацию при отсутствии ключей
            deactivate_result = await service.deactivate_user_keys(999)
            
            # Тестируем реактивацию при отсутствии ключей
            reactivate_result = await service.reactivate_user_keys(999)
            
            # Проверяем результаты
            success = (
                deactivate_result.get("success") == True and
                deactivate_result.get("deactivated_count") == 0 and
                reactivate_result.get("success") == True and
                reactivate_result.get("reactivated_count") == 0
            )
            
            await self.log_test(
                "No Keys Scenario",
                success,
                "Correctly handled user with no keys",
                {
                    "deactivate_success": deactivate_result.get("success"),
                    "deactivate_count": deactivate_result.get("deactivated_count"),
                    "reactivate_success": reactivate_result.get("success"),
                    "reactivate_count": reactivate_result.get("reactivated_count")
                }
            )
            
            return success
            
        except Exception as e:
            await self.log_test(
                "No Keys Scenario",
                False,
                f"Error testing no keys scenario: {str(e)}"
            )
            return False
    
    async def run_all_tests(self):
        """Запуск всех тестов"""
        print("🧪 Starting VPN Key Lifecycle Tests...")
        print("=" * 60)
        
        # Запускаем тесты
        await self.test_deactivate_user_keys()
        await self.test_reactivate_user_keys()
        await self.test_get_user_keys_status()
        await self.test_helper_functions()
        await self.test_no_keys_scenario()
        
        # Выводим отчет
        await self.print_test_report()
    
    async def print_test_report(self):
        """Вывод итогового отчета"""
        print("\n" + "=" * 60)
        print("📊 VPN KEY LIFECYCLE TEST REPORT")
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
            print("✅ All VPN Key Lifecycle tests passed!")
            print("🚀 VPNKeyLifecycleService is working correctly")
            print("🚀 Ready to proceed to Step 6: Automation")
        else:
            print("⚠️ Some lifecycle tests failed. Issues to address:")
            for result in self.test_results:
                if not result["success"]:
                    print(f"   - {result['test']}: {result['message']}")
        
        print("\n🔧 NEXT STEPS:")
        if failed_tests == 0:
            print("1. ✅ VPNKeyLifecycleService implemented and tested")
            print("2. ✅ Key deactivation/reactivation logic working")
            print("3. 🚀 Ready to implement automation scripts (Step 6)")
            print("4. 🚀 Ready to integrate with payment webhooks (Step 7)")
        else:
            print("1. 🔧 Fix failing lifecycle service logic")
            print("2. 🔧 Verify key status management")
            print("3. ⏸️ Hold on automation until lifecycle is stable")

async def main():
    """Точка входа для тестирования"""
    tester = VPNKeyLifecycleTester()
    await tester.run_all_tests()

if __name__ == "__main__":
    print("🚀 VPN Key Lifecycle Testing Suite")
    print("=" * 60)
    print("ℹ️ Testing VPN key lifecycle management")
    print("ℹ️ Using mocked data for validation")
    print("=" * 60)
    
    asyncio.run(main()) 