# Design Document: Autopay Toggle Fix

## Overview

This design document outlines the solution for fixing the bug where autopay toggle preferences are not being saved for users without active subscriptions in the VPN service Telegram bot. The current implementation correctly updates the UI when a user toggles the autopay setting, but fails to persist this preference in the database for users without active subscriptions, leading to inconsistent behavior.

## Architecture

The fix will maintain the existing architecture while ensuring that autopay preferences are properly persisted regardless of subscription status:

1. **Frontend (Telegram Bot)**: The bot will continue to use the existing toggle handlers but will ensure proper error handling and feedback.

2. **Backend API**: The backend API will be modified to handle autopay preference updates for all users, regardless of subscription status.

3. **Database**: The existing `auto_payment` table will be used to store user preferences, ensuring that preferences are maintained even when a user doesn't have an active subscription.

## Components and Interfaces

### 1. Telegram Bot Handlers

The existing handlers `handle_toggle_autopay_on` and `handle_toggle_autopay_off` will be modified to:

- Ensure proper error handling
- Provide clear feedback to users when preferences are saved or when errors occur
- Correctly update the UI state after preference changes

```python
@router.callback_query(F.data == "toggle_autopay_on")
async def handle_toggle_autopay_on(callback: CallbackQuery):
    """Enabling autopay through toggle button"""
    try:
        telegram_id = callback.from_user.id
        api_client = SimpleAPIClient()
        
        # Call API to enable autopay
        result = await api_client.enable_user_auto_payment(telegram_id)
        
        if result and result.get('success'):
            await callback.answer("✅ Autopay enabled")
            
            # Get updated subscription info
            subscription_info = await api_client.get_user_subscription_status(telegram_id)
            
            # Update UI based on subscription status
            if subscription_info and subscription_info.get('success'):
                days_remaining = subscription_info.get('days_remaining', 0)
                
                if days_remaining > 0:
                    # Update active subscription menu
                    await show_active_subscription_info_with_autopay_state(callback.message, subscription_info, telegram_id, True)
                else:
                    # Update subscription plans selection with new autopay state
                    await show_subscription_plans_selection_with_new_state(callback.message, autopay_enabled=True)
            else:
                # Fallback if subscription status can't be retrieved
                await show_subscription_plans_selection_with_new_state(callback.message, autopay_enabled=True)
        else:
            error_msg = result.get('message', 'Unknown error') if result else 'Failed to connect to server'
            await callback.answer(f"❌ Error enabling autopay: {error_msg}")
            
    except Exception as e:
        logger.error(f"Error toggling autopay on: {e}")
        await callback.answer("❌ An error occurred")
```

Similar changes will be made to the `handle_toggle_autopay_off` handler.

### 2. Backend API Endpoints

The backend API endpoints for managing autopay preferences will be modified to:

- Handle requests for users without active subscriptions
- Return appropriate error messages when operations fail
- Ensure consistent behavior across all user states

```python
@router.post("/api/v1/users/{telegram_id}/auto_payment/enable")
async def enable_user_auto_payment(
    telegram_id: int,
    db: AsyncSession = Depends(get_async_session)
):
    """Enable autopay for a user regardless of subscription status"""
    try:
        # Get user by telegram_id
        user = await get_user_by_telegram_id(db, telegram_id)
        if not user:
            return {"success": False, "message": "User not found"}
        
        # Update or create autopay preference
        await update_user_auto_payment(db, user.id, enabled=True)
        
        return {"success": True}
    except Exception as e:
        logger.error(f"Error enabling autopay: {e}")
        return {"success": False, "message": str(e)}
```

Similar changes will be made to the disable endpoint.

### 3. Database Service

The database service for autopay preferences will be enhanced to:

- Create autopay preference records for users without existing records
- Update existing records regardless of subscription status
- Handle edge cases and provide proper error handling

```python
async def update_user_auto_payment(
    db: AsyncSession, 
    user_id: int, 
    enabled: bool
) -> bool:
    """Update or create user autopay preference"""
    try:
        # Check if auto_payment record exists
        stmt = select(AutoPayment).where(AutoPayment.user_id == user_id)
        result = await db.execute(stmt)
        auto_payment = result.scalar_one_or_none()
        
        if auto_payment:
            # Update existing record
            auto_payment.enabled = enabled
        else:
            # Create new record
            auto_payment = AutoPayment(
                user_id=user_id,
                enabled=enabled,
                created_at=datetime.utcnow()
            )
            db.add(auto_payment)
        
        await db.commit()
        return True
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating autopay preference: {e}")
        raise
```

### 4. Helper Functions

The helper function `show_subscription_plans_selection` will be modified to:

- Retrieve the user's actual autopay preference from the database
- Use the retrieved preference instead of defaulting to True
- Handle errors gracefully

```python
async def show_subscription_plans_selection(message: Message, state: FSMContext):
    """Show subscription plan selection for users without active subscription"""
    try:
        telegram_id = message.from_user.id
        api_client = SimpleAPIClient()
        
        # Get user's autopay preference
        auto_payment_info = await api_client.get_user_auto_payment_info(telegram_id)
        autopay_enabled = auto_payment_info.get('enabled', True)  # Default to True if not found
        
        text = (
            f"💳 **Choose a subscription plan:**\n\n"
            f"📊 Available plans for VPN service"
        )
        
        # Use the retrieved autopay preference
        keyboard = await get_subscription_keyboard_with_autopay_toggle(autopay_enabled)
        
        await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
        await state.set_state(PaymentStates.selecting_plan)
    except Exception as e:
        logger.error(f"Error showing subscription plans: {e}")
        await message.answer(
            "❌ Error loading subscription plans. Please try again.",
            reply_markup=get_back_to_menu_keyboard()
        )
```

## Data Models

We'll use the existing `AutoPayment` model which should have the following structure:

```python
class AutoPayment(Base):
    __tablename__ = "auto_payment"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationship
    user = relationship("User", back_populates="auto_payment")
```

## Error Handling

The solution will implement comprehensive error handling:

1. **API Errors**: All API calls will include proper error handling with specific error messages.
2. **Database Errors**: Database operations will be wrapped in try-except blocks with rollback on failure.
3. **UI Feedback**: Users will receive clear feedback when operations succeed or fail.
4. **Logging**: All errors will be logged with sufficient context for debugging.

## Testing Strategy

The fix will be tested using the following approach:

1. **Unit Tests**:
   - Test autopay preference update for users without subscriptions
   - Test autopay preference retrieval for users without subscriptions
   - Test error handling in API endpoints

2. **Integration Tests**:
   - Test the complete flow of toggling autopay and verifying persistence
   - Test the flow across subscription state changes (active → expired)

3. **Manual Testing**:
   - Verify UI updates correctly when toggling autopay
   - Verify preferences persist after bot restart
   - Verify preferences are applied correctly when making purchases