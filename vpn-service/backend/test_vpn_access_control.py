"""
Тест VPNAccessControlService с реальными данными
Проверяем работу контроля доступа с пользователем ID=2 (истекшая подписка)
"""

import asyncio
import sys
import os
from datetime import datetime

# Добавляем путь к корневой директории
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from config.database import get_db
from services.vpn_access_control_service import VPNAccessControlService, check_user_vpn_access
from models.user import User
from sqlalchemy import select

class VPNAccessControlTester:
    """Класс для тестирования VPN Access Control Service"""
    
    def __init__(self):
        self.test_results = []
        self.test_user_id = 2  # Пользователь с истекшей подпиской
        
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
    
    async def test_get_user_details(self, db_session):
        """Тест получения детальной информации о пользователе"""
        try:
            # Получаем пользователя напрямую из БД для сравнения
            result = await db_session.execute(
                select(User).where(User.id == self.test_user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                await self.log_test(
                    "Get User Details",
                    False,
                    f"Test user with ID={self.test_user_id} not found in database"
                )
                return None
            
            await self.log_test(
                "Get User Details",
                True,
                f"Test user found",
                {
                    "user_id": user.id,
                    "telegram_id": user.telegram_id,
                    "subscription_status": user.subscription_status.value if user.subscription_status else "none",
                    "valid_until": user.valid_until.isoformat() if user.valid_until else None,
                    "has_active_subscription": user.has_active_subscription,
                    "created_at": user.created_at.isoformat() if user.created_at else None
                }
            )
            return user
            
        except Exception as e:
            await self.log_test(
                "Get User Details",
                False,
                f"Error getting user details: {str(e)}"
            )
            return None
    
    async def test_vpn_access_check(self, db_session, user):
        """Тест проверки VPN доступа"""
        try:
            service = VPNAccessControlService(db_session)
            access_result = await service.check_vpn_access(user.telegram_id)
            
            # Проверяем что доступ запрещен для пользователя с истекшей подпиской
            expected_access = user.has_active_subscription
            actual_access = access_result.get("has_access", False)
            
            success = actual_access == expected_access
            
            await self.log_test(
                "VPN Access Check",
                success,
                f"Access check result: {actual_access} (expected: {expected_access})",
                {
                    "has_access": actual_access,
                    "reason": access_result.get("reason"),
                    "message": access_result.get("message"),
                    "days_remaining": access_result.get("days_remaining"),
                    "user_id": access_result.get("user_id")
                }
            )
            
            return access_result
            
        except Exception as e:
            await self.log_test(
                "VPN Access Check",
                False,
                f"Error checking VPN access: {str(e)}"
            )
            return None
    
    async def test_subscription_plans_retrieval(self, db_session, user):
        """Тест получения планов подписки для пользователя без доступа"""
        try:
            service = VPNAccessControlService(db_session)
            plans_result = await service.get_subscription_plans_for_user(user.telegram_id)
            
            success = plans_result.get("success", False)
            plans_count = len(plans_result.get("plans", {}))
            
            await self.log_test(
                "Subscription Plans Retrieval",
                success,
                f"Plans retrieved successfully: {plans_count} plans available",
                {
                    "success": success,
                    "plans_count": plans_count,
                    "message": plans_result.get("message", "")[:100] + "..." if len(plans_result.get("message", "")) > 100 else plans_result.get("message", "")
                }
            )
            
            return plans_result
            
        except Exception as e:
            await self.log_test(
                "Subscription Plans Retrieval",
                False,
                f"Error retrieving subscription plans: {str(e)}"
            )
            return None
    
    async def test_helper_function(self, db_session, user):
        """Тест функции-хелпера check_user_vpn_access"""
        try:
            access_result = await check_user_vpn_access(db_session, user.telegram_id)
            
            success = isinstance(access_result, dict) and "has_access" in access_result
            
            await self.log_test(
                "Helper Function Test",
                success,
                f"Helper function works correctly",
                {
                    "has_access": access_result.get("has_access"),
                    "reason": access_result.get("reason"),
                    "user_id": access_result.get("user_id")
                }
            )
            
            return access_result
            
        except Exception as e:
            await self.log_test(
                "Helper Function Test",
                False,
                f"Error with helper function: {str(e)}"
            )
            return None
    
    async def test_subscription_details(self, db_session, user):
        """Тест получения детальной информации о подписке"""
        try:
            service = VPNAccessControlService(db_session)
            details = await service.check_user_subscription_details(user.telegram_id)
            
            success = details.get("found", False)
            
            await self.log_test(
                "Subscription Details",
                success,
                f"Subscription details retrieved",
                {
                    "found": details.get("found"),
                    "subscription_status": details.get("subscription_status"),
                    "valid_until_formatted": details.get("valid_until_formatted"),
                    "has_active_subscription": details.get("has_active_subscription"),
                    "days_remaining": details.get("days_remaining"),
                    "is_expired": details.get("is_expired"),
                    "autopay_enabled": details.get("autopay_enabled")
                }
            )
            
            return details
            
        except Exception as e:
            await self.log_test(
                "Subscription Details",
                False,
                f"Error getting subscription details: {str(e)}"
            )
            return None
    
    async def run_all_tests(self):
        """Запуск всех тестов"""
        print("🧪 Starting VPN Access Control Tests...")
        print("=" * 50)
        print(f"📋 Testing with user ID: {self.test_user_id} (should have expired subscription)")
        print("=" * 50)
        
        async for db_session in get_db():
            try:
                # 1. Получаем детали пользователя
                user = await self.test_get_user_details(db_session)
                if not user:
                    print("❌ Cannot proceed without test user")
                    return
                
                # 2. Проверяем VPN доступ
                access_result = await self.test_vpn_access_check(db_session, user)
                
                # 3. Проверяем получение планов подписки
                plans_result = await self.test_subscription_plans_retrieval(db_session, user)
                
                # 4. Тестируем функцию-хелпер
                helper_result = await self.test_helper_function(db_session, user)
                
                # 5. Тестируем детальную информацию о подписке
                details_result = await self.test_subscription_details(db_session, user)
                
                break  # Выходим из async generator
                
            except Exception as e:
                print(f"❌ Database connection error: {e}")
                return
        
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
            print("✅ All tests passed! VPNAccessControlService is working correctly.")
            print("🚀 Ready to proceed to next step: Update VPN handlers")
        else:
            print("⚠️  Some tests failed. Issues to address:")
            for result in self.test_results:
                if not result["success"]:
                    print(f"   - {result['test']}: {result['message']}")
        
        print("\n🔧 NEXT STEPS:")
        if failed_tests == 0:
            print("1. ✅ VPNAccessControlService implemented and tested")
            print("2. 🚀 Ready to update VPN handlers with subscription check")
            print("3. 🚀 Ready to implement VPNKeyLifecycleService")
            print("4. 🚀 Continue with main implementation (Step 4)")
        else:
            print("1. 🔧 Fix failing access control checks")
            print("2. 🔧 Verify database connections and user data")
            print("3. ⏸️  Hold on handler updates until access control is stable")

async def main():
    """Точка входа для тестирования"""
    tester = VPNAccessControlTester()
    await tester.run_all_tests()

if __name__ == "__main__":
    print("🚀 VPN Access Control Testing Suite")
    print("=" * 50)
    print("ℹ️  This test will check VPN access control with real user data")
    print("ℹ️  Testing with user ID=2 (should have expired subscription)")
    print("=" * 50)
    
    asyncio.run(main()) 