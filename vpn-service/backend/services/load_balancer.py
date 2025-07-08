"""
LoadBalancer Service - Балансировка нагрузки между VPN нодами
"""

import structlog
import random
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from sqlalchemy.orm import joinedload

from models.vpn_node import VPNNode
from models.user_node_assignment import UserNodeAssignment
from models.user import User
from config.database import get_db

logger = structlog.get_logger(__name__)

class LoadBalancer:
    """Балансировка нагрузки между нодами"""
    
    def __init__(self, db_session: AsyncSession = None):
        self.db = db_session
    
    async def select_optimal_node(self, user_id: Optional[int] = None) -> Optional[VPNNode]:
        """
        Выбор оптимальной ноды для пользователя
        
        Алгоритм:
        1. Фильтрация только здоровых нод
        2. Расчет нагрузки (current_users / max_users)
        3. Применение весов и приоритетов
        4. Выбор ноды с наименьшей взвешенной нагрузкой
        """
        try:
            # Получаем только активные и здоровые ноды
            result = await self.db.execute(
                select(VPNNode)
                .where(VPNNode.status == 'active')
                .where(VPNNode.health_status == 'healthy')
            )
            healthy_nodes = result.scalars().all()
            
            if not healthy_nodes:
                logger.error("No healthy nodes available")
                return None
            
            # Рассчитываем оценку для каждой ноды
            scored_nodes = []
            for node in healthy_nodes:
                # Проверяем может ли нода принимать пользователей
                if not node.can_accept_users:
                    continue
                
                # Рассчитываем финальную оценку (меньше = лучше)
                final_score = node.calculate_score()
                scored_nodes.append((node, final_score))
            
            if not scored_nodes:
                logger.error("No nodes available for new users")
                return None
            
            # Выбираем ноду с наименьшей оценкой
            optimal_node = min(scored_nodes, key=lambda x: x[1])[0]
            
            logger.info("Selected optimal node", 
                       node_id=optimal_node.id, 
                       name=optimal_node.name,
                       load_percentage=optimal_node.load_percentage)
            
            return optimal_node
            
        except Exception as e:
            logger.error("Error selecting optimal node", error=str(e))
            return None
    
    async def assign_user_to_node(self, user_id: int, node_id: Optional[int] = None) -> Optional[UserNodeAssignment]:
        """Привязка пользователя к ноде"""
        try:
            # Если нода не указана - выбираем оптимальную
            if node_id is None:
                optimal_node = await self.select_optimal_node()
                if not optimal_node:
                    return None
                node_id = optimal_node.id
            
            # Проверяем существование пользователя
            user_result = await self.db.execute(select(User).where(User.id == user_id))
            user = user_result.scalar_one_or_none()
            
            if not user:
                logger.error("User not found", user_id=user_id)
                return None
            
            # Проверяем существование ноды
            node_result = await self.db.execute(select(VPNNode).where(VPNNode.id == node_id))
            node = node_result.scalar_one_or_none()
            
            if not node:
                logger.error("Node not found", node_id=node_id)
                return None
            
            # Деактивируем все текущие привязки
            await self.db.execute(
                update(UserNodeAssignment)
                .where(UserNodeAssignment.user_id == user_id)
                .where(UserNodeAssignment.is_active == True)
                .values(is_active=False)
            )
            
            # Создаем новую привязку
            new_assignment = UserNodeAssignment(
                user_id=user_id,
                node_id=node_id,
                is_active=True,
                assigned_at=datetime.utcnow()
            )
            
            self.db.add(new_assignment)
            
            # Обновляем счетчик пользователей
            node.current_users += 1
            
            await self.db.commit()
            await self.db.refresh(new_assignment)
            
            logger.info("User assigned to node successfully", 
                       user_id=user_id, 
                       node_id=node_id,
                       assignment_id=new_assignment.id)
            
            return new_assignment
            
        except Exception as e:
            logger.error("Error assigning user to node", 
                        user_id=user_id, 
                        node_id=node_id, 
                        error=str(e))
            await self.db.rollback()
            return None
    
    async def get_user_node(self, user_id: int) -> Optional[VPNNode]:
        """Получение текущей ноды пользователя"""
        try:
            result = await self.db.execute(
                select(VPNNode)
                .join(UserNodeAssignment)
                .where(UserNodeAssignment.user_id == user_id)
                .where(UserNodeAssignment.is_active == True)
            )
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error("Error getting user node", user_id=user_id, error=str(e))
            return None
    
    async def migrate_user(self, user_id: int, target_node_id: int) -> bool:
        """Миграция пользователя на другую ноду"""
        try:
            # Получаем текущую ноду
            current_node = await self.get_user_node(user_id)
            
            # Создаем новый assignment
            new_assignment = await self.assign_user_to_node(user_id, target_node_id)
            
            if not new_assignment:
                return False
            
            # Обновляем счетчик на старой ноде
            if current_node:
                current_node.current_users = max(0, current_node.current_users - 1)
                await self.db.commit()
            
            logger.info("User migrated successfully", 
                       user_id=user_id,
                       from_node=current_node.id if current_node else None,
                       to_node=target_node_id)
            
            return True
            
        except Exception as e:
            logger.error("Error migrating user", 
                        user_id=user_id, 
                        target_node_id=target_node_id, 
                        error=str(e))
            await self.db.rollback()
            return False
    
    async def rebalance_users(self) -> Dict[str, Any]:
        """
        Перебалансировка пользователей между нодами
        для более равномерного распределения нагрузки
        """
        try:
            # Получаем все активные ноды
            nodes_result = await self.db.execute(
                select(VPNNode)
                .where(VPNNode.status == 'active')
                .where(VPNNode.health_status == 'healthy')
            )
            nodes = nodes_result.scalars().all()
            
            if not nodes or len(nodes) < 2:
                logger.info("Not enough healthy nodes for rebalancing")
                return {"success": False, "reason": "not_enough_nodes"}
            
            # Находим ноды с максимальной и минимальной нагрузкой
            max_load_node = max(nodes, key=lambda n: n.load_percentage)
            min_load_node = min(nodes, key=lambda n: n.load_percentage)
            
            # Если разница в нагрузке меньше 20% - не балансируем
            load_difference = max_load_node.load_percentage - min_load_node.load_percentage
            if load_difference < 20:
                logger.info("Load difference too small for rebalancing", 
                           difference=load_difference)
                return {"success": False, "reason": "small_difference"}
            
            # Получаем пользователей на ноде с максимальной нагрузкой
            users_result = await self.db.execute(
                select(User)
                .join(UserNodeAssignment)
                .where(UserNodeAssignment.node_id == max_load_node.id)
                .where(UserNodeAssignment.is_active == True)
                .limit(10)  # Мигрируем не более 10 пользователей за раз
            )
            users = users_result.scalars().all()
            
            if not users:
                logger.info("No users to migrate")
                return {"success": False, "reason": "no_users"}
            
            # Определяем количество пользователей для миграции
            # Перемещаем примерно столько, чтобы выровнять нагрузку
            users_to_migrate = min(
                len(users),
                int((max_load_node.current_users - min_load_node.current_users) / 2)
            )
            
            if users_to_migrate < 1:
                logger.info("No need to migrate users")
                return {"success": False, "reason": "balanced"}
            
            # Мигрируем пользователей
            migrated_count = 0
            for user in users[:users_to_migrate]:
                success = await self.migrate_user(user.id, min_load_node.id)
                if success:
                    migrated_count += 1
            
            logger.info("Users rebalanced successfully", 
                       from_node=max_load_node.id,
                       to_node=min_load_node.id,
                       migrated_count=migrated_count)
            
            return {
                "success": True,
                "from_node": max_load_node.id,
                "to_node": min_load_node.id,
                "migrated_count": migrated_count
            }
            
        except Exception as e:
            logger.error("Error rebalancing users", error=str(e))
            await self.db.rollback()
            return {"success": False, "reason": "error", "error": str(e)}
    
    async def get_node_load_stats(self) -> List[Dict[str, Any]]:
        """Получение статистики нагрузки по нодам"""
        try:
            # Получаем все ноды
            query = select(VPNNode)
            result = await self.db.execute(query)
            nodes = list(result.scalars().all())
            
            # Формируем статистику
            stats = []
            for node in nodes:
                # Создаем копию данных, чтобы избежать проблем с отсоединенными объектами
                node_stats = {
                    "id": node.id,
                    "name": node.name,
                    "location": node.location,
                    "status": node.status,
                    "health_status": node.health_status,
                    "current_users": node.current_users,
                    "max_users": node.max_users,
                    "load_percentage": node.load_percentage
                }
                stats.append(node_stats)
            
            return stats
            
        except Exception as e:
            logger.error("Error getting node load stats", error=str(e))
            return [] 