# DATABASE SCHEMA DESIGN - VPN Service

## PostgreSQL Schema for MVP

```sql
-- Users table
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(255),
    first_name VARCHAR(255),
    referrer_id INTEGER REFERENCES users(id),
    balance DECIMAL(10,2) DEFAULT 0.00,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Subscription plans
CREATE TABLE subscription_plans (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    duration_days INTEGER NOT NULL,
    price_rub DECIMAL(8,2) NOT NULL,
    features JSONB, -- {"traffic_limit": null, "servers": "all", "devices": 5}
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User subscriptions
CREATE TABLE subscriptions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    plan_id INTEGER REFERENCES subscription_plans(id),
    start_date TIMESTAMP NOT NULL,
    end_date TIMESTAMP NOT NULL,
    status VARCHAR(20) DEFAULT 'active', -- active, expired, cancelled
    vpn_key TEXT, -- VLESS key from 3X-UI
    qr_code TEXT, -- Base64 QR code
    server_id INTEGER REFERENCES vpn_servers(id),
    traffic_used BIGINT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- VPN servers
CREATE TABLE vpn_servers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    location VARCHAR(100),
    endpoint VARCHAR(255) NOT NULL,
    xui_panel_url VARCHAR(255),
    xui_username VARCHAR(100),
    xui_password VARCHAR(255),
    max_users INTEGER DEFAULT 1000,
    current_users INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Payments
CREATE TABLE payments (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    subscription_id INTEGER REFERENCES subscriptions(id),
    amount DECIMAL(10,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'RUB',
    payment_method VARCHAR(20) NOT NULL, -- sbp, card, crypto
    status VARCHAR(20) DEFAULT 'pending', -- pending, completed, failed, cancelled
    external_id VARCHAR(255), -- ID from payment provider
    external_data JSONB, -- Additional data from provider
    webhook_received_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Referral system
CREATE TABLE referrals (
    id SERIAL PRIMARY KEY,
    referrer_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    referred_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    bonus_amount DECIMAL(8,2),
    status VARCHAR(20) DEFAULT 'pending', -- pending, paid, cancelled
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(referrer_id, referred_id)
);

-- Audit logs
CREATE TABLE audit_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50), -- user, subscription, payment
    entity_id INTEGER,
    details JSONB,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Notification queue
CREATE TABLE notifications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    type VARCHAR(50) NOT NULL, -- payment_success, subscription_expiring, etc.
    title VARCHAR(255),
    message TEXT,
    data JSONB,
    status VARCHAR(20) DEFAULT 'pending', -- pending, sent, failed
    scheduled_at TIMESTAMP,
    sent_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_users_telegram_id ON users(telegram_id);
CREATE INDEX idx_subscriptions_user_id ON subscriptions(user_id);
CREATE INDEX idx_subscriptions_status ON subscriptions(status);
CREATE INDEX idx_subscriptions_end_date ON subscriptions(end_date);
CREATE INDEX idx_payments_user_id ON payments(user_id);
CREATE INDEX idx_payments_status ON payments(status);
CREATE INDEX idx_payments_external_id ON payments(external_id);
CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at);
CREATE INDEX idx_notifications_user_id ON notifications(user_id);
CREATE INDEX idx_notifications_status ON notifications(status);

-- Sample data
INSERT INTO subscription_plans (name, duration_days, price_rub, features) VALUES
('1 месяц', 30, 249.00, '{"traffic_limit": null, "devices": 5}'),
('3 месяца', 90, 599.00, '{"traffic_limit": null, "devices": 5, "discount": 20}'),
('6 месяцев', 180, 1049.00, '{"traffic_limit": null, "devices": 5, "discount": 30}'),
('12 месяцев', 365, 1999.00, '{"traffic_limit": null, "devices": 5, "discount": 45}');

INSERT INTO vpn_servers (name, location, endpoint, is_active) VALUES
('Server-1', 'Netherlands', 'your-domain.com:443', true);
```

## Key Design Decisions

1. **JSONB для гибкости**: features в планах, details в логах
2. **Referential integrity**: CASCADE DELETE для связанных данных
3. **Индексы для производительности**: на часто запрашиваемые поля
4. **Аудит**: полное логирование действий пользователей
5. **Уведомления**: отдельная таблица для queue processing
6. **Масштабируемость**: возможность добавления серверов

## SQLAlchemy Models Structure

```python
# models/user.py
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String(255))
    # ... остальные поля
    
    subscriptions = relationship("Subscription", back_populates="user")
    payments = relationship("Payment", back_populates="user")

# models/subscription.py  
class Subscription(Base):
    __tablename__ = "subscriptions"
    # ... поля
    
    user = relationship("User", back_populates="subscriptions")
    plan = relationship("SubscriptionPlan")
``` 