import asyncio
import json
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

async def test_client_cleanup():
    """Тестирование очистки клиентов"""
    # Подключение к базе данных
    DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/vpn_db"
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    print("Подключение к базе данных...")
    async with async_session() as session:
        # Импортируем утилиту для очистки клиентов
        try:
            # Используем импорт без тире
            import sys
            sys.path.append('./vpn-service')
            from backend.services.client_cleanup_utility import ClientCleanupUtility
            print("Модуль client_cleanup_utility успешно импортирован")
        except ImportError as e:
            print(f"Ошибка импорта модуля client_cleanup_utility: {e}")
            return
        
        print("Создание экземпляра ClientCleanupUtility...")
        util = ClientCleanupUtility(session)
        
        print("Получение списка активных нод...")
        nodes = await util.get_active_nodes()
        print(f"Найдено {len(nodes)} активных нод")
        
        if not nodes:
            print("Нет активных нод для тестирования")
            return
        
        node = nodes[0]
        print(f"Тестирование на ноде: {node.name} (ID: {node.id})")
        
        print("Получение списка клиентов на ноде...")
        clients = await util.get_clients_on_node(node)
        print(f"Найдено {len(clients)} клиентов на ноде")
        
        print("Поиск осиротевших клиентов и дубликатов...")
        orphaned, duplicates = await util.find_orphaned_clients(node)
        print(f"Найдено {len(orphaned)} осиротевших клиентов и {len(duplicates)} дубликатов")
        
        if orphaned or duplicates:
            print("Удаление осиротевших клиентов и дубликатов...")
            result = await util.delete_orphaned_clients(node)
            print(f"Результаты удаления: {json.dumps(result, indent=2)}")
        
        print("Запуск очистки всех нод...")
        result = await util.cleanup_all_nodes()
        print(f"Результаты очистки: {json.dumps(result, indent=2)}")

if __name__ == "__main__":
    asyncio.run(test_client_cleanup()) 