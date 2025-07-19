"""
Тесты API методов 3xUI панели для управления состоянием клиентов
Проверяем enable/disable функциональность перед реализацией основной задачи
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from typing import Dict, Any, Optional
import uuid

# Добавляем путь к корневой директории
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from services.x3ui_client import X3UIClient
from services.x3ui_panel_service import X3UIPanelService
from models.vpn_node import VPNNode

class X3UIAPITester:
    """Класс для тестирования API методов 3xUI панели"""
    
    def __init__(self):
        self.test_results = []
        self.test_clients = []  # Для очистки после тестов
        
    async def log_test(self, test_name: str, success: bool, message: str, details: Dict = None):
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
            print(f"   Details: {details}")
    
    async def create_test_x3ui_client(self) -> Optional[X3UIClient]:
        """Создание тестового клиента 3xUI"""
        try:
            # Используем тестовые данные - нужно будет настроить
            test_node = {
                "base_url": "https://your-test-panel.com",  # ЗАМЕНИТЬ НА РЕАЛЬНЫЙ URL
                "username": "admin",
                "password": "admin"
            }
            
            client = X3UIClient(
                base_url=test_node["base_url"],
                username=test_node["username"], 
                password=test_node["password"]
            )
            
            # Проверяем подключение
            login_success = await client._login()
            if not login_success:
                await self.log_test(
                    "X3UI Connection",
                    False,
                    "Failed to connect to X3UI panel",
                    {"url": test_node["base_url"]}
                )
                return None
                
            await self.log_test(
                "X3UI Connection", 
                True,
                "Successfully connected to X3UI panel"
            )
            return client
            
        except Exception as e:
            await self.log_test(
                "X3UI Connection",
                False,
                f"Error creating X3UI client: {str(e)}"
            )
            return None
    
    async def test_create_client(self, x3ui_client: X3UIClient) -> Optional[Dict]:
        """Тест создания клиента"""
        try:
            # Генерируем уникальные данные для тестового клиента
            test_email = f"test_enable_disable_{int(datetime.now().timestamp())}"
            test_client_id = str(uuid.uuid4())
            
            # Получаем первый доступный inbound
            inbounds = await x3ui_client.get_inbounds()
            if not inbounds:
                await self.log_test(
                    "Create Test Client",
                    False,
                    "No inbounds available for testing"
                )
                return None
            
            # Используем первый inbound для тестов
            test_inbound = inbounds[0]
            inbound_id = test_inbound.get("id")
            
            # Конфигурация тестового клиента
            client_config = {
                "telegram_id": 999999999,  # Тестовый ID
                "email": test_email,
                "client_id": test_client_id,
                "flow": "xtls-rprx-vision",
                "limit_ip": 2,
                "total_gb": 0,
                "expiry_time": 0
            }
            
            # Создаем клиента
            result = await x3ui_client.create_client(inbound_id, client_config)
            
            if result and result.get("success"):
                client_data = {
                    "email": test_email,
                    "client_id": test_client_id,
                    "inbound_id": inbound_id
                }
                self.test_clients.append(client_data)
                
                await self.log_test(
                    "Create Test Client",
                    True,
                    f"Test client created successfully",
                    client_data
                )
                return client_data
            else:
                await self.log_test(
                    "Create Test Client",
                    False,
                    "Failed to create test client",
                    {"result": result}
                )
                return None
                
        except Exception as e:
            await self.log_test(
                "Create Test Client",
                False,
                f"Error creating test client: {str(e)}"
            )
            return None
    
    async def test_get_client_info(self, x3ui_client: X3UIClient, client_email: str) -> Optional[Dict]:
        """Тест получения информации о клиенте"""
        try:
            # Получаем все inbound'ы
            inbounds = await x3ui_client.get_inbounds()
            
            for inbound in inbounds:
                settings = json.loads(inbound.get("settings", "{}"))
                clients = settings.get("clients", [])
                
                for client in clients:
                    if client.get("email") == client_email:
                        await self.log_test(
                            "Get Client Info",
                            True,
                            f"Client found with enable status: {client.get('enable')}",
                            {
                                "email": client_email,
                                "enable": client.get("enable"),
                                "inbound_id": inbound.get("id")
                            }
                        )
                        return client
            
            await self.log_test(
                "Get Client Info",
                False,
                f"Client not found: {client_email}"
            )
            return None
            
        except Exception as e:
            await self.log_test(
                "Get Client Info",
                False,
                f"Error getting client info: {str(e)}"
            )
            return None
    
    async def test_disable_client(self, x3ui_panel: X3UIPanelService, client_email: str) -> bool:
        """Тест отключения клиента"""
        try:
            result = await x3ui_panel.disable_client_by_email(client_email)
            
            await self.log_test(
                "Disable Client",
                result,
                f"Client disable result: {result}",
                {"email": client_email}
            )
            return result
            
        except Exception as e:
            await self.log_test(
                "Disable Client",
                False,
                f"Error disabling client: {str(e)}"
            )
            return False
    
    async def test_enable_client(self, x3ui_panel: X3UIPanelService, client_email: str) -> bool:
        """Тест включения клиента"""
        try:
            result = await x3ui_panel.enable_client_by_email(client_email)
            
            await self.log_test(
                "Enable Client",
                result,
                f"Client enable result: {result}",
                {"email": client_email}
            )
            return result
            
        except Exception as e:
            await self.log_test(
                "Enable Client",
                False,
                f"Error enabling client: {str(e)}"
            )
            return False
    
    async def test_enable_disable_cycle(self, x3ui_client: X3UIClient, x3ui_panel: X3UIPanelService, client_email: str):
        """Полный тест цикла включения/отключения клиента"""
        
        # 1. Проверяем начальное состояние (должно быть enable=True)
        initial_state = await self.test_get_client_info(x3ui_client, client_email)
        if not initial_state:
            return
        
        initial_enable = initial_state.get("enable", False)
        
        # 2. Отключаем клиента
        disable_success = await self.test_disable_client(x3ui_panel, client_email)
        
        if disable_success:
            # 3. Проверяем что клиент отключен
            await asyncio.sleep(1)  # Даем время на обновление
            disabled_state = await self.test_get_client_info(x3ui_client, client_email)
            
            if disabled_state and disabled_state.get("enable") == False:
                await self.log_test(
                    "Disable Verification",
                    True,
                    "Client successfully disabled"
                )
            else:
                await self.log_test(
                    "Disable Verification",
                    False,
                    f"Client still enabled after disable: {disabled_state}"
                )
        
        # 4. Пытаемся включить клиента
        enable_success = await self.test_enable_client(x3ui_panel, client_email)
        
        if enable_success:
            # 5. Проверяем что клиент включен
            await asyncio.sleep(1)  # Даем время на обновление
            enabled_state = await self.test_get_client_info(x3ui_client, client_email)
            
            if enabled_state and enabled_state.get("enable") == True:
                await self.log_test(
                    "Enable Verification",
                    True,
                    "Client successfully enabled"
                )
            else:
                await self.log_test(
                    "Enable Verification",
                    False,
                    f"Client still disabled after enable: {enabled_state}"
                )
        
        # Общий результат цикла
        cycle_success = disable_success and enable_success
        await self.log_test(
            "Enable/Disable Cycle",
            cycle_success,
            f"Cycle completed. Disable: {disable_success}, Enable: {enable_success}"
        )
    
    async def cleanup_test_clients(self, x3ui_client: X3UIClient):
        """Очистка тестовых клиентов"""
        for client_data in self.test_clients:
            try:
                email = client_data.get("email")
                success = await x3ui_client.delete_client_by_email(email)
                
                await self.log_test(
                    "Cleanup Test Client",
                    success,
                    f"Cleanup client {email}: {success}"
                )
                
            except Exception as e:
                await self.log_test(
                    "Cleanup Test Client",
                    False,
                    f"Error cleaning up client {client_data.get('email', 'unknown')}: {str(e)}"
                )
    
    async def run_all_tests(self):
        """Запуск всех тестов"""
        print("🧪 Starting X3UI API Tests...")
        print("=" * 50)
        
        # 1. Создаем клиент 3xUI
        x3ui_client = await self.create_test_x3ui_client()
        if not x3ui_client:
            print("❌ Cannot proceed without X3UI connection")
            return
        
        # 2. Создаем клиент панели
        x3ui_panel = X3UIPanelService()
        
        try:
            # 3. Создаем тестового клиента
            test_client_data = await self.test_create_client(x3ui_client)
            if not test_client_data:
                print("❌ Cannot proceed without test client")
                return
            
            client_email = test_client_data["email"]
            
            # 4. Запускаем цикл тестов enable/disable
            await self.test_enable_disable_cycle(x3ui_client, x3ui_panel, client_email)
            
        finally:
            # 5. Очищаем тестовые данные
            await self.cleanup_test_clients(x3ui_client)
            await x3ui_client.close()
        
        # 6. Выводим итоговый отчет
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
            print("✅ All tests passed! Ready to proceed with main implementation.")
        else:
            print("⚠️  Some tests failed. Issues to address:")
            for result in self.test_results:
                if not result["success"]:
                    print(f"   - {result['test']}: {result['message']}")
        
        print("\n🔧 NEXT STEPS:")
        if failed_tests == 0:
            print("1. ✅ enable_client_by_email method implemented and working")
            print("2. ✅ toggle functionality (_toggle_client_status) implemented") 
            print("3. 🚀 Ready to proceed to VPNAccessControlService implementation")
            print("4. 🚀 Ready to proceed to VPNKeyLifecycleService implementation")
        else:
            print("1. 🔧 Fix failing API methods before proceeding")
            print("2. 🔧 Test with real VPN nodes when available")
            print("3. ⏸️  Hold on VPNAccessControlService until API is stable")
            print("4. ⏸️  Hold on main implementation until tests pass")

async def main():
    """Точка входа для тестирования"""
    tester = X3UIAPITester()
    await tester.run_all_tests()

if __name__ == "__main__":
    print("🚀 X3UI API Testing Suite")
    print("=" * 50)
    print("⚠️  IMPORTANT: Configure real X3UI panel URL in create_test_x3ui_client()")
    print("⚠️  This test will create and delete test clients on the panel")
    print("=" * 50)
    
    # Запрашиваем подтверждение
    response = input("Continue with testing? (y/N): ")
    if response.lower() in ['y', 'yes']:
        asyncio.run(main())
    else:
        print("Testing cancelled.") 