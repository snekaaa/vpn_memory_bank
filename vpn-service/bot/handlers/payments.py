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
    get_existing_payment_keyboard
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

@router.message(F.text.startswith("💳 Подписка"))
async def show_subscription_plans(message: Message, state: FSMContext):
    """Показать планы подписок или существующие неоплаченные счета"""
    try:
        telegram_id = message.from_user.id
        
        # Сначала проверяем есть ли у пользователя неоплаченные платежи
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
        
        # Нет неоплаченных платежей - показываем планы БЕЗ кнопки отмены
        await state.set_state(PaymentStates.selecting_plan)
        
        # Получаем планы из API для формирования текста
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
        
        await message.answer(
            text,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Error showing subscription plans: {e}")
        # Получаем количество дней для главного меню
        days_remaining = await get_user_subscription_days(message.from_user.id)
        await message.answer(
            "❌ Произошла ошибка при загрузке планов подписки",
            reply_markup=get_main_menu(days_remaining)
        )

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
        
        # Получаем количество дней для главного меню
        days_remaining = await get_user_subscription_days(callback.from_user.id)
        
        await callback.message.delete()
        await callback.message.answer(
            "🏠 Главное меню",
            reply_markup=get_main_menu(days_remaining)
        )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error returning to main menu: {e}")
        await callback.answer("❌ Произошла ошибка")

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