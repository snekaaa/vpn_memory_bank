"""
Обработчики платежей для Telegram бота
"""

import logging
from typing import Dict, Any
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import json

from keyboards.main_menu import (
    get_main_menu, 
    get_back_to_menu_keyboard, 
    get_user_subscription_days,
    get_subscription_keyboard_without_cancel,
    get_payment_confirmation_keyboard_back_only,
    get_existing_payment_keyboard,
    get_subscription_keyboard_with_autopay,
    get_subscription_keyboard_with_autopay_toggle,
    send_main_menu
)
from services.plans_api_client import plans_api_client
# from api_client import api_client  # Отключен - используем локальный SimpleAPIClient
import aiohttp
import structlog

logger = structlog.get_logger(__name__)

router = Router()

class PaymentStates(StatesGroup):
    """Состояния для процесса оплаты"""
    selecting_plan = State()
    confirming_payment = State()
    processing_payment = State()

async def get_subscription_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру выбора подписки (с кнопкой отмены - для обратной совместимости)"""
    buttons = []
    
    try:
        # Получаем планы из API
        subscription_plans = await plans_api_client.get_plans()
        
        for plan_id, plan in subscription_plans.items():
            discount_text = f" (-{plan['discount']})" if plan.get('discount') else ""
            button_text = f"{plan['name']} - {plan['price']}₽{discount_text}"
            buttons.append([InlineKeyboardButton(
                text=button_text,
                callback_data=f"pay:{plan_id}"
            )])
    except Exception as e:
        logger.error(f"Error loading subscription plans: {e}")
        # В случае ошибки показываем кнопку "Попробовать позже"
        buttons.append([InlineKeyboardButton(
            text="⚠️ Планы временно недоступны",
            callback_data="plans_unavailable"
        )])
    
    buttons.append([InlineKeyboardButton(
        text="❌ Отмена",
        callback_data="cancel_payment"
    )])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_payment_confirmation_keyboard(plan_id: str) -> InlineKeyboardMarkup:
    """Создает клавиатуру подтверждения платежа (с кнопкой отмены - для обратной совместимости)"""
    buttons = [
        [InlineKeyboardButton(
            text="💳 Оплатить",
            callback_data=f"confirm_pay:{plan_id}"
        )],
        [InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data="select_subscription"
        )],
        [InlineKeyboardButton(
            text="❌ Отмена",
            callback_data="cancel_payment"
        )]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

async def show_active_subscription_info(message: Message, subscription_info: dict, telegram_id: int):
    """Показать информацию об активной подписке с управлением автоплатежом"""
    
    end_date = subscription_info.get('end_date')
    days_remaining = subscription_info.get('days_remaining', 0)
    
    # Получаем актуальную настройку автоплатежа от пользователя
    api_client = SimpleAPIClient()
    auto_payment_info = await api_client.get_user_auto_payment_info(telegram_id)
    autopay_enabled = auto_payment_info.get('enabled', True)
    
    # Статус автоплатежа для отображения
    autopay_status = "✅ Включен" if autopay_enabled else "❌ Отключен"
    
    text = (
        f"💳 **Ваша подписка действует до {end_date}**\n\n"
        f"⏰ **Осталось:** {days_remaining} дн.\n\n"
        f"⚡ **Автопродление:** {autopay_status}\n\n"
        f"💡 **Докупить подписку:**"
    )
    
    # Используем новую клавиатуру с управлением автопродления
    keyboard = await get_subscription_keyboard_with_autopay_toggle(autopay_enabled)
    
    await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")


async def show_active_subscription_info_with_autopay_state(message: Message, subscription_info: dict, telegram_id: int, autopay_enabled: bool):
    """Показать информацию об активной подписке с заданным состоянием автоплатежа"""
    
    end_date = subscription_info.get('end_date')
    days_remaining = subscription_info.get('days_remaining', 0)
    
    # Статус автоплатежа для отображения
    autopay_status = "✅ Включен" if autopay_enabled else "❌ Отключен"
    
    text = (
        f"💳 **Ваша подписка действует до {end_date}**\n\n"
        f"⏰ **Осталось:** {days_remaining} дн.\n\n"
        f"⚡ **Автопродление:** {autopay_status}\n\n"
        f"💡 **Докупить подписку:**"
    )
    
    # Используем новую клавиатуру с управлением автопродления
    keyboard = await get_subscription_keyboard_with_autopay_toggle(autopay_enabled)
    
    try:
        await message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error updating message: {e}")
        # Если не удалось отредактировать, отправляем новое сообщение
        await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")


async def show_subscription_plans_selection(message: Message, state: FSMContext):
    """Показать выбор планов подписки для пользователей без активной подписки"""
    
    await state.set_state(PaymentStates.selecting_plan)
    
    text = (
        f"💳 **Выберите план подписки:**\n\n"
        f"📊 Доступные тарифы для подключения VPN сервиса"
    )
    
    # Для новых пользователей по умолчанию автопродление включено
    keyboard = await get_subscription_keyboard_with_autopay_toggle(autopay_enabled=True)
    
    await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")

@router.message(F.text.startswith("💳 Подписка"))
async def show_subscription_plans(message: Message, state: FSMContext):
    """Показать информацию о подписке или планы для покупки"""
    try:
        telegram_id = message.from_user.id
        api_client = SimpleAPIClient()
        
        # 1. СНАЧАЛА проверяем статус подписки по valid_until
        subscription_info = await api_client.get_user_subscription_status(telegram_id)
        
        if subscription_info and subscription_info.get('success'):
            days_remaining = subscription_info.get('days_remaining', 0)
            
            if days_remaining > 0:
                # АКТИВНАЯ ПОДПИСКА - показать информацию + управление автоплатежом
                await show_active_subscription_info(message, subscription_info, telegram_id)
                return
        
        # Проверяем есть ли у пользователя неоплаченные платежи
        pending_payments_response = await SimpleAPIClient().get_user_pending_payments(telegram_id)
        
        if pending_payments_response and pending_payments_response.get('pending_payments'):
            # Есть неоплаченные платежи - показываем их
            payments = pending_payments_response['pending_payments']
            latest_payment = payments[0]  # Берем самый последний
            
            payment_id = latest_payment['id']
            amount = latest_payment['amount']
            description = latest_payment['description']
            payment_url = latest_payment['confirmation_url']
            payment_metadata = latest_payment.get('payment_metadata', {})
            
            # Получаем информацию о плане для детализации
            service_name = "VPN Подписка"
            service_description = description or "Подписка на VPN сервис"
            
            if payment_metadata and payment_metadata.get('subscription_type'):
                try:
                    plan = await plans_api_client.get_plan(payment_metadata['subscription_type'])
                    if plan:
                        service_name = plan['name']
                        service_description = plan['description']
                except Exception as e:
                    logger.error(f"Error getting plan details: {e}")
            
            text = (
                f"💳 **Счет на оплату**\n\n"
                f"🎯 **Услуга:** {service_name}\n"
                f"📋 **Описание:** {service_description}\n\n"
                f"💰 **Сумма:** {amount}₽\n"
                f"🆔 **ID платежа:** {payment_id}\n\n"
                f"👆 Нажмите кнопку для перехода к оплате.\n"
                f"После оплаты вернитесь в бот и проверьте статус."
            )
            
            if payment_url:
                keyboard = get_existing_payment_keyboard(payment_id, payment_url)
            else:
                # Если URL нет, показываем только проверку статуса и отмену
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text="🔄 Проверить статус",
                        callback_data=f"check_payment:{payment_id}"
                    )],
                    [InlineKeyboardButton(
                        text="❌ Отменить счет",
                        callback_data="cancel_payment"
                    )]
                ])
            
            await message.answer(
                text,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            
            # Устанавливаем состояние для отслеживания текущего платежа
            await state.update_data(payment_id=payment_id)
            await state.set_state(PaymentStates.processing_payment)
            return
        
        # 2. НЕТ АКТИВНОЙ ПОДПИСКИ - показать планы
        await show_subscription_plans_selection(message, state)
        
    except Exception as e:
        logger.error(f"Error showing subscription plans: {e}")
        await send_main_menu(message, message.from_user.id, "❌ Произошла ошибка при загрузке информации о подписке")

@router.callback_query(F.data.startswith("pay:"))
async def handle_plan_selection(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора плана подписки"""
    try:
        plan_id = callback.data.split(":")[1]
        
        # Получаем план из API
        plan = await plans_api_client.get_plan(plan_id)
        
        if not plan:
            await callback.answer("❌ Неверный план подписки или планы недоступны")
            return
        
        await state.update_data(selected_plan=plan_id)
        await state.set_state(PaymentStates.confirming_payment)
        
        discount_text = f"\n🎉 **Скидка: {plan['discount']}**" if plan.get('discount') else ""
        
        text = (
            f"📋 **Подтверждение заказа:**\n\n"
            f"🎯 План: {plan['name']}\n"
            f"💰 Цена: {plan['price']}₽\n"
            f"⏱ Срок: {plan['duration']}"
            f"{discount_text}\n\n"
            f"📝 Описание: {plan['description']}\n\n"
            f"Подтвердите оплату для продолжения"
        )
        
        await callback.message.edit_text(
            text,
            reply_markup=get_payment_confirmation_keyboard_back_only(plan_id),
            parse_mode="Markdown"
        )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error handling plan selection: {e}")
        await callback.answer("❌ Произошла ошибка")

@router.callback_query(F.data.startswith("confirm_pay:"))
async def handle_payment_confirmation(callback: CallbackQuery, state: FSMContext):
    """Обработка подтверждения платежа"""
    try:
        plan_id = callback.data.split(":")[1]
        user_id = callback.from_user.id
        
        # Обновляем сообщение о создании платежа
        await callback.message.edit_text(
            "⏳ Создание платежа...",
            reply_markup=None
        )
        
        api_client = SimpleAPIClient()
        
        # Получаем user_id из базы данных
        user_data = await api_client.get_user_by_telegram_id(user_id)
        if not user_data:
            await callback.message.edit_text(
                "❌ Пользователь не найден. Пожалуйста, начните с команды /start",
                reply_markup=get_back_to_menu_keyboard()
            )
            return
        
        # Получаем информацию о плане для названия услуги
        plan = await plans_api_client.get_plan(plan_id)
        if not plan:
            await callback.message.edit_text(
                "❌ План подписки не найден",
                reply_markup=get_back_to_menu_keyboard()
            )
            return
        
        # Получаем список активных провайдеров и выбираем первый попавшийся
        active_providers = await api_client.get_active_payment_providers()
        
        if not active_providers or not active_providers.get('providers'):
            await callback.message.edit_text(
                "❌ Нет доступных способов оплаты. Обратитесь в поддержку.",
                reply_markup=get_back_to_menu_keyboard()
            )
            return
        
        # Выбираем первый активный провайдер
        selected_provider = active_providers['providers'][0]
        provider_type = selected_provider['provider_type']
        
        logger.info(f"🎯 Выбранный провайдер для платежа: {selected_provider['name']} ({provider_type})")
        
        # Создаем платеж с выбранным провайдером
        payment_data = {
            "user_id": user_data["id"],
            "subscription_type": plan_id,
            "service_name": plan["name"],  # Добавляем название услуги
            "user_email": f"user_{user_id}@telegram.local",
            "success_url": f"https://t.me/vpn_bezlagov_test_bot?start=payment_success",
            "fail_url": f"https://t.me/vpn_bezlagov_test_bot?start=payment_fail",
            "provider_type": provider_type  # Указываем выбранный провайдер
        }
        
        payment_result = await api_client.create_payment(payment_data)
        
        if payment_result.get("status") == "success":
            payment_url = payment_result["payment_url"]
            payment_id = payment_result["payment_id"]
            amount = payment_result["amount"]
            
            # Сохраняем ID платежа в состоянии
            await state.update_data(payment_id=payment_id)
            
            # Создаем клавиатуру с кнопкой оплаты
            payment_keyboard = get_existing_payment_keyboard(payment_id, payment_url)
            
            text = (
                f"💳 **Счет на оплату**\n\n"
                f"🎯 **Услуга:** {plan['name']}\n"
                f"📋 **Описание:** {plan['description']}\n\n"
                f"💰 **Сумма:** {amount}₽\n"
                f"🆔 **ID платежа:** {payment_id}\n"
                f"💳 **Способ оплаты:** {selected_provider['name']}\n\n"
                f"👆 Нажмите кнопку для перехода к оплате.\n"
                f"После оплаты вернитесь в бот и проверьте статус."
            )
            
            await callback.message.edit_text(
                text,
                reply_markup=payment_keyboard,
                parse_mode="Markdown"
            )
            
        else:
            error_message = "Неизвестная ошибка"
            if payment_result:
                # Пытаемся извлечь осмысленное сообщение
                detail = payment_result.get('detail')
                if isinstance(detail, dict):
                    # Если detail - это словарь (например, от FastAPI), ищем в нем 'detail'
                    error_message = detail.get('detail', str(detail))
                elif detail:
                    # Если detail - это просто строка
                    error_message = str(detail)
                else:
                    # Фоллбэк на поле 'error'
                    error_message = payment_result.get('error', 'Неизвестная ошибка')

            await callback.message.edit_text(
                f"❌ Ошибка создания платежа: {error_message}",
                reply_markup=get_back_to_menu_keyboard()
            )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error handling payment confirmation: {e}")
        await callback.message.edit_text(
            "❌ Произошла ошибка при создании платежа",
            reply_markup=get_back_to_menu_keyboard()
        )
        await callback.answer()

@router.callback_query(F.data.startswith("check_payment:"))
async def handle_payment_check(callback: CallbackQuery, state: FSMContext):
    """Проверка статуса платежа"""
    try:
        payment_id = callback.data.split(":")[1]
        
        # Обновляем сообщение о проверке
        await callback.message.edit_text(
            "⏳ Проверка статуса платежа...",
            reply_markup=None
        )
        
        # Проверяем статус через API
        api_client = SimpleAPIClient()
        payment_status = await api_client.get_payment_status(payment_id)
        
        if payment_status.get("status") == "success":
            status = payment_status["payment_status"]
            amount = payment_status["amount"]
            
            if status == "SUCCEEDED":
                # Получаем информацию об услуге для успешного платежа
                service_info = ""
                try:
                    if payment_status.get("payment_metadata") and payment_status["payment_metadata"].get("subscription_type"):
                        plan = await plans_api_client.get_plan(payment_status["payment_metadata"]["subscription_type"])
                        if plan:
                            service_info = f"🎯 **Услуга:** {plan['name']}\n📋 **Описание:** {plan['description']}\n\n"
                except Exception as e:
                    logger.error(f"Error getting plan details for success message: {e}")
                
                # Платеж успешен
                await callback.message.edit_text(
                    f"✅ **Платеж успешно завершен!**\n\n"
                    f"{service_info}"
                    f"💰 **Сумма:** {amount}₽\n"
                    f"🆔 **ID:** {payment_id}\n\n"
                    f"🎉 Ваша подписка активирована!\n"
                    f"Теперь вы можете получить VPN ключи.",
                    reply_markup=get_back_to_menu_keyboard(),
                    parse_mode="Markdown"
                )
                
                # Очищаем состояние
                await state.clear()
                
            elif status == "FAILED":
                # Получаем информацию об услуге для неуспешного платежа
                service_info = ""
                try:
                    if payment_status.get("payment_metadata") and payment_status["payment_metadata"].get("subscription_type"):
                        plan = await plans_api_client.get_plan(payment_status["payment_metadata"]["subscription_type"])
                        if plan:
                            service_info = f"🎯 **Услуга:** {plan['name']}\n\n"
                except Exception as e:
                    logger.error(f"Error getting plan details for failed message: {e}")
                
                # Платеж не удался
                await callback.message.edit_text(
                    f"❌ **Платеж не удался**\n\n"
                    f"{service_info}"
                    f"🆔 **ID:** {payment_id}\n\n"
                    f"Попробуйте создать новый платеж или обратитесь в поддержку.",
                    reply_markup=get_back_to_menu_keyboard(),
                    parse_mode="Markdown"
                )
                
                await state.clear()
                
            else:
                # Платеж еще в процессе - получаем URL из ответа если есть
                payment_url = payment_status.get("confirmation_url", "")
                if payment_url:
                    payment_keyboard = get_existing_payment_keyboard(payment_id, payment_url)
                else:
                    payment_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(
                            text="🔄 Проверить еще раз",
                            callback_data=f"check_payment:{payment_id}"
                        )],
                        [InlineKeyboardButton(
                            text="❌ Отменить счет",
                            callback_data="cancel_payment"
                        )]
                    ])
                
                # Получаем дополнительные данные о платеже для отображения
                service_info = ""
                try:
                    if payment_status.get("payment_metadata") and payment_status["payment_metadata"].get("subscription_type"):
                        plan = await plans_api_client.get_plan(payment_status["payment_metadata"]["subscription_type"])
                        if plan:
                            service_info = f"🎯 **Услуга:** {plan['name']}\n📋 **Описание:** {plan['description']}\n\n"
                except Exception as e:
                    logger.error(f"Error getting plan details for payment check: {e}")
                
                await callback.message.edit_text(
                    f"⏳ **Платеж в обработке**\n\n"
                    f"{service_info}"
                    f"💰 **Сумма:** {amount}₽\n"
                    f"🆔 **ID:** {payment_id}\n"
                    f"📊 **Статус:** {status}\n\n"
                    f"Пожалуйста, подождите или проверьте статус позже.",
                    reply_markup=payment_keyboard,
                    parse_mode="Markdown"
                )
        else:
            await callback.message.edit_text(
                f"❌ Ошибка проверки платежа: {payment_status.get('message', 'Неизвестная ошибка')}",
                reply_markup=get_back_to_menu_keyboard()
            )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error checking payment status: {e}")
        await callback.message.edit_text(
            "❌ Произошла ошибка при проверке платежа",
            reply_markup=get_back_to_menu_keyboard()
        )
        await callback.answer()

@router.callback_query(F.data == "select_subscription")
async def back_to_subscription_selection(callback: CallbackQuery, state: FSMContext):
    """Возврат к выбору подписки"""
    try:
        await state.set_state(PaymentStates.selecting_plan)
        
        # Получаем актуальные планы из API
        try:
            subscription_plans = await plans_api_client.get_plans()
            
            text_lines = ["🎯 **Выберите план подписки:**\n"]
            for plan_id, plan in subscription_plans.items():
                discount_text = f" **-{plan['discount']}**" if plan.get('discount') else ""
                text_lines.append(f"• {plan['name']} - {plan['price']}₽ ({plan['duration']}){discount_text}")
            
            text_lines.append("\n💡 Чем дольше подписка, тем больше скидка!")
            text = "\n".join(text_lines)
            
        except Exception as e:
            logger.error(f"Error loading plans for text: {e}")
            text = (
                "🎯 **Выберите план подписки:**\n\n"
                "⚠️ Загрузка актуальных цен...\n\n"
                "💡 Чем дольше подписка, тем больше скидка!"
            )
        
        keyboard = await get_subscription_keyboard_without_cancel()
        
        await callback.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error going back to subscription selection: {e}")
        await callback.answer("❌ Произошла ошибка")

@router.callback_query(F.data == "plans_unavailable")
async def handle_plans_unavailable(callback: CallbackQuery, state: FSMContext):
    """Обработка недоступности планов"""
    try:
        await callback.answer("⚠️ Планы временно недоступны. Попробуйте позже.")
        
        await callback.message.edit_text(
            "⚠️ **Планы подписок временно недоступны**\n\n"
            "Возможные причины:\n"
            "• Технические работы\n"
            "• Обновление системы\n\n"
            "Пожалуйста, попробуйте позже или обратитесь в поддержку.",
            reply_markup=get_back_to_menu_keyboard(),
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Error handling plans unavailable: {e}")
        await callback.answer("❌ Произошла ошибка")

@router.callback_query(F.data == "cancel_payment")
async def cancel_payment(callback: CallbackQuery, state: FSMContext):
    """Отмена платежа и всех неоплаченных счетов"""
    try:
        telegram_id = callback.from_user.id
        
        # Отменяем все неоплаченные платежи пользователя
        cancel_result = await SimpleAPIClient().cancel_user_pending_payments(telegram_id)
        
        if cancel_result and cancel_result.get('status') == 'success':
            logger.info(f"Successfully cancelled pending payments for user {telegram_id}")
        else:
            logger.warning(f"Failed to cancel pending payments for user {telegram_id}")
        
        await state.clear()
        
        # Получаем актуальные планы из API для отображения после отмены
        try:
            subscription_plans = await plans_api_client.get_plans()
            
            text_lines = ["❌ **Оплата отменена**\n"]
            text_lines.append("🎯 **Выберите план подписки:**\n")
            for plan_id, plan in subscription_plans.items():
                discount_text = f" **-{plan['discount']}**" if plan.get('discount') else ""
                text_lines.append(f"• {plan['name']} - {plan['price']}₽ ({plan['duration']}){discount_text}")
            
            text_lines.append("\n💡 Чем дольше подписка, тем больше скидка!")
            text = "\n".join(text_lines)
            
        except Exception as e:
            logger.error(f"Error loading plans after cancel: {e}")
            text = (
                "❌ **Оплата отменена**\n\n"
                "🎯 **Выберите план подписки:**\n\n"
                "⚠️ Загрузка актуальных цен...\n\n"
                "💡 Чем дольше подписка, тем больше скидка!"
            )
        
        keyboard = await get_subscription_keyboard_without_cancel()
        
        await callback.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        
        await state.set_state(PaymentStates.selecting_plan)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error canceling payment: {e}")
        await callback.answer("❌ Произошла ошибка")


@router.callback_query(F.data == "back_to_main_menu")
async def back_to_main_menu(callback: CallbackQuery, state: FSMContext):
    """Возврат в главное меню"""
    try:
        await state.clear()
        await callback.message.delete()
        await send_main_menu(callback.message, callback.from_user.id)
        await callback.answer()
    except Exception as e:
        logger.error(f"Error returning to main menu: {e}")
        await callback.answer("❌ Произошла ошибка")

@router.callback_query(F.data.startswith("pay_autopay:"))
async def handle_autopay_payment(callback: CallbackQuery, state: FSMContext):
    """Обработка оплаты с автоплатежом"""
    try:
        plan_id = callback.data.split(":")[1]
        user_id = callback.from_user.id
        
        # Обновляем сообщение о создании платежа
        await callback.message.edit_text(
            "⏳ Создание платежа с автоплатежом...",
            reply_markup=None
        )
        
        api_client = SimpleAPIClient()
        
        # Получаем user_id из базы данных
        user_data = await api_client.get_user_by_telegram_id(user_id)
        if not user_data:
            await callback.message.edit_text(
                "❌ Пользователь не найден. Пожалуйста, начните с команды /start",
                reply_markup=get_back_to_menu_keyboard()
            )
            return
        
        # Получаем информацию о плане для названия услуги
        plan = await plans_api_client.get_plan(plan_id)
        if not plan:
            await callback.message.edit_text(
                "❌ План подписки не найден",
                reply_markup=get_back_to_menu_keyboard()
            )
            return
        
        # Создаем платеж с флагом автоплатежа
        payment_data = {
            "user_id": user_data["id"],
            "subscription_type": plan_id,
            "service_name": plan["name"],
            "user_email": f"user_{user_id}@telegram.local",
            "success_url": f"https://t.me/vpn_bezlagov_test_bot?start=payment_success",
            "fail_url": f"https://t.me/vpn_bezlagov_test_bot?start=payment_fail",
            "provider_type": "robokassa",  # Автоплатежи только через Robokassa
            "enable_autopay": True  # Ключевой флаг
        }
        
        payment_result = await api_client.create_payment(payment_data)
        
        if payment_result.get("status") == "success":
            payment_url = payment_result["payment_url"]
            payment_id = payment_result["payment_id"]
            amount = payment_result["amount"]
            
            # Сохраняем ID платежа в состоянии
            await state.update_data(payment_id=payment_id)
            
            # Создаем клавиатуру с кнопкой оплаты
            payment_keyboard = get_existing_payment_keyboard(payment_id, payment_url)
            
            text = (
                f"💳 **Оплата с автоплатежом**\n\n"
                f"📋 **План:** {plan['name']}\n"
                f"💰 **Сумма:** {amount}₽\n\n"
                f"⚡ **Автоплатеж будет настроен** после первой оплаты\n"
                f"🔄 Подписка будет автоматически продлеваться каждый период\n\n"
                f"👆 Нажмите для перехода к оплате"
            )
            
            await callback.message.edit_text(
                text,
                reply_markup=payment_keyboard,
                parse_mode="Markdown"
            )
            
        else:
            error_message = payment_result.get('detail', 'Неизвестная ошибка')
            await callback.message.edit_text(
                f"❌ Ошибка создания платежа: {error_message}",
                reply_markup=get_back_to_menu_keyboard()
            )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error handling autopay payment: {e}")
        await callback.message.edit_text(
            "❌ Произошла ошибка при создании платежа",
            reply_markup=get_back_to_menu_keyboard()
        )
        await callback.answer()

@router.callback_query(F.data == "autopay_disable")
async def handle_autopay_disable(callback: CallbackQuery):
    """Отключение автоплатежа"""
    try:
        telegram_id = callback.from_user.id
        
        # Подтверждение отключения
        text = (
            "⚠️ **Отключение автоплатежа**\n\n"
            "Вы уверены, что хотите отключить автоматическое продление подписки?\n\n"
            "После отключения нужно будет продлевать подписку вручную."
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="✅ Да, отключить",
                callback_data="autopay_disable_confirm"
            )],
            [InlineKeyboardButton(
                text="❌ Отмена",
                callback_data="back_to_subscription"
            )]
        ])
        
        await callback.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error handling autopay disable: {e}")
        await callback.answer("❌ Произошла ошибка")

@router.callback_query(F.data == "autopay_disable_confirm")
async def handle_autopay_disable_confirm(callback: CallbackQuery):
    """Подтверждение отключения автоплатежа"""
    try:
        telegram_id = callback.from_user.id
        
        # Отключаем автоплатеж через API
        api_client = SimpleAPIClient()
        result = await api_client.cancel_user_auto_payment(telegram_id)
        
        if result and result.get('success'):
            text = (
                "✅ **Автоплатеж отключен**\n\n"
                "Автоматическое продление подписки отключено.\n"
                "Теперь нужно будет продлевать подписку вручную."
            )
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="📋 Планы подписок",
                    callback_data="show_plans"
                )],
                [InlineKeyboardButton(
                    text="⬅️ Главное меню",
                    callback_data="back_to_main_menu"
                )]
            ])
        else:
            text = (
                "❌ **Ошибка**\n\n"
                "Не удалось отключить автоплатеж. Попробуйте позже или обратитесь в поддержку."
            )
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="🔄 Попробовать снова",
                    callback_data="autopay_disable"
                )],
                [InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="back_to_subscription"
                )]
            ])
        
        await callback.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error confirming autopay disable: {e}")
        await callback.answer("❌ Произошла ошибка")

@router.callback_query(F.data == "back_to_subscription")
async def back_to_subscription_view(callback: CallbackQuery):
    """Возврат к просмотру подписки"""
    try:
        # Эмулируем обработку команды "💳 Подписка"
        from aiogram.types import Message
        
        # Создаем фейковое сообщение для вызова обработчика
        await show_subscription_plans(callback.message, FSMContext())
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error going back to subscription: {e}")
        await callback.answer("❌ Произошла ошибка")

@router.callback_query(F.data == "show_plans")
async def show_plans_callback(callback: CallbackQuery):
    """Показать планы подписок (callback версия)"""
    try:
        keyboard = await get_subscription_keyboard_with_autopay()
        
        text = (
            f"💳 **Выберите план подписки**\n\n"
            f"⚡ **С автоплатежом** - автоматическое продление\n"
            f"💳 **Обычная оплата** - разовый платеж\n\n"
            f"💡 Чем дольше подписка, тем больше скидка!"
        )
        
        await callback.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error showing plans: {e}")
        await callback.answer("❌ Произошла ошибка")

@router.callback_query(F.data == "autopay_enable")
async def handle_autopay_enable(callback: CallbackQuery):
    """Включение автоплатежа"""
    try:
        telegram_id = callback.from_user.id
        api_client = SimpleAPIClient()
        
        result = await api_client.enable_user_auto_payment(telegram_id)
        
        if result and result.get('success'):
            await callback.answer("✅ Автопродление включено")
            # Обновляем отображение подписки
            await refresh_subscription_display(callback.message, telegram_id)
        else:
            await callback.answer("❌ Ошибка включения автопродления")
            
    except Exception as e:
        logger.error(f"Error enabling autopay: {e}")
        await callback.answer("❌ Произошла ошибка")


@router.callback_query(F.data == "toggle_autopay_on")
async def handle_toggle_autopay_on(callback: CallbackQuery):
    """Включение автопродления через toggle кнопку"""
    try:
        telegram_id = callback.from_user.id
        api_client = SimpleAPIClient()
        
        result = await api_client.enable_user_auto_payment(telegram_id)
        
        if result and result.get('success'):
            await callback.answer("✅ Автопродление включено")
            # Получаем обновленную информацию о подписке
            subscription_info = await api_client.get_user_subscription_status(telegram_id)
            
            if subscription_info and subscription_info.get('success'):
                days_remaining = subscription_info.get('days_remaining', 0)
                
                if days_remaining > 0:
                    # Обновляем меню для активной подписки
                    await show_active_subscription_info_with_autopay_state(callback.message, subscription_info, telegram_id, True)
                else:
                    # Обновляем меню выбора планов
                    await show_subscription_plans_selection_with_new_state(callback.message, autopay_enabled=True)
            else:
                # Если не удалось получить статус подписки, обновляем с включенным автопродлением
                await show_subscription_plans_selection_with_new_state(callback.message, autopay_enabled=True)
        else:
            await callback.answer("❌ Ошибка включения автопродления")
            
    except Exception as e:
        logger.error(f"Error toggling autopay on: {e}")
        await callback.answer("❌ Произошла ошибка")


@router.callback_query(F.data == "toggle_autopay_off")  
async def handle_toggle_autopay_off(callback: CallbackQuery):
    """Отключение автопродления через toggle кнопку"""
    try:
        telegram_id = callback.from_user.id
        api_client = SimpleAPIClient()
        
        result = await api_client.cancel_user_auto_payment(telegram_id)
        
        if result and result.get('success'):
            await callback.answer("✅ Автопродление отключено")
            # Получаем обновленную информацию о подписке
            subscription_info = await api_client.get_user_subscription_status(telegram_id)
            
            if subscription_info and subscription_info.get('success'):
                days_remaining = subscription_info.get('days_remaining', 0)
                
                if days_remaining > 0:
                    # Обновляем меню для активной подписки
                    await show_active_subscription_info_with_autopay_state(callback.message, subscription_info, telegram_id, False)
                else:
                    # Обновляем меню выбора планов
                    await show_subscription_plans_selection_with_new_state(callback.message, autopay_enabled=False)
            else:
                # Если не удалось получить статус подписки, обновляем с отключенным автопродлением
                await show_subscription_plans_selection_with_new_state(callback.message, autopay_enabled=False)
        else:
            await callback.answer("❌ Ошибка отключения автопродления")
            
    except Exception as e:
        logger.error(f"Error toggling autopay off: {e}")
        await callback.answer("❌ Произошла ошибка")


async def show_subscription_plans_selection_with_new_state(message: Message, autopay_enabled: bool):
    """Обновление меню выбора планов с новым состоянием автопродления"""
    
    text = (
        f"💳 **Выберите план подписки:**\n\n"
        f"📊 Доступные тарифы для подключения VPN сервиса"
    )
    
    keyboard = await get_subscription_keyboard_with_autopay_toggle(autopay_enabled)
    
    try:
        await message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error updating message: {e}")
        # Если не удалось отредактировать, отправляем новое сообщение
        await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")


async def refresh_subscription_display(message: Message, telegram_id: int):
    """Обновление отображения подписки"""
    api_client = SimpleAPIClient()
    subscription_info = await api_client.get_user_subscription_status(telegram_id)
    
    if subscription_info and subscription_info.get('success'):
        days_remaining = subscription_info.get('days_remaining', 0)
        
        if days_remaining > 0:
            await show_active_subscription_info(message, subscription_info, telegram_id)
        else:
            await show_subscription_plans_selection_with_new_state(message, autopay_enabled=True)

class SimpleAPIClient:
    """Упрощенный API клиент для работы с backend"""
    
    def __init__(self):
        self.base_url = "http://backend:8000"
    
    async def _make_request(self, method: str, endpoint: str, data: Dict = None) -> Dict:
        """Выполнение HTTP запроса"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}{endpoint}"
                async with session.request(method, url, json=data) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        text = await response.text()
                        logger.error("API request failed", status=response.status, response=text)
                        try:
                            detail = json.loads(text)
                        except json.JSONDecodeError:
                            detail = text
                        return {"error": f"HTTP {response.status}", "detail": detail}
        except Exception as e:
            logger.error("API request error", error=str(e))
            return {"error": str(e), "detail": str(e)}
    
    async def get_user_by_telegram_id(self, telegram_id: int) -> Dict:
        """Получение пользователя по telegram_id"""
        return await self._make_request("GET", f"/api/v1/users/telegram/{telegram_id}")
    
    async def create_payment(self, payment_data: Dict) -> Dict:
        """Создание платежа"""
        return await self._make_request("POST", "/api/v1/payments/create", payment_data)
    
    async def get_payment_status(self, payment_id: int) -> Dict:
        """Получение статуса платежа"""
        return await self._make_request("GET", f"/api/v1/payments/{payment_id}") 
    
    async def get_user_pending_payments(self, telegram_id: int) -> Dict:
        """Получение неоплаченных платежей пользователя"""
        return await self._make_request("GET", f"/api/v1/payments/user/{telegram_id}/pending")
    
    async def cancel_user_pending_payments(self, telegram_id: int) -> Dict:
        """Отмена всех неоплаченных платежей пользователя"""
        return await self._make_request("POST", f"/api/v1/payments/user/{telegram_id}/cancel_all")
    
    async def get_active_payment_providers(self) -> Dict:
        """Получение списка активных провайдеров"""
        return await self._make_request("GET", "/api/v1/payments/providers/active")

    async def get_user_auto_payment_info(self, telegram_id: int) -> Dict:
        """Получение информации об автоплатеже пользователя"""
        return await self._make_request("GET", f"/api/v1/users/{telegram_id}/auto_payment_info")

    async def get_user_subscription_status(self, telegram_id: int) -> Dict:
        """Получение статуса подписки пользователя"""
        return await self._make_request("GET", f"/api/v1/users/{telegram_id}/subscription_status")

    async def cancel_user_auto_payment(self, telegram_id: int) -> Dict:
        """Отключение автоплатежа пользователя"""
        return await self._make_request("POST", f"/api/v1/users/{telegram_id}/auto_payment/disable")

    async def enable_user_auto_payment(self, telegram_id: int) -> Dict:
        """Включение автоплатежа пользователя"""
        return await self._make_request("POST", f"/api/v1/users/{telegram_id}/auto_payment/enable")