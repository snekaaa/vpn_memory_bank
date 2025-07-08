"""
Система тестирования платежных провайдеров
Позволяет проверить подключение и конфигурацию различных платежных систем
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from models.payment_provider import PaymentProvider, PaymentProviderStatus
from .payment_processor import PaymentProcessorManager, PaymentRequest
from config.database import get_db_session


@dataclass
class TestResult:
    """Результат тестирования провайдера"""
    provider_id: int
    provider_name: str
    provider_type: str
    success: bool
    message: str
    duration: float
    tested_at: datetime
    details: Dict[str, Any] = None


@dataclass
class TestSuite:
    """Набор тестов для провайдера"""
    connection_test: bool = True
    config_validation: bool = True
    test_payment: bool = False  # Опционально - создание тестового платежа
    webhook_validation: bool = True


class PaymentProviderTester:
    """
    Класс для тестирования платежных провайдеров
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.processor_manager = PaymentProcessorManager()
    
    async def test_provider(
        self, 
        provider: PaymentProvider, 
        test_suite: TestSuite = None
    ) -> TestResult:
        """
        Тестирование одного провайдера
        
        Args:
            provider: Провайдер для тестирования
            test_suite: Набор тестов для выполнения
            
        Returns:
            TestResult: Результат тестирования
        """
        if test_suite is None:
            test_suite = TestSuite()
        
        start_time = datetime.now()
        details = {}
        overall_success = True
        messages = []
        
        try:
            # 1. Валидация конфигурации
            if test_suite.config_validation:
                config_valid, config_message = provider.validate_config()
                details["config_validation"] = {
                    "success": config_valid,
                    "message": config_message
                }
                
                if not config_valid:
                    overall_success = False
                    messages.append(f"Конфигурация: {config_message}")
            
            # 2. Тест подключения
            if test_suite.connection_test and overall_success:
                try:
                    processor = await self.processor_manager.get_processor(provider)
                    connection_success, connection_message = await processor.test_connection()
                    
                    details["connection_test"] = {
                        "success": connection_success,
                        "message": connection_message
                    }
                    
                    if not connection_success:
                        overall_success = False
                        messages.append(f"Подключение: {connection_message}")
                    else:
                        messages.append("Подключение успешно")
                        
                except Exception as e:
                    connection_error = f"Ошибка тестирования подключения: {str(e)}"
                    details["connection_test"] = {
                        "success": False,
                        "message": connection_error
                    }
                    overall_success = False
                    messages.append(connection_error)
            
            # 3. Тест создания платежа (опционально)
            if test_suite.test_payment and overall_success:
                test_payment_result = await self._test_payment_creation(provider)
                details["test_payment"] = test_payment_result
                
                if not test_payment_result["success"]:
                    messages.append(f"Тестовый платеж: {test_payment_result['message']}")
            
            # 4. Валидация webhook (если URL настроен)
            if test_suite.webhook_validation and provider.webhook_url:
                webhook_result = await self._test_webhook_config(provider)
                details["webhook_validation"] = webhook_result
                
                if not webhook_result["success"]:
                    messages.append(f"Webhook: {webhook_result['message']}")
            
            # Вычисляем продолжительность
            duration = (datetime.now() - start_time).total_seconds()
            
            # Формируем итоговое сообщение
            if overall_success:
                final_message = "Все тесты пройдены успешно"
            else:
                final_message = "; ".join(messages)
            
            # Обновляем статус тестирования в провайдере
            await self._update_provider_test_status(
                provider, overall_success, final_message
            )
            
            return TestResult(
                provider_id=provider.id,
                provider_name=provider.name,
                provider_type=provider.provider_type.value,
                success=overall_success,
                message=final_message,
                duration=duration,
                tested_at=start_time,
                details=details
            )
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            error_message = f"Критическая ошибка тестирования: {str(e)}"
            
            await self._update_provider_test_status(provider, False, error_message)
            
            return TestResult(
                provider_id=provider.id,
                provider_name=provider.name,
                provider_type=provider.provider_type.value,
                success=False,
                message=error_message,
                duration=duration,
                tested_at=start_time,
                details={"error": str(e)}
            )
    
    async def test_all_providers(
        self, 
        test_suite: TestSuite = None,
        active_only: bool = True
    ) -> List[TestResult]:
        """
        Тестирование всех провайдеров
        
        Args:
            test_suite: Набор тестов для выполнения
            active_only: Тестировать только активные провайдеры
            
        Returns:
            List[TestResult]: Результаты тестирования всех провайдеров
        """
        async with get_db_session() as db:
            # Получаем список провайдеров
            query = select(PaymentProvider)
            if active_only:
                query = query.where(PaymentProvider.is_active == True)
            
            result = await db.execute(query)
            providers = result.scalars().all()
        
        # Тестируем провайдеры параллельно
        tasks = []
        for provider in providers:
            task = self.test_provider(provider, test_suite)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Обрабатываем исключения
        test_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                provider = providers[i]
                test_results.append(TestResult(
                    provider_id=provider.id,
                    provider_name=provider.name,
                    provider_type=provider.provider_type.value,
                    success=False,
                    message=f"Исключение при тестировании: {str(result)}",
                    duration=0.0,
                    tested_at=datetime.now()
                ))
            else:
                test_results.append(result)
        
        return test_results
    
    async def test_provider_by_id(self, provider_id: int) -> Optional[TestResult]:
        """
        Тестирование провайдера по ID
        
        Args:
            provider_id: ID провайдера
            
        Returns:
            Optional[TestResult]: Результат тестирования или None
        """
        async with get_db_session() as db:
            result = await db.execute(
                select(PaymentProvider).where(PaymentProvider.id == provider_id)
            )
            provider = result.scalar_one_or_none()
        
        if not provider:
            return None
        
        return await self.test_provider(provider)
    
    async def _test_payment_creation(self, provider: PaymentProvider) -> Dict[str, Any]:
        """
        Тест создания платежа (без фактической оплаты)
        
        Args:
            provider: Провайдер для тестирования
            
        Returns:
            Dict[str, Any]: Результат теста
        """
        try:
            processor = await self.processor_manager.get_processor(provider)
            
            # Создаем тестовый запрос
            test_request = PaymentRequest(
                user_id=999999,  # Тестовый пользователь
                amount=1.00,     # Минимальная сумма
                description="Тестовый платеж для проверки конфигурации",
                return_url="https://example.com/success"
            )
            
            # Пытаемся создать платеж
            response = await processor.create_payment(test_request)
            
            if response.success:
                return {
                    "success": True,
                    "message": "Тестовый платеж создан успешно",
                    "payment_url": response.confirmation_url
                }
            else:
                return {
                    "success": False,
                    "message": response.error_message or "Неизвестная ошибка"
                }
                
        except Exception as e:
            return {
                "success": False,
                "message": f"Ошибка создания тестового платежа: {str(e)}"
            }
    
    async def _test_webhook_config(self, provider: PaymentProvider) -> Dict[str, Any]:
        """
        Тест конфигурации webhook
        
        Args:
            provider: Провайдер для тестирования
            
        Returns:
            Dict[str, Any]: Результат теста
        """
        try:
            webhook_url = provider.webhook_url
            
            if not webhook_url:
                return {
                    "success": False,
                    "message": "Webhook URL не настроен"
                }
            
            # Проверяем формат URL
            if not webhook_url.startswith(('http://', 'https://')):
                return {
                    "success": False,
                    "message": "Webhook URL должен начинаться с http:// или https://"
                }
            
            # В будущем здесь можно добавить проверку доступности URL
            return {
                "success": True,
                "message": "Webhook URL настроен корректно"
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Ошибка проверки webhook: {str(e)}"
            }
    
    async def _update_provider_test_status(
        self, 
        provider: PaymentProvider, 
        success: bool, 
        message: str
    ):
        """
        Обновление статуса тестирования в базе данных
        
        Args:
            provider: Провайдер
            success: Успешность тестирования
            message: Сообщение о результате
        """
        try:
            async with get_db_session() as db:
                # Обновляем статус тестирования
                status = "success" if success else "error"
                
                await db.execute(
                    update(PaymentProvider)
                    .where(PaymentProvider.id == provider.id)
                    .values(
                        last_test_at=datetime.now(),
                        last_test_status=status,
                        last_test_message=message[:1000]  # Ограничиваем длину сообщения
                    )
                )
                
                await db.commit()
                
        except Exception as e:
            self.logger.error(f"Error updating test status: {e}")
    
    async def get_test_summary(self) -> Dict[str, Any]:
        """
        Получение сводки по тестированию всех провайдеров
        
        Returns:
            Dict[str, Any]: Сводка по тестированию
        """
        async with get_db_session() as db:
            result = await db.execute(select(PaymentProvider))
            providers = result.scalars().all()
        
        total_providers = len(providers)
        active_providers = len([p for p in providers if p.is_active])
        tested_providers = len([p for p in providers if p.last_test_at])
        successful_tests = len([
            p for p in providers 
            if p.last_test_status == "success"
        ])
        
        return {
            "total_providers": total_providers,
            "active_providers": active_providers,
            "tested_providers": tested_providers,
            "successful_tests": successful_tests,
            "test_success_rate": (
                successful_tests / tested_providers * 100 
                if tested_providers > 0 else 0
            )
        }


# Глобальный экземпляр тестера
payment_provider_tester = PaymentProviderTester() 