# VPN Service - Active Tasks

## 📋 CURRENT STATUS: НОВАЯ ЗАДАЧА - Улучшение скрипта автосоздания нод для обхода блокировок

**Last Updated**: 2025-08-21  
**Memory Bank Status**: ✅ Ready for new task  
**System Status**: ✅ Operational, требует улучшения node creation algorithm  

## 🎯 ЗАДАЧА: Модификация скрипта автосоздания VPN нод для максимальной совместимости

### 📋 ОПИСАНИЕ ПРОБЛЕМЫ
Текущий скрипт автоматического создания нод (http://localhost:8000/admin/nodes/auto/create) создает VLESS конфигурации с Reality+XTLS технологией, которые блокируются в некоторых странах (например, Киргизия). Нужно модифицировать алгоритм для создания более универсальных конфигураций.

**Текущая проблема**:
- ✅ Reality+XTLS: Быстро, но блокируется DPI в некоторых странах
- ❌ WebSocket+TLS: Медленнее, но работает везде через маскировку под HTTPS

**Анализ различий ключей**:

**Первый ключ (блокируется в Киргизии)**:
```
vless://...@146.103.123.8:443
?type=tcp&security=reality&flow=xtls-rprx-vision
&sni=apple.com&pbk=uPL_f_-RrvOMk0PLILkHa6xixkGGdjxvIejRuIQrG1c
```
- Протокол: TCP + Reality
- Маскировка: Reality с SNI подменой
- Проблема: DPI легко обнаруживает Reality/XTLS трафик

**Второй ключ (работает везде)**:
```
vless://...@91.103.140.180:443
?type=ws&security=tls&path=%2Fxray
&host=sss.mahmalganat.online&fragment=3,1,tlshello
&alpn=h2&sni=sss.mahmalganat.online
```
- Протокол: WebSocket + TLS
- Маскировка: Под обычный HTTPS-сайт
- Преимущество: DPI не может отличить от веб-трафика

### 🧩 COMPLEXITY ASSESSMENT
**Level: 3** - Intermediate Feature
**Type**: Algorithm Enhancement / Anti-Censorship Technology

**Обоснование Level 3**:
- Требует понимания VPN протоколов и anti-censorship технологий
- Модификация существующего алгоритма создания нод
- Интеграция с X3UI API для настройки WS+TLS
- Необходимо тестирование в различных сетевых условиях
- Влияет на пользователей в странах с блокировками

## 🛠️ TECHNOLOGY STACK

### Затронутые компоненты:
- **Admin Panel**: Node auto-creation endpoint
- **X3UI Integration**: VLESS configuration templates
- **Backend Services**: Node automation и configuration generation
- **Database**: VPN nodes storage и templates

### Технические требования:
- **VLESS Protocol**: WebSocket + TLS configuration
- **Domain Fronting**: Использование реальных доменов для маскировки
- **Fragment Parameters**: Настройка fragment для обхода DPI
- **TLS Configuration**: ALPN h2, proper SNI settings

## ✅ TECHNOLOGY VALIDATION CHECKLIST

- [x] **Admin panel accessible** - http://localhost:8000/admin/nodes/auto/create работает
- [x] **X3UI API available** - Интеграция с X3UI для создания inbound'ов
- [x] **Current algorithm analyzed** - Reality+XTLS approach identified
- [ ] **WS+TLS requirements researched** - Нужно изучить параметры
- [ ] **Domain fronting strategy** - Выбор доменов для маскировки
- [ ] **Fragment optimization** - Настройка параметров обхода DPI

## 📋 IMPLEMENTATION PLAN

### Фаза 1: Исследование и анализ (1 день)
1. **Анализ текущего алгоритма**
   - Изучение кода auto-creation endpoint'а
   - Понимание X3UI API для создания VLESS inbound'ов
   - Анализ текущих Reality+XTLS настроек

2. **Исследование WS+TLS конфигураций**
   - Изучение оптимальных параметров WebSocket+TLS
   - Анализ fragment settings для различных регионов
   - Выбор доменов для domain fronting

3. **Техническое планирование**
   - Определение новой структуры конфигурации
   - Планирование A/B тестирования алгоритмов
   - Стратегия постепенного перехода

### Фаза 2: Реализация нового алгоритма (1-2 дня)
1. **Создание WS+TLS template**
   - Разработка конфигурации WebSocket+TLS
   - Интеграция domain fronting
   - Настройка fragment parameters

2. **Модификация auto-creation logic**
   - Добавление выбора между Reality и WS+TLS
   - Реализация региональной логики (по умолчанию WS+TLS)
   - Сохранение backward compatibility

3. **Обновление X3UI интеграции**
   - Модификация API вызовов для WS+TLS inbound'ов
   - Настройка правильных TLS сертификатов
   - Конфигурация path и host параметров

### Фаза 3: Тестирование и оптимизация (1 день)
1. **Функциональное тестирование**
   - Создание тестовых нод с новым алгоритмом
   - Проверка подключения из различных регионов
   - Валидация производительности

2. **A/B тестирование**
   - Сравнение Reality vs WS+TLS в различных условиях
   - Анализ скорости и стабильности соединений
   - Оценка обхода блокировок

3. **Документирование и rollout**
   - Документация новых настроек
   - Планирование постепенного внедрения
   - Создание fallback механизмов

## 🔍 ТЕХНИЧЕСКИЕ ДЕТАЛИ

### Целевая конфигурация WS+TLS:
```json
{
  "protocol": "vless",
  "settings": {
    "clients": [{"id": "uuid", "encryption": "none"}]
  },
  "streamSettings": {
    "network": "ws",
    "security": "tls",
    "wsSettings": {
      "path": "/xray",
      "headers": {"Host": "domain.com"}
    },
    "tlsSettings": {
      "serverName": "domain.com",
      "alpn": ["h2", "http/1.1"],
      "fragment": {
        "packets": "3,1",
        "length": "tlshello"
      }
    }
  }
}
```

### Параметры для обхода DPI:
- **Fragment**: `3,1,tlshello` - дробление TLS handshake
- **ALPN**: `h2` - имитация HTTP/2 трафика  
- **Path**: `/xray` или другие реалистичные пути
- **SNI**: Использование реальных доменов

### Домены для fronting:
- Content delivery networks (CDN) домены
- Популярные сервисы (например, storage services)
- Регионально-нейтральные домены

## 📋 ДИАГНОСТИЧЕСКИЕ ВОПРОСЫ

1. **Текущий алгоритм**:
   - Как именно работает auto-creation endpoint?
   - Какие параметры используются для Reality конфигурации?
   - Есть ли возможность выбора типа конфигурации?

2. **X3UI интеграция**:
   - Какие API методы используются для создания inbound'ов?
   - Поддерживает ли X3UI WebSocket+TLS out of the box?
   - Как настраиваются TLS сертификаты?

3. **Производительность**:
   - Какая разница в скорости между Reality и WS+TLS?
   - Какие overhead параметры у fragment настроек?
   - Как влияет domain fronting на latency?

## 🎯 SUCCESS CRITERIA

- ✅ Скрипт создает WS+TLS конфигурации по умолчанию
- ✅ Возможность выбора между Reality и WS+TLS режимами
- ✅ Правильные fragment настройки для обхода DPI
- ✅ Domain fronting для максимальной маскировки
- ✅ Backward compatibility с существующими нодами
- ✅ Тестирование работы в "сложных" регионах (Киргизия, и т.д.)

## 📋 VERIFICATION CHECKLIST

- [x] **Current algorithm analyzed** - Текущий код auto-creation изучен
- [x] **WS+TLS template created** - Новая конфигурация разработана
- [ ] **X3UI integration updated** - API вызовы модифицированы
- [ ] **Fragment parameters optimized** - DPI обход настроен
- [ ] **Domain fronting configured** - Маскировка доменов реализована
- [ ] **Testing completed** - Проверка в различных регионах
- [ ] **Documentation updated** - Инструкции обновлены

## ✅ CREATIVE PHASE COMPLETED

### 🎨 ALGORITHM ARCHITECTURE DESIGN - COMPLETED ✅

**Creative Document**: `memory-bank/creative/creative-anti-censorship-node-algorithm.md`

**Архитектурные решения принятые**:
1. ✅ **WebSocket+TLS First Approach** - выбрана как оптимальная архитектура
2. ✅ **Domain Fronting Strategy** - использование популярных CDN доменов
3. ✅ **Fragment Optimization** - региональные настройки для обхода DPI
4. ✅ **Protocol Selection Interface** - advanced опции для выбора Reality+XTLS
5. ✅ **Phased Implementation** - поэтапное внедрение с backward compatibility

**Technical Specifications Ready**:
- ✅ WebSocket+TLS configuration template разработан
- ✅ Domain pool management strategy определена
- ✅ Fragment parameter optimization по регионам
- ✅ X3UI API integration approach спланирован
- ✅ Migration strategy для существующих нод

## 🚀 NEXT MODE RECOMMENDATION

**РЕКОМЕНДУЕМЫЙ РЕЖИМ**: 🛠️ **IMPLEMENT MODE**

**Обоснование**:
- ✅ Творческая фаза завершена - все архитектурные решения приняты
- ✅ Техническая спецификация готова для реализации
- ✅ WebSocket+TLS approach полностью спроектирован
- ✅ Domain fronting strategy определена
- ✅ Implementation guidelines детализированы
- 🛠️ Готов к переходу на фазу имплементации кода

---
*Anti-censorship node creation enhancement - ready for creative design phase*
