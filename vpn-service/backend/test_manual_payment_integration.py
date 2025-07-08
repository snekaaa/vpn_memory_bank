#!/usr/bin/env python3
"""
Интеграционный тест для Manual Payment Management System

Проверяет основную функциональность:
1. Создание ручного платежа
2. Изменение статуса платежа  
3. Автоматическое продление подписки
4. Создание триального платежа при регистрации
"""

import asyncio
import sys
import os
from datetime import datetime, timezone

# Добавляем корневую директорию в путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.ext.asyncio import AsyncSession
from config.database import get_db
from models.user import User, UserSubscriptionStatus
from models.payment import Payment, PaymentStatus, PaymentMethod
from services.payment_management_service import get_payment_management_service
from services.trial_automation_service import get_trial_automation_service
from services.integration_service import IntegrationService


async def test_manual_payment_creation():
    """Тест создания ручного платежа"""
    print("\n=== Тест создания ручного платежа ===")
    
    async for db in get_db():
        try:
            # Создаем тестового пользователя
            test_user = User(
                telegram_id=999999999,
                username="test_user",
                first_name="Test",
                language_code="ru",
                is_active=True,
                subscription_status=UserSubscriptionStatus.inactive
            )
            
            db.add(test_user)
            await db.commit()
            await db.refresh(test_user)
            print(f"✓ Создан тестовый пользователь: ID {test_user.id}")
            
            # Создаем ручной платеж
            payment_service = get_payment_management_service(db)
            
            payment = await payment_service.create_manual_payment(
                user_id=test_user.id,
                amount=100.0,
                description="Тестовый ручной платеж - месячная подписка",
                payment_method=PaymentMethod.manual_admin,
                admin_user="test_admin"
            )
            
            print(f"✓ Создан ручной платеж: ID {payment.id}, сумма {payment.amount}₽")
            assert payment.status == PaymentStatus.PENDING
            assert payment.amount == 100.0
            
            # Изменяем статус на SUCCEEDED
            updated_payment = await payment_service.update_payment_status(
                payment_id=payment.id,
                new_status=PaymentStatus.SUCCEEDED,
                admin_user="test_admin",
                reason="Test payment confirmation"
            )
            
            print(f"✓ Статус платежа изменен на: {updated_payment.status.value}")
            assert updated_payment.status == PaymentStatus.SUCCEEDED
            assert updated_payment.paid_at is not None
            
            # Проверяем продление подписки
            await db.refresh(test_user)
            print(f"✓ Подписка пользователя продлена до: {test_user.valid_until}")
            assert test_user.subscription_status == UserSubscriptionStatus.active
            assert test_user.valid_until is not None
            
            return True
            
        except Exception as e:
            print(f"✗ Ошибка в тесте создания платежа: {e}")
            return False
        finally:
            # Очистка
            await db.rollback()
            break


async def test_trial_automation():
    """Тест автоматического создания триального платежа"""
    print("\n=== Тест автоматического триального платежа ===")
    
    async for db in get_db():
        try:
            # Создаем сервисы
            payment_service = get_payment_management_service(db)
            trial_service = await get_trial_automation_service(payment_service)
            
            # Создаем нового пользователя
            new_user = User(
                telegram_id=888888888,
                username="trial_test_user",
                first_name="Trial Test",
                language_code="ru",
                is_active=True,
                subscription_status=UserSubscriptionStatus.inactive
            )
            
            db.add(new_user)
            await db.commit()
            await db.refresh(new_user)
            print(f"✓ Создан новый пользователь: ID {new_user.id}")
            
            # Создаем триальный платеж
            trial_payment = await trial_service.create_trial_for_new_user(new_user, db)
            
            if trial_payment:
                print(f"✓ Создан триальный платеж: ID {trial_payment.id}")
                print(f"  - Сумма: {trial_payment.amount}₽")
                print(f"  - Статус: {trial_payment.status.value}")
                print(f"  - Метод: {trial_payment.payment_method.value}")
                print(f"  - Описание: {trial_payment.description}")
                
                assert trial_payment.amount == 0.0
                assert trial_payment.status == PaymentStatus.SUCCEEDED
                assert trial_payment.payment_method == PaymentMethod.auto_trial
                
                # Проверяем что подписка пользователя активирована
                await db.refresh(new_user)
                print(f"✓ Подписка пользователя активирована до: {new_user.valid_until}")
                assert new_user.subscription_status == UserSubscriptionStatus.active
                
                return True
            else:
                print("✗ Триальный платеж не был создан")
                return False
                
        except Exception as e:
            print(f"✗ Ошибка в тесте триального платежа: {e}")
            return False
        finally:
            # Очистка
            await db.rollback()
            break


async def test_integration_service_with_trial():
    """Тест полного цикла регистрации пользователя с триальным платежом"""
    print("\n=== Тест полного цикла регистрации с триалом ===")
    
    try:
        integration_service = IntegrationService()
        
        # Данные нового пользователя
        user_data = {
            "username": "integration_test",
            "first_name": "Integration",
            "last_name": "Test",
            "language_code": "ru"
        }
        
        # Создаем пользователя с подпиской
        result = await integration_service.create_user_with_subscription(
            telegram_id=777777777,
            user_data=user_data
        )
        
        print(f"✓ Результат регистрации: {result['success']}")
        print(f"  - User ID: {result['user_id']}")
        print(f"  - Message: {result['message']}")
        
        if result.get('trial_payment'):
            trial_info = result['trial_payment']
            print(f"  - Trial Payment ID: {trial_info['id']}")
            print(f"  - Trial Amount: {trial_info['amount']}₽")
            print(f"  - Trial Status: {trial_info['status']}")
            print(f"  - Trial Description: {trial_info['description']}")
        
        assert result['success'] is True
        assert result['user_id'] is not None
        assert result.get('trial_payment') is not None
        
        return True
        
    except Exception as e:
        print(f"✗ Ошибка в тесте интеграционного сервиса: {e}")
        return False


async def main():
    """Основная функция тестирования"""
    print("🚀 Запуск интеграционных тестов Manual Payment Management System")
    
    tests = [
        ("Manual Payment Creation", test_manual_payment_creation),
        ("Trial Automation", test_trial_automation),
        ("Integration Service with Trial", test_integration_service_with_trial)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{'='*60}")
        print(f"Запуск теста: {test_name}")
        print('='*60)
        
        try:
            result = await test_func()
            results.append((test_name, result))
            
            if result:
                print(f"✅ ТЕСТ ПРОЙДЕН: {test_name}")
            else:
                print(f"❌ ТЕСТ НЕ ПРОЙДЕН: {test_name}")
                
        except Exception as e:
            print(f"💥 ОШИБКА ТЕСТА: {test_name} - {e}")
            results.append((test_name, False))
    
    # Итоговая статистика
    print(f"\n{'='*60}")
    print("📊 ИТОГОВЫЕ РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ")
    print('='*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ ПРОЙДЕН" if result else "❌ НЕ ПРОЙДЕН"
        print(f"{status}: {test_name}")
    
    print(f"\nПройдено тестов: {passed}/{total}")
    
    if passed == total:
        print("🎉 ВСЕ ТЕСТЫ УСПЕШНО ПРОЙДЕНЫ!")
        print("✅ Manual Payment Management System готов к использованию")
    else:
        print("⚠️ НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОЙДЕНЫ")
        print("❗ Требуется дополнительная отладка")
    
    return passed == total


if __name__ == "__main__":
    asyncio.run(main()) 