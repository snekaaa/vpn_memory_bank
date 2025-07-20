"""
Admin Routes - VPN Node Management
"""

from fastapi import APIRouter, Request, Depends, HTTPException, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any, Optional
from pathlib import Path
import json
from datetime import datetime

from config.database import get_db
from services.node_manager import NodeManager, NodeConfig
from services.load_balancer import LoadBalancer
from services.health_checker import HealthChecker
from services.x3ui_client_pool import X3UIClientPool
from models.vpn_node import VPNNode
from services.node_automation import (
    NodeAutomationService, 
    NodeDeploymentConfig, 
    DeploymentMethod
)

router = APIRouter(prefix="/admin/nodes", tags=["admin"])

# Setup Jinja2 templates
templates = Jinja2Templates(directory=["backend/templates", "backend/app/templates"])

@router.get("/", response_class=HTMLResponse)
async def list_nodes(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Список всех VPN нод"""
    node_manager = NodeManager(db)
    nodes = await node_manager.get_nodes(include_assignments=True)
    
    # Получаем статистику нагрузки
    load_balancer = LoadBalancer(db)
    load_stats = await load_balancer.get_node_load_stats()
    
    # Получаем отчет о здоровье системы
    health_checker = HealthChecker(db)
    health_report = await health_checker.get_health_report()
    
    return templates.TemplateResponse("admin/nodes/list.html", {
        "request": request,
        "nodes": nodes,
        "load_stats": load_stats,
        "health_report": health_report
    })

@router.get("/create", response_class=HTMLResponse)
async def create_node_form(request: Request, db: AsyncSession = Depends(get_db)):
    """Форма создания новой ноды"""
    from sqlalchemy import select
    from models.country import Country
    
    # Получаем все активные страны
    countries_result = await db.execute(
        select(Country).where(Country.is_active == True).order_by(Country.priority.desc())
    )
    countries = countries_result.scalars().all()
    
    return templates.TemplateResponse("admin/nodes/create.html", {
        "request": request,
        "countries": countries
    })

@router.get("/auto/create", response_class=HTMLResponse)
async def create_auto_node_form(request: Request, db: AsyncSession = Depends(get_db)):
    """Форма автоматического создания ноды (уникальный static path)"""
    from sqlalchemy import select
    from models.country import Country
    
    # Получаем все активные страны
    countries_result = await db.execute(
        select(Country).where(Country.is_active == True).order_by(Country.priority.desc())
    )
    countries = countries_result.scalars().all()
    
    return templates.TemplateResponse("admin/nodes/create_auto.html", {
        "request": request,
        "countries": countries
    })

@router.post("/create")
async def create_node(
    request: Request,
    name: str = Form(...),
    x3ui_url: str = Form(...),
    x3ui_username: str = Form(...),
    x3ui_password: str = Form(...),
    description: str = Form(""),
    location: str = Form(""),
    max_users: int = Form(1000),
    priority: int = Form(100),
    weight: float = Form(1.0),
    db: AsyncSession = Depends(get_db)
):
    """Создание новой ноды"""
    from sqlalchemy import select
    from models.country import Country
    
    # Найдем country_id на основе выбранной локации
    country_id = None
    if location:
        country_query = select(Country).where(Country.name == location)
        country_result = await db.execute(country_query)
        country = country_result.scalar_one_or_none()
        if country:
            country_id = country.id
    
    node_manager = NodeManager(db)
    
    node_config = NodeConfig(
        name=name,
        x3ui_url=x3ui_url,
        x3ui_username=x3ui_username,
        x3ui_password=x3ui_password,
        description=description,
        location=location,
        max_users=max_users,
        priority=priority,
        weight=weight,
        country_id=country_id  # Добавляем country_id
    )
    
    new_node = await node_manager.create_node(node_config)
    
    if not new_node:
        return templates.TemplateResponse("admin/nodes/create.html", {
            "request": request,
            "error": "Не удалось создать ноду. Проверьте подключение к X3UI."
        }, status_code=400)
    
    return RedirectResponse(url="/admin/nodes/", status_code=303)

@router.get("/dashboard", response_class=HTMLResponse)
async def nodes_dashboard(
    request: Request,
    node_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db)
):
    """Дашборд мониторинга нод"""
    node_manager = NodeManager(db)
    
    # Если указан node_id, показываем конкретную ноду
    if node_id:
        node = await node_manager.get_node_by_id(node_id)
        if not node:
            raise HTTPException(status_code=404, detail="Нода не найдена")
        
        return templates.TemplateResponse("admin/nodes/node_dashboard.html", {
            "request": request,
            "node": node
        })
    
    # Иначе показываем все ноды
    nodes = await node_manager.get_nodes(include_assignments=True)
    
    # Получаем статистику нагрузки
    load_balancer = LoadBalancer(db)
    load_stats = await load_balancer.get_node_load_stats()
    
    # Получаем отчет о здоровье системы
    health_checker = HealthChecker(db)
    health_report = await health_checker.get_health_report()
    
    return templates.TemplateResponse("admin/nodes/dashboard.html", {
        "request": request,
        "nodes": nodes,
        "load_stats": load_stats,
        "health_report": health_report
    })

@router.post("/rebalance")
async def rebalance_nodes(
    db: AsyncSession = Depends(get_db)
):
    """Ребалансировка пользователей между нодами"""
    load_balancer = LoadBalancer(db)
    result = await load_balancer.rebalance_users()
    return result

@router.post("/health-check")
async def health_check_all_nodes(
    db: AsyncSession = Depends(get_db)
):
    """Проверка здоровья всех нод"""
    health_checker = HealthChecker(db)
    results = await health_checker.check_all_nodes()
    return {"success": True, "results": results}

@router.get("/{node_id:int}", response_class=HTMLResponse)
async def view_node(
    request: Request,
    node_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Просмотр информации о ноде"""
    node_manager = NodeManager(db)
    node = await node_manager.get_node_by_id(node_id)
    
    if not node:
        raise HTTPException(status_code=404, detail="Нода не найдена")
    
    # Получаем статистику ноды
    health_checker = HealthChecker(db)
    node_stats = await health_checker.get_node_stats(node_id)
    
    return templates.TemplateResponse("admin/nodes/view.html", {
        "request": request,
        "node": node,
        "stats": node_stats
    })

@router.get("/{node_id:int}/edit", response_class=HTMLResponse)
async def edit_node_form(
    request: Request,
    node_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Форма редактирования ноды"""
    node_manager = NodeManager(db)
    node = await node_manager.get_node_by_id(node_id)
    
    if not node:
        raise HTTPException(status_code=404, detail="Нода не найдена")
    
    return templates.TemplateResponse("admin/nodes/edit.html", {
        "request": request,
        "node": node
    })

@router.post("/{node_id:int}/edit")
async def edit_node(
    request: Request,
    node_id: int,
    name: str = Form(...),
    x3ui_url: str = Form(...),
    x3ui_username: str = Form(...),
    x3ui_password: str = Form(...),
    description: str = Form(""),
    location: str = Form(""),
    max_users: int = Form(1000),
    priority: int = Form(100),
    weight: float = Form(1.0),
    status: str = Form("active"),
    db: AsyncSession = Depends(get_db)
):
    """Обновление ноды"""
    node_manager = NodeManager(db)
    
    updates = {
        "name": name,
        "x3ui_url": x3ui_url,
        "x3ui_username": x3ui_username,
        "x3ui_password": x3ui_password,
        "description": description,
        "location": location,
        "max_users": max_users,
        "priority": priority,
        "weight": weight,
        "status": status
    }
    
    updated_node = await node_manager.update_node(node_id, updates)
    
    if not updated_node:
        return templates.TemplateResponse("admin/nodes/edit.html", {
            "request": request,
            "error": "Не удалось обновить ноду",
            "node": await node_manager.get_node_by_id(node_id)
        }, status_code=400)
    
    return RedirectResponse(url=f"/admin/nodes/{node_id}", status_code=303)

@router.post("/{node_id:int}/delete")
async def delete_node(
    node_id: int,
    migrate_users: bool = Form(True),
    db: AsyncSession = Depends(get_db)
):
    """Удаление ноды"""
    node_manager = NodeManager(db)
    success = await node_manager.delete_node(node_id, migrate_users)
    
    if not success:
        raise HTTPException(status_code=400, detail="Не удалось удалить ноду")
    
    return RedirectResponse(url="/admin/nodes/", status_code=303)

@router.post("/{node_id:int}/test-connection")
async def test_node_connection(
    node_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Тестирование подключения к ноде"""
    node_manager = NodeManager(db)
    success = await node_manager.test_node_connection(node_id)
    
    return {"success": success}

@router.post("/{node_id:int}/check-health")
async def check_node_health(
    node_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Проверка здоровья ноды"""
    health_checker = HealthChecker(db)
    status = await health_checker.check_node_health(node_id)
    
    return {
        "success": status.is_healthy,
        "response_time_ms": status.response_time_ms,
        "error_message": status.error_message,
        "checked_at": status.checked_at.isoformat()
    }

@router.post("/{node_id:int}/migrate-user")
async def migrate_user(
    node_id: int,
    user_id: int = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """Миграция пользователя на другую ноду"""
    load_balancer = LoadBalancer(db)
    success = await load_balancer.migrate_user(user_id, node_id)
    
    if not success:
        raise HTTPException(status_code=400, detail="Не удалось мигрировать пользователя")
    
    return {"success": True}

@router.post("/{node_id:int}/activate")
async def activate_node(node_id: int, db: AsyncSession = Depends(get_db)):
    node_manager = NodeManager(db)
    updated_node = await node_manager.update_node(node_id, {"status": "active"})
    if not updated_node:
        raise HTTPException(status_code=400, detail="Не удалось активировать ноду")
    return {"success": True}

@router.post("/{node_id:int}/deactivate")
async def deactivate_node(node_id: int, db: AsyncSession = Depends(get_db)):
    node_manager = NodeManager(db)
    updated_node = await node_manager.update_node(node_id, {"status": "inactive"})
    if not updated_node:
        raise HTTPException(status_code=400, detail="Не удалось деактивировать ноду")
    return {"success": True}

@router.post("/api/test-x3ui-connection")
async def test_x3ui_connection_api(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """API endpoint для тестирования X3UI соединения"""
    try:
        data = await request.json()
        
        config = NodeConfig(
            name="Test",
            x3ui_url=data.get("x3ui_url"),
            x3ui_username=data.get("x3ui_username"),
            x3ui_password=data.get("x3ui_password")
        )
        
        node_manager = NodeManager(db)
        result = await node_manager._test_x3ui_connection(config)
        
        return {"success": result}
        
    except Exception as e:
        logger.error("Error testing X3UI connection", error=str(e))
        return {"success": False, "error": str(e)}

@router.post("/api/create-node")
async def create_node_api(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """API endpoint для создания ноды через JSON"""
    try:
        data = await request.json()
        
        node_config = NodeConfig(
            name=data.get("name"),
            x3ui_url=data.get("x3ui_url"),
            x3ui_username=data.get("x3ui_username"),
            x3ui_password=data.get("x3ui_password"),
            description=data.get("description", ""),
            location=data.get("location", ""),
            max_users=data.get("max_users", 1000),
            priority=data.get("priority", 100),
            weight=data.get("weight", 1.0)
        )
        
        node_manager = NodeManager(db)
        new_node = await node_manager.create_node(node_config)
        
        if new_node:
            return {"success": True, "node_id": new_node.id}
        else:
            return {"success": False, "error": "Failed to create node"}
            
    except Exception as e:
        logger.error("Error creating node via API", error=str(e))
        return {"success": False, "error": str(e)}

# ========== AUTOMATION ENDPOINTS ==========

@router.post("/api/auto-deploy")
async def start_auto_deployment(
    request: Request,
    ssh_host: str = Form(...),
    ssh_user: str = Form("root"),
    ssh_password: str = Form(...),
    name: Optional[str] = Form(None),
    location: Optional[str] = Form(None),
    custom_port: int = Form(443),
    sni_mask: str = Form("apple.com"),
    auto_add_to_balancer: bool = Form(True),
    db: AsyncSession = Depends(get_db)
):
    """Запуск автоматического развертывания VPN ноды (Reality Mode)"""
    try:
        automation_service = NodeAutomationService(db)
        
        # Создаем конфигурацию для Reality mode
        config = NodeDeploymentConfig(
            ssh_host=ssh_host,
            ssh_user=ssh_user,
            ssh_password=ssh_password,
            name=name,
            location=location,
            custom_port=custom_port,
            sni_mask=sni_mask,
            auto_add_to_balancer=auto_add_to_balancer
        )
        
        # Запускаем развертывание
        deployment_id = await automation_service.start_automated_deployment(config)
        
        return {
            "success": True,
            "deployment_id": deployment_id,
            "message": "Автоматическое развертывание запущено",
            "config": {
                "host": ssh_host,
                "port": custom_port,
                "public_key": config.public_key,
                "short_id": config.short_id
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Ошибка запуска развертывания: {str(e)}"
        }

@router.get("/api/deployment-progress/{deployment_id}")
async def get_deployment_progress(
    deployment_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Получение прогресса развертывания"""
    try:
        automation_service = NodeAutomationService(db)
        progress = await automation_service.get_deployment_progress(deployment_id)
        
        if progress:
            return {
                "success": True,
                "progress": progress
            }
        else:
            return {
                "success": False,
                "error": "Развертывание не найдено"
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": f"Ошибка получения прогресса: {str(e)}"
        }

@router.post("/api/validate-deployment-config")
async def validate_deployment_config(
    ssh_host: str = Form(...),
    ssh_user: str = Form("root"),
    ssh_password: str = Form(...),
    custom_port: int = Form(443),
    sni_mask: str = Form("apple.com")
):
    """Валидация конфигурации развертывания (тест SSH подключения)"""
    try:
        # Создаем временную конфигурацию для валидации
        config = NodeDeploymentConfig(
            ssh_host=ssh_host,
            ssh_user=ssh_user,
            ssh_password=ssh_password,
            custom_port=custom_port,
            sni_mask=sni_mask
        )
        
        # Создаем временный сервис для валидации (без DB session)
        # В реальной системе можно использовать отдельный валидатор
        automation_service = NodeAutomationService(None)
        result = await automation_service.validate_deployment_config(config)
        
        return result
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Ошибка валидации: {str(e)}"
        } 