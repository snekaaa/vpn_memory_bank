"""
Скрипт для тестирования функциональности очистки клиентов в контейнере.
Запускать с помощью команды:
docker exec -it vpn-service-backend-1 python test_in_container.py
"""

import asyncio
import json
from datetime import datetime
from config.database import get_db_session
from services.client_cleanup_utility import ClientCleanupUtility

async def test_cleanup():
    print(f"Запуск тестирования в {datetime.now().isoformat()}")
    
    async with get_db_session() as session:
        print("Сессия к БД успешно создана")
        
        # Создаем экземпляр утилиты для очистки
        util = ClientCleanupUtility(session)
        
        # Получаем список активных нод
        print("Получение списка активных нод...")
        nodes = await util.get_active_nodes()
        print(f"Найдено {len(nodes)} активных нод")
        
        if not nodes:
            print("Нет активных нод для тестирования")
            return
        
        # Берем первую ноду для тестирования
        node = nodes[0]
        print(f"Тестирование на ноде: {node.name} (ID: {node.id})")
        
        # Получаем список клиентов на ноде
        print("Получение списка клиентов на ноде...")
        clients = await util.get_clients_on_node(node)
        print(f"Найдено {len(clients)} клиентов на ноде")
        
        # Ищем осиротевших клиентов и дубликаты
        print("Поиск осиротевших клиентов и дубликатов...")
        orphaned, duplicates = await util.find_orphaned_clients(node)
        print(f"Найдено {len(orphaned)} осиротевших клиентов и {len(duplicates)} дубликатов")
        
        # Выводим информацию о найденных клиентах
        if orphaned:
            print("Осиротевшие клиенты:")
            for i, client in enumerate(orphaned[:5], 1):  # Показываем только первые 5
                print(f"  {i}. Email: {client.get('email', 'Н/Д')}, ID: {client.get('id', 'Н/Д')}, Inbound: {client.get('inbound_id', 'Н/Д')}")
            if len(orphaned) > 5:
                print(f"  ... и еще {len(orphaned) - 5}")
                
        if duplicates:
            print("Дубликаты:")
            for i, client in enumerate(duplicates[:5], 1):  # Показываем только первые 5
                print(f"  {i}. Email: {client.get('email', 'Н/Д')}, ID: {client.get('id', 'Н/Д')}, Inbound: {client.get('inbound_id', 'Н/Д')}")
            if len(duplicates) > 5:
                print(f"  ... и еще {len(duplicates) - 5}")
        
        # Запускаем очистку одной ноды
        if orphaned or duplicates:
            print("\n--- Тестирование очистки одной ноды ---")
            try:
                result = await util.delete_orphaned_clients(node)
                print(f"Результат очистки ноды: {json.dumps(result, indent=2)}")
            except Exception as e:
                print(f"Ошибка при очистке ноды: {str(e)}")
        
        # Запускаем очистку всех нод
        print("\n--- Тестирование очистки всех нод ---")
        try:
            result = await util.cleanup_all_nodes()
            print(f"Результат очистки всех нод: {json.dumps(result, indent=2)}")
        except Exception as e:
            print(f"Ошибка при очистке всех нод: {str(e)}")
        
        print("\nТестирование завершено!")

if __name__ == "__main__":
    asyncio.run(test_cleanup()) 