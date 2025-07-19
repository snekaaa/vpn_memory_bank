"""
Простой тест VPNAccessControlService без подключения к БД
Проверяем основную логику работы сервиса
"""

import asyncio
import sys
import os
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock

# Добавляем путь к корневой директории
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Мокаем импорты для тестирования без БД
from unittest.mock import patch
from services.vpn_access_control_service import VPNAccessControlService

class MockUser:
    """Мок пользователя для тестирования"""
    
    def __init__(self, user_id: int, telegram_id: int, has_active: bool, valid_until=None):
        self.id = user_id
        self.telegram_id = telegram_id
        self.subscription_status = Mock()
        self.subscription_status.value = "active" if has_active else "expired"
        self.valid_until = valid_until
        self.created_at = datetime.now(timezone.utc) - timedelta(days=30)
        self.autopay_enabled = False
        
    @property
    def has_active_subscription(self):
        """Мокаем метод проверки активной подписки"""
        if not self.valid_until:
            return False
        return self.valid_until > datetime.now(timezone.utc)
    
    @property
    def subscription_days_remaining(self):
        """Мокаем метод подсчета оставшихся дней"""
        if not self.valid_until:
            return 0
        delta = self.valid_until - datetime.now(timezone.utc)
        return max(0, delta.days)

class VPNAccessControlSimpleTester:
    """Простой тестер VPN Access Control Service"""
    
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
    
    async def test_user_with_active_subscription(self):
        """Тест пользователя с активной подпиской"""
        try:
            # Создаем пользователя с активной подпиской
            user = MockUser(
                user_id=1,
                telegram_id=12345,
                has_active=True,
                valid_until=datetime.now(timezone.utc) + timedelta(days=15)
            )
            
            # Мокаем сессию БД
            mock_session = AsyncMock()
            
            # Создаем сервис
            service = VPNAccessControlService(mock_session)
            
            # Мокаем метод получения пользователя
            service._get_user_by_telegram_id = AsyncMock(return_value=user)
            
            # Тестируем проверку доступа
            result = await service.check_vpn_access(user.telegram_id)
            
            # Проверяем результат
            expected_access = True
            actual_access = result.get("has_access", False)
            success = actual_access == expected_access
            
            await self.log_test(
                "Active Subscription User",
                success,
                f"Access granted: {actual_access} (expected: {expected_access})",
                {
                    "has_access": actual_access,
                    "reason": result.get("reason"),
                    "days_remaining": result.get("days_remaining"),
                    "user_id": result.get("user_id")
                }
            )
            
            return result
            
        except Exception as e:
            await self.log_test(
                "Active Subscription User",
                False,
                f"Error testing active subscription user: {str(e)}"
            )
            return None
    
    async def test_user_with_expired_subscription(self):
        """Тест пользователя с истекшей подпиской"""
        try:
            # Создаем пользователя с истекшей подпиской
            user = MockUser(
                user_id=2,
                telegram_id=67890,
                has_active=False,
                valid_until=datetime.now(timezone.utc) - timedelta(days=5)
            )
            
            # Мокаем сессию БД
            mock_session = AsyncMock()
            
            # Создаем сервис
            service = VPNAccessControlService(mock_session)
            
            # Мокаем метод получения пользователя
            service._get_user_by_telegram_id = AsyncMock(return_value=user)
            
            # Тестируем проверку доступа
            result = await service.check_vpn_access(user.telegram_id)
            
            # Проверяем результат
            expected_access = False
            actual_access = result.get("has_access", True)  # Default True для проверки
            success = actual_access == expected_access
            
            await self.log_test(
                "Expired Subscription User",
                success,
                f"Access denied: {not actual_access} (expected: {not expected_access})",
                {
                    "has_access": actual_access,
                    "reason": result.get("reason"),
                    "days_remaining": result.get("days_remaining"),
                    "user_id": result.get("user_id")
                }
            )
            
            return result
            
        except Exception as e:
            await self.log_test(
                "Expired Subscription User",
                False,
                f"Error testing expired subscription user: {str(e)}"
            )
            return None
    
    async def test_nonexistent_user(self):
        """Тест несуществующего пользователя"""
        try:
            # Мокаем сессию БД
            mock_session = AsyncMock()
            
            # Создаем сервис
            service = VPNAccessControlService(mock_session)
            
            # Мокаем метод получения пользователя (возвращает None)
            service._get_user_by_telegram_id = AsyncMock(return_value=None)
            
            # Тестируем проверку доступа
            result = await service.check_vpn_access(99999)
            
            # Проверяем результат
            expected_access = False
            actual_access = result.get("has_access", True)
            expected_reason = "user_not_found"
            actual_reason = result.get("reason")
            
            success = (actual_access == expected_access) and (actual_reason == expected_reason)
            
            await self.log_test(
                "Nonexistent User",
                success,
                f"Access denied for nonexistent user: {not actual_access}",
                {
                    "has_access": actual_access,
                    "reason": actual_reason,
                    "expected_reason": expected_reason
                }
            )
            
            return result
            
        except Exception as e:
            await self.log_test(
                "Nonexistent User",
                False,
                f"Error testing nonexistent user: {str(e)}"
            )
            return None
    
    async def test_subscription_plans_retrieval(self):
        """Тест получения планов подписки"""
        try:
            # Мокаем сессию БД
            mock_session = AsyncMock()
            
            # Создаем сервис
            service = VPNAccessControlService(mock_session)
            
            # Тестируем получение планов
            result = await service.get_subscription_plans_for_user(12345)
            
            # Проверяем результат
            success = result.get("success", False)
            plans_count = len(result.get("plans", {}))
            
            await self.log_test(
                "Subscription Plans",
                success and plans_count > 0,
                f"Plans retrieved: {plans_count} plans available",
                {
                    "success": success,
                    "plans_count": plans_count,
                    "plans": list(result.get("plans", {}).keys())
                }
            )
            
            return result
            
        except Exception as e:
            await self.log_test(
                "Subscription Plans",
                False,
                f"Error retrieving subscription plans: {str(e)}"
            )
            return None
    
    async def run_all_tests(self):
        """Запуск всех тестов"""
        print("🧪 Starting VPN Access Control Simple Tests...")
        print("=" * 50)
        print("ℹ️  Testing VPN access control logic without database connection")
        print("=" * 50)
        
        # 1. Тест пользователя с активной подпиской
        await self.test_user_with_active_subscription()
        
        # 2. Тест пользователя с истекшей подпиской  
        await self.test_user_with_expired_subscription()
        
        # 3. Тест несуществующего пользователя
        await self.test_nonexistent_user()
        
        # 4. Тест получения планов подписки
        await self.test_subscription_plans_retrieval()
        
        # Выводим итоговый отчет
        await self.print_test_report()
    
    async def print_test_report(self):
        """Вывод итогового отчета тестирования"""
        print("\n" + "=" * 50)
        print("📊 TEST REPORT")
        print("=" * 50)
        
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
        
        # Рекомендации для дальнейшей работы
        print("\n💡 RECOMMENDATIONS:")
        if failed_tests == 0:
            print("✅ All logic tests passed! VPNAccessControlService core logic works correctly.")
            print("🚀 Ready to proceed to VPN handlers integration (Step 4)")
        else:
            print("⚠️  Some logic tests failed. Issues to address:")
            for result in self.test_results:
                if not result["success"]:
                    print(f"   - {result['test']}: {result['message']}")
        
        print("\n🔧 NEXT STEPS:")
        if failed_tests == 0:
            print("1. ✅ VPNAccessControlService core logic validated")
            print("2. 🚀 Ready to update VPN handlers with subscription check")
            print("3. 🚀 Ready to implement VPNKeyLifecycleService")
            print("4. 🚀 Continue with Step 4: Update VPN handlers")
        else:
            print("1. 🔧 Fix failing logic in VPNAccessControlService")
            print("2. 🔧 Review access control algorithms")
            print("3. ⏸️  Hold on handler integration until logic is correct")
        
        print("\n📝 NOTE:")
        print("   This test used mocked data. For full validation, test with real database when available.")

async def main():
    """Точка входа для тестирования"""
    tester = VPNAccessControlSimpleTester()
    await tester.run_all_tests()

if __name__ == "__main__":
    print("🚀 VPN Access Control Simple Testing Suite")
    print("=" * 50)
    print("ℹ️  Testing core logic without database dependencies")
    print("ℹ️  Using mocked user data for validation")
    print("=" * 50)
    
    asyncio.run(main()) 