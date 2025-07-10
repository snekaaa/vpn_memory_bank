# VPN Service - Project Brief

## 📋 PROJECT OVERVIEW

**Project Name**: VPN Memory Bank - Multi-Node VPN Service Platform  
**Type**: FastAPI + Telegram Bot VPN Management System  
**Status**: Production Ready - Continuous Enhancement Mode  
**Platform**: Docker + PostgreSQL + Multi-Node Architecture

## 🎯 CORE OBJECTIVES

**Primary Goal**: Автоматизированный VPN сервис с поддержкой множественных нод, платежными системами и Telegram Bot интерфейсом

**Key Features**:
- 🌐 **Multi-Node VPN Architecture** - Поддержка множественных X3UI нод
- 💳 **Payment Systems Integration** - Robokassa, FreeKassa payment processors
- 🤖 **Telegram Bot Interface** - Управление подписками через Telegram
- 👨‍💼 **Admin Dashboard** - Web интерфейс для администрирования
- 🔑 **VPN Key Management** - Автоматическое создание/удаление VLESS ключей
- 📊 **Subscription Management** - Система подписок с различными тарифами

## 🏗️ TECHNICAL ARCHITECTURE

### Backend Stack:
- **Framework**: FastAPI (Python)
- **Database**: PostgreSQL + SQLAlchemy ORM  
- **Authentication**: Session-based Admin auth
- **API Architecture**: RESTful endpoints
- **Payment Processing**: Multi-provider factory pattern

### Infrastructure:
- **Containerization**: Docker + Docker Compose
- **VPN Technology**: X3UI panels (VLESS protocol)
- **Load Balancing**: Round-robin node assignment
- **Monitoring**: Health checks + automated failover

### Bot Stack:
- **Framework**: aiogram (Telegram Bot API)
- **Storage**: PostgreSQL integration
- **UI**: Custom keyboards + inline buttons
- **Payment Flow**: Integrated с payment processors

## 🔄 SYSTEM COMPONENTS

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Telegram Bot  │────│  FastAPI Backend │────│  PostgreSQL DB  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                        ┌───────┴───────┐
                        │               │
                ┌───────▼─────┐ ┌───────▼─────┐
                │  X3UI Node 1 │ │  X3UI Node N │
                └─────────────┘ └─────────────┘
```

## 🌟 CURRENT STATE

**Production Status**: ✅ STABLE & OPERATIONAL
- Multi-node architecture working correctly
- Payment systems integrated (Robokassa + FreeKassa in progress)
- Admin panel fully functional
- Telegram bot operational

**Recent Achievements**:
- ✅ Critical multi-node architecture fixes completed (Jan 5-7, 2025)
- ✅ Payment provider system stabilized 
- ✅ Production deployment optimization
- ✅ UI simplification for VPN key management

## 🎯 ACTIVE DEVELOPMENT

**Current Task Priority**: FreeKassa Payment Integration (Level 3)
- ✅ Creative phase completed - Architecture designed
- ⚙️ Implementation phase required
- 🎯 Next Action: Type 'IMPLEMENT' to begin

**Implementation Strategy**: 5-Phase approach
1. Database & Model Updates
2. FreeKassa Service Implementation  
3. Admin Interface Enhancement
4. Bot Integration
5. Webhook & API Integration

## 📁 PROJECT STRUCTURE

```
vpn_memory_bank/
├── memory-bank/           # Project documentation & tracking
├── vpn-service/
│   ├── backend/          # FastAPI application
│   ├── bot/              # Telegram Bot
│   └── docker-compose.yml
├── production_setup.md   # Deployment documentation
└── deploy.sh            # Deployment scripts
```

## 🔧 DEVELOPMENT WORKFLOW

**Memory Bank System**: Активно используется для отслеживания задач
- Structured task management с progress tracking
- Creative phase documentation
- Reflection и archiving для completed tasks
- Technical context preservation между sessions 