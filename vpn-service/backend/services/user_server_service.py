"""
UserServerService - сервис для управления назначениями пользователей на VPN серверы
Включает алгоритм выбора оптимального сервера согласно креативной фазе
"""

import time
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update, insert, delete
from sqlalchemy.orm import selectinload

from models.country import Country
from models.vpn_node import VPNNode
from models.user_server_assignment import UserServerAssignment
from models.server_switch_log import ServerSwitchLog
from services.country_service import CountryService
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class NodeSelectionResult:
    """Результат выбора ноды"""
    success: bool
    node: Optional[VPNNode] = None
    error_message: Optional[str] = None
    fallback_used: bool = False
    processing_time_ms: int = 0
    
    @classmethod
    def success_result(cls, node: VPNNode, processing_time_ms: int = 0) -> 'NodeSelectionResult':
        return cls(success=True, node=node, processing_time_ms=processing_time_ms)
    
    @classmethod
    def fallback_result(cls, node: VPNNode, message: str, processing_time_ms: int = 0) -> 'NodeSelectionResult':
        return cls(success=True, node=node, fallback_used=True, 
                  error_message=message, processing_time_ms=processing_time_ms)
    
    @classmethod
    def error_result(cls, message: str, processing_time_ms: int = 0) -> 'NodeSelectionResult':
        return cls(success=False, error_message=message, processing_time_ms=processing_time_ms)


class UserServerService:
    """Сервис для управления назначениями пользователей на серверы"""
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.country_service = CountryService(db_session)
    
    async def get_user_current_assignment(self, user_id: int) -> Optional[UserServerAssignment]:
        """Получить текущее назначение пользователя на сервер"""
        try:
            query = select(UserServerAssignment).where(UserServerAssignment.user_id == user_id)
            result = await self.db.execute(query)
            assignment = result.scalar_one_or_none()
            
            if assignment:
                logger.info("Retrieved user assignment", user_id=user_id, node_id=assignment.node_id)
            
            return assignment
            
        except Exception as e:
            logger.error("Failed to get user assignment", user_id=user_id, error=str(e))
            return None
    
    async def assign_user_to_country(self, user_id: int, country_code: str) -> NodeSelectionResult:
        """Назначить пользователя на оптимальный сервер в указанной стране"""
        start_time = time.time()
        
        try:
            # Получаем страну
            country = await self.country_service.get_country_by_code(country_code)
            if not country:
                return NodeSelectionResult.error_result(f"Country {country_code} not found")
            
            # Выбираем оптимальную ноду
            selection_result = await self.select_optimal_node(country_code, user_id)
            
            if not selection_result.success:
                return selection_result
            
            # Сохраняем назначение
            await self._save_user_assignment(user_id, selection_result.node, country)
            
            # Логируем переключение
            await self._log_server_switch(
                user_id=user_id,
                to_node_id=selection_result.node.id,
                country_code=country_code,
                success=True,
                processing_time_ms=int((time.time() - start_time) * 1000)
            )
            
            processing_time = int((time.time() - start_time) * 1000)
            logger.info("User assigned to country successfully", 
                       user_id=user_id, 
                       country_code=country_code,
                       node_id=selection_result.node.id,
                       processing_time_ms=processing_time)
            
            return NodeSelectionResult.success_result(selection_result.node, processing_time)
            
        except Exception as e:
            error_msg = f"Failed to assign user to country: {str(e)}"
            processing_time = int((time.time() - start_time) * 1000)
            
            # Логируем ошибку
            await self._log_server_switch(
                user_id=user_id,
                to_node_id=None,
                country_code=country_code,
                success=False,
                error_message=error_msg,
                processing_time_ms=processing_time
            )
            
            logger.error("Failed to assign user to country", 
                        user_id=user_id, 
                        country_code=country_code, 
                        error=str(e))
            
            return NodeSelectionResult.error_result(error_msg, processing_time)
    
    async def select_optimal_node(self, country_code: str, user_id: int) -> NodeSelectionResult:
        """
        Выбрать оптимальный VPN node для пользователя в указанной стране
        Использует алгоритм взвешенного выбора на основе нагрузки (из креативной фазы)
        """
        try:
            # Phase 1: Получаем кандидатов
            country = await self.country_service.get_country_by_code(country_code)
            if not country:
                return NodeSelectionResult.error_result("Country not found")
            
            nodes = await self._get_healthy_nodes_by_country(country.id)
            if not nodes:
                return await self._handle_no_nodes_fallback(country_code, user_id)
            
            # Phase 2: Вычисляем оценки и ранжируем ноды
            scored_nodes = []
            for node in nodes:
                score = await self._calculate_enhanced_node_score(node, user_id)
                if score > 0.3:  # Минимальный порог жизнеспособности
                    scored_nodes.append((node, score))
            
            if not scored_nodes:
                return await self._handle_no_viable_nodes_fallback(country_code, user_id)
            
            # Phase 3: Выбираем лучший node
            best_node = max(scored_nodes, key=lambda x: x[1])[0]
            
            # Phase 4: Проверяем доступность
            if await self._verify_node_availability(best_node):
                return NodeSelectionResult.success_result(best_node)
            else:
                return await self._retry_selection_without_node(country_code, user_id, best_node.id)
                
        except Exception as e:
            logger.error("Node selection failed", error=str(e), user_id=user_id, country=country_code)
            return await self._emergency_fallback_selection(user_id)
    
    async def _get_healthy_nodes_by_country(self, country_id: int) -> List[VPNNode]:
        """Получить здоровые ноды для страны"""
        try:
            query = select(VPNNode).where(
                and_(
                    VPNNode.country_id == country_id,
                    VPNNode.status == "active",
                    VPNNode.health_status.in_(["healthy", "unknown"])  # Unknown считаем работоспособным
                )
            ).order_by(VPNNode.priority.desc())
            
            result = await self.db.execute(query)
            nodes = result.scalars().all()
            
            return list(nodes)
            
        except Exception as e:
            logger.error("Failed to get healthy nodes", country_id=country_id, error=str(e))
            return []
    
    async def _calculate_enhanced_node_score(self, node: VPNNode, user_id: int) -> float:
        """
        Вычислить комплексную оценку ноды для выбора
        Диапазон оценки: 0.0 (непригодный) до 1.0 (оптимальный)
        """
        try:
            # Health Check (Binary: 0.0 или 1.0)
            health_ok = await self._check_node_health(node)
            if not health_ok:
                return 0.0
            
            # Capacity Score (0.0 до 1.0)
            if node.current_users >= node.max_users:
                return 0.0  # Нода на пределе capacity
            
            available_ratio = (node.max_users - node.current_users) / node.max_users
            capacity_score = min(1.0, available_ratio * 1.2)  # Легкое предпочтение более доступным
            
            # Performance Score (0.0 до 1.0)
            performance_score = await self._get_node_performance_score(node)
            
            # Priority Score (0.0 до 1.0)
            priority_score = min(1.0, node.priority / 100.0)
            
            # User Affinity Score (0.0 до 1.0)
            affinity_score = await self._get_user_affinity_score(user_id, node.id)
            
            # Взвешенная комбинация (из креативной фазы)
            final_score = (
                capacity_score * 0.50 +      # Capacity самое важное для load balancing
                performance_score * 0.30 +   # Performance влияет на пользовательский опыт
                priority_score * 0.15 +      # Приоритет, определенный админом
                affinity_score * 0.05        # Легкое предпочтение предыдущему серверу
            )
            
            return final_score
            
        except Exception as e:
            logger.error("Failed to calculate node score", node_id=node.id, error=str(e))
            return 0.0
    
    async def _check_node_health(self, node: VPNNode) -> bool:
        """Комплексная проверка здоровья ноды"""
        try:
            # Проверяем статус в БД
            if node.health_status == 'unhealthy':
                return False
            
            # Проверяем свежесть последней проверки здоровья
            if node.last_health_check:
                # ИСПРАВЛЕНИЕ: Используем timezone-aware datetime
                from datetime import timezone
                now = datetime.now(timezone.utc)
                
                # Убеждаемся что last_health_check тоже timezone-aware
                last_check = node.last_health_check
                if last_check.tzinfo is None:
                    # Если timezone не указан, считаем что это UTC
                    last_check = last_check.replace(tzinfo=timezone.utc)
                
                time_since_check = now - last_check
                if time_since_check > timedelta(minutes=10):
                    # Проверка здоровья слишком старая
                    logger.warning("Health check too old", 
                                 node_id=node.id, 
                                 time_since=str(time_since_check),
                                 last_check=last_check.isoformat())
                    # Можно считать такую ноду менее надежной, но не полностью недоступной
                    # TODO: Реализовать perform_live_health_check
            
            # Проверяем время отклика
            if node.response_time_ms and node.response_time_ms > 5000:  # 5 секунд порог
                logger.warning("Node response time too high", 
                             node_id=node.id, 
                             response_time=node.response_time_ms)
                return False
            
            return True
            
        except Exception as e:
            logger.warning("Health check failed", node_id=node.id, error=str(e))
            return False
    
    async def _get_node_performance_score(self, node: VPNNode) -> float:
        """Вычислить оценку производительности на основе времени отклика и нагрузки"""
        try:
            # Компонент времени отклика (0.0 до 1.0)
            if not node.response_time_ms:
                response_score = 0.5  # Неизвестно = нейтрально
            else:
                # Оптимально: <500ms = 1.0, Плохо: >3000ms = 0.1
                if node.response_time_ms <= 500:
                    response_score = 1.0
                elif node.response_time_ms >= 3000:
                    response_score = 0.1
                else:
                    # Линейная интерполяция между 500ms и 3000ms
                    response_score = 1.0 - ((node.response_time_ms - 500) / 2500) * 0.9
            
            # Компонент нагрузки (0.0 до 1.0)
            load_ratio = node.current_users / node.max_users if node.max_users > 0 else 0
            load_score = max(0.1, 1.0 - load_ratio)  # Никогда не опускается ниже 0.1
            
            # Объединенная оценка производительности
            performance_score = (response_score * 0.6 + load_score * 0.4)
            
            return max(0.0, min(1.0, performance_score))
            
        except Exception:
            return 0.5  # Нейтральная оценка при ошибке
    
    async def _get_user_affinity_score(self, user_id: int, node_id: int) -> float:
        """Вычислить оценку пользовательского соответствия ноде на основе истории"""
        try:
            # Проверяем, был ли пользователь ранее назначен на эту ноду
            assignment = await self.get_user_current_assignment(user_id)
            if assignment and assignment.node_id == node_id:
                return 0.8  # Высокое предпочтение текущему серверу
            
            # TODO: Проверить исторические назначения когда будет реализована
            # history = await self.get_user_server_history(user_id, limit=5)
            
            return 0.5  # Нейтрально - нет истории с этой нодой
            
        except Exception:
            return 0.5  # Нейтрально при ошибке
    
    async def _verify_node_availability(self, node: VPNNode) -> bool:
        """Проверить, что нода все еще доступна"""
        # Простая проверка - можно расширить
        return node.can_accept_users
    
    async def _save_user_assignment(self, user_id: int, node: VPNNode, country: Country):
        """Сохранить назначение пользователя на сервер"""
        try:
            # ИСПРАВЛЕНИЕ: Импортируем timezone для timezone-aware datetime
            from datetime import timezone
            now = datetime.now(timezone.utc)
            
            # Простой подход: сначала удаляем старое назначение, потом создаем новое
            # Удаляем существующее назначение пользователя
            delete_stmt = delete(UserServerAssignment).where(
                UserServerAssignment.user_id == user_id
            )
            await self.db.execute(delete_stmt)
            
            # Создаем новое назначение
            new_assignment = UserServerAssignment(
                user_id=user_id,
                node_id=node.id,
                country_id=country.id,
                assigned_at=now,
                last_switch_at=now
            )
            
            self.db.add(new_assignment)
            await self.db.commit()
            
            logger.info("User assignment saved successfully", 
                       user_id=user_id, 
                       node_id=node.id, 
                       country_id=country.id)
            
        except Exception as e:
            logger.error("Failed to save user assignment", 
                        user_id=user_id, node_id=node.id, error=str(e))
            await self.db.rollback()
            raise
    
    async def _log_server_switch(self, user_id: int, to_node_id: Optional[int], 
                                country_code: str, success: bool, 
                                error_message: Optional[str] = None,
                                processing_time_ms: int = 0):
        """Логировать попытку переключения сервера"""
        try:
            # Получаем текущее назначение для from_node_id
            current_assignment = await self.get_user_current_assignment(user_id)
            from_node_id = current_assignment.node_id if current_assignment else None
            
            log_entry = ServerSwitchLog(
                user_id=user_id,
                from_node_id=from_node_id,
                to_node_id=to_node_id,
                country_code=country_code,
                success=success,
                error_message=error_message,
                processing_time_ms=processing_time_ms
            )
            
            self.db.add(log_entry)
            await self.db.commit()
            
        except Exception as e:
            logger.error("Failed to log server switch", user_id=user_id, error=str(e))
            # Не выбрасываем исключение, так как это логирование
    
    # Fallback методы (исправленные версии из креативной фазы)
    async def _handle_no_nodes_fallback(self, country_code: str, user_id: int) -> NodeSelectionResult:
        """Обработать случай, когда нет доступных нод в запрошенной стране"""
        fallback_countries = self._get_fallback_countries(country_code)
        
        for fallback_country in fallback_countries:
            # НЕ ВЫЗЫВАЕМ select_optimal_node рекурсивно - это причина бесконечной рекурсии
            # Вместо этого прямо проверяем ноды в fallback стране
            fallback_country_obj = await self.country_service.get_country_by_code(fallback_country)
            if fallback_country_obj:
                nodes = await self._get_healthy_nodes_by_country(fallback_country_obj.id)
                if nodes:
                    # Выбираем первую доступную ноду из fallback страны
                    for node in nodes:
                        if node.can_accept_users:
                            logger.info("Fallback node selected", 
                                      user_id=user_id, 
                                      original_country=country_code,
                                      fallback_country=fallback_country,
                                      node_id=node.id)
                            return NodeSelectionResult.fallback_result(
                                node, 
                                f"Fallback to {fallback_country}"
                            )
        
        return NodeSelectionResult.error_result("No working nodes available")
    
    async def _handle_no_viable_nodes_fallback(self, country_code: str, user_id: int) -> NodeSelectionResult:
        """Обработать случай, когда нет жизнеспособных нод"""
        # Используем тот же подход без рекурсии
        return await self._handle_no_nodes_fallback(country_code, user_id)
    
    async def _retry_selection_without_node(self, country_code: str, user_id: int, exclude_node_id: int) -> NodeSelectionResult:
        """Повторить выбор, исключив определенную ноду"""
        try:
            # Получаем страну и ноды, исключая проблемную
            country = await self.country_service.get_country_by_code(country_code)
            if not country:
                return NodeSelectionResult.error_result("Country not found in retry")
            
            nodes = await self._get_healthy_nodes_by_country(country.id)
            available_nodes = [node for node in nodes if node.id != exclude_node_id and node.can_accept_users]
            
            if available_nodes:
                # Выбираем первую доступную ноду
                best_node = available_nodes[0]
                logger.info("Retry node selection successful", 
                          user_id=user_id, 
                          excluded_node=exclude_node_id,
                          selected_node=best_node.id)
                return NodeSelectionResult.success_result(best_node)
            
            # Если нет доступных нод, используем fallback
            return await self._handle_no_nodes_fallback(country_code, user_id)
            
        except Exception as e:
            logger.error("Retry selection failed", 
                        user_id=user_id, 
                        exclude_node_id=exclude_node_id, 
                        error=str(e))
            return NodeSelectionResult.error_result(f"Retry failed: {str(e)}")
    
    async def _emergency_fallback_selection(self, user_id: int) -> NodeSelectionResult:
        """Экстренный fallback - любая работающая нода"""
        try:
            query = select(VPNNode).where(
                and_(
                    VPNNode.status == "active",
                    VPNNode.current_users < VPNNode.max_users
                )
            ).limit(1)
            
            result = await self.db.execute(query)
            node = result.scalar_one_or_none()
            
            if node:
                logger.info("Emergency fallback successful", user_id=user_id, node_id=node.id)
                return NodeSelectionResult.fallback_result(
                    node, 
                    "Emergency assignment - system overloaded"
                )
            
            return NodeSelectionResult.error_result("No working nodes available in entire system")
            
        except Exception as e:
            logger.error("Emergency fallback failed", user_id=user_id, error=str(e))
            return NodeSelectionResult.error_result(f"Emergency fallback failed: {str(e)}")
    
    def _get_fallback_countries(self, country_code: str) -> List[str]:
        """Получить предпочитаемые fallback страны для данной страны"""
        fallback_map = {
            "RU": ["DE", "NL"],  # Россия -> Германия -> Нидерланды
            "DE": ["NL", "RU"],  # Германия -> Нидерланды -> Россия  
            "NL": ["DE", "RU"],  # Нидерланды -> Германия -> Россия
        }
        return fallback_map.get(country_code, []) 