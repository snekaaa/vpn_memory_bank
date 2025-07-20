"""
CountryService - сервис для управления странами VPN серверов
"""

import json
import os
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from models.country import Country
from models.vpn_node import VPNNode
import structlog

logger = structlog.get_logger(__name__)


class CountryService:
    """Сервис для управления странами VPN серверов"""
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
    
    async def get_available_countries(self) -> List[Country]:
        """Получить список активных стран с доступными нодами"""
        try:
            # Получаем активные страны, у которых есть хотя бы одна активная нода
            query = select(Country).where(
                and_(
                    Country.is_active == True,
                    Country.id.in_(
                        select(VPNNode.country_id).where(
                            and_(
                                VPNNode.country_id.isnot(None),
                                VPNNode.status == "active"
                            )
                        )
                    )
                )
            ).order_by(Country.priority.desc())
            
            result = await self.db.execute(query)
            countries = result.scalars().all()
            
            logger.info("Retrieved available countries", count=len(countries))
            return list(countries)
            
        except Exception as e:
            logger.error("Failed to get available countries", error=str(e))
            return []
    
    async def get_nodes_by_country(self, country_id: int) -> List[VPNNode]:
        """Получить все активные ноды для указанной страны"""
        try:
            query = select(VPNNode).where(
                and_(
                    VPNNode.country_id == country_id,
                    VPNNode.status == "active"
                )
            ).order_by(VPNNode.priority.desc())
            
            result = await self.db.execute(query)
            nodes = result.scalars().all()
            
            logger.info("Retrieved nodes for country", country_id=country_id, count=len(nodes))
            return list(nodes)
            
        except Exception as e:
            logger.error("Failed to get nodes by country", country_id=country_id, error=str(e))
            return []
    
    async def get_country_by_code(self, code: str) -> Optional[Country]:
        """Получить страну по ISO коду"""
        try:
            query = select(Country).where(Country.code == code.upper())
            result = await self.db.execute(query)
            country = result.scalar_one_or_none()
            
            if country:
                logger.info("Retrieved country by code", code=code, country_id=country.id)
            else:
                logger.warning("Country not found by code", code=code)
            
            return country
            
        except Exception as e:
            logger.error("Failed to get country by code", code=code, error=str(e))
            return None
    
    async def get_country_by_id(self, country_id: int) -> Optional[Country]:
        """Получить страну по ID"""
        try:
            query = select(Country).where(Country.id == country_id)
            result = await self.db.execute(query)
            country = result.scalar_one_or_none()
            
            if country:
                logger.info("Retrieved country by ID", country_id=country_id)
            else:
                logger.warning("Country not found by ID", country_id=country_id)
            
            return country
            
        except Exception as e:
            logger.error("Failed to get country by ID", country_id=country_id, error=str(e))
            return None
    
    async def validate_country_availability(self, country_id: int) -> bool:
        """Проверить, есть ли у страны доступные здоровые ноды"""
        try:
            query = select(VPNNode).where(
                and_(
                    VPNNode.country_id == country_id,
                    VPNNode.status == "active",
                    VPNNode.health_status == "healthy"
                )
            )
            
            result = await self.db.execute(query)
            nodes = result.scalars().all()
            
            # Проверяем, есть ли ноды с доступной capacity
            available_nodes = [node for node in nodes if node.can_accept_users]
            is_available = len(available_nodes) > 0
            
            logger.info("Validated country availability", 
                       country_id=country_id, 
                       total_nodes=len(nodes),
                       available_nodes=len(available_nodes),
                       is_available=is_available)
            
            return is_available
            
        except Exception as e:
            logger.error("Failed to validate country availability", country_id=country_id, error=str(e))
            return False
    
    async def seed_initial_countries(self, force_reload: bool = False) -> bool:
        """Заполнить таблицу стран начальными данными"""
        try:
            # Проверяем, есть ли уже данные
            if not force_reload:
                query = select(Country)
                result = await self.db.execute(query)
                existing_countries = result.scalars().all()
                
                if existing_countries:
                    logger.info("Countries already exist, skipping seed", count=len(existing_countries))
                    return True
            
            # Загружаем данные из файла
            countries_file = os.path.join(os.path.dirname(__file__), "../data/countries_seed.json")
            
            if not os.path.exists(countries_file):
                logger.error("Countries seed file not found", file=countries_file)
                return False
            
            with open(countries_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            countries_data = data.get("countries", [])
            
            for country_data in countries_data:
                # Проверяем, существует ли страна
                existing = await self.get_country_by_code(country_data["code"])
                
                if not existing:
                    country = Country(
                        code=country_data["code"],
                        name=country_data["name"],
                        name_en=country_data.get("name_en"),
                        flag_emoji=country_data["flag_emoji"],
                        is_active=country_data["is_active"],
                        priority=country_data["priority"]
                    )
                    
                    self.db.add(country)
                    logger.info("Added country", code=country_data["code"], name=country_data["name"])
            
            await self.db.commit()
            logger.info("Successfully seeded countries", count=len(countries_data))
            return True
            
        except Exception as e:
            logger.error("Failed to seed countries", error=str(e))
            await self.db.rollback()
            return False 