# Active Context

## Current Task
**VPN Country Selection Feature** (Level 3) - Добавление кнопок выбора стран в раздел "Мой VPN ключ" для смены серверов

## Task Details
- **Status**: All Creative Phases Complete, Ready for Implementation
- **Complexity**: Level 3 - Intermediate Feature
- **Components**: UI Enhancement + Database Integration + Server Selection Logic
- **Timeline**: 5-phase implementation plan (25 tasks)

## Creative Phases Completed ✅

### 1. UI/UX Design Decision
**Decision**: Vertical column layout with progressive loading
- "Текущий сервер: 🇷🇺 Россия" display above buttons
- Disabled state for current country with ✓ mark
- Progressive loading messages during 15-30 second server switches
- Direct switch without confirmation for optimal UX

### 2. Architecture Design Decision  
**Decision**: Hybrid Practical Architecture (Option 3)
- Countries table with flag emojis and priority system
- country_id field added to existing vpn_nodes table
- user_server_assignments table for current tracking
- CountryService, UserServerService, migration service
- Admin interface for country<->node management

### 3. Algorithm Design Decision
**Decision**: Weighted Load-Based Selection with health checks
- Multi-factor scoring: capacity (50%), performance (30%), priority (15%), affinity (5%)
- Comprehensive health checks with X3UI integration
- Smart fallback: neighboring countries → any country → emergency assignment
- Performance target: <100ms selection time for current 5 nodes

## Implementation Plan Summary
1. **Database & Models** (6 tasks) - Countries, UserServerAssignment, ServerSwitchLog models + migration
2. **Country Service** (7 tasks) - CountryService, UserServerService, algorithm, migration logic  
3. **Bot UI Enhancement** (5 tasks) - Enhanced keyboard, handlers, loading states
4. **Server Selection Logic** (5 tasks) - VPN manager integration, health checks, fallback
5. **Admin Integration** (5 tasks) - Admin routes, interface, migration tools

## Current System State
- **VPN Nodes Available**: 5 nodes with mixed location data
  - vpn2 (Auto-detected), vpn3 (Auto-detected)
  - Test Node (Россия), vpn2-2 (Нидерланды), vpn3-2 (Германия)
- **Bot Interface**: aiogram-based with inline keyboards
- **Current Flow**: "🔑 Мой VPN ключ" → VPN key + "🔄 Обновить ключ" button

## Key Design Decisions Made

### UI Design:
- Vertical layout for country buttons (easy mobile use)
- Current server indication with flag and checkmark
- Progressive loading with educational tips
- No confirmation dialog (direct switch for speed)

### Architecture:
- Hybrid approach balancing complexity and functionality
- Clean migration path from location strings to country system
- Separate services for country management and user assignments
- Admin-friendly interface for managing mappings

### Algorithm:
- Weighted scoring prevents simple round-robin issues
- Health checks prevent assignment to failed servers
- Fallback strategy ensures user always gets working server
- Performance optimized for current scale (5 nodes)

## Technology Stack
- **Backend**: FastAPI + SQLAlchemy + PostgreSQL (existing)
- **Bot**: aiogram 3.x (existing)
- **Integration**: X3UI API (existing)
- **New**: Country mapping system, Weighted server selection algorithm

## Next Action
**IMPLEMENT MODE** - Begin Phase 1: Database & Models

## Recently Completed
- **VPN Subscription Integration** (2025-01-09) - Complete system with access control
- **Archive**: [archive-vpn-subscription-integration-20250109.md](archive/archive-vpn-subscription-integration-20250109.md)

*All creative phases complete for VPN Country Selection Feature. 25 implementation tasks defined across 5 phases. Ready for IMPLEMENT mode.* 