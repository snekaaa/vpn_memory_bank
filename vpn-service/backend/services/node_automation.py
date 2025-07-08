"""
NodeAutomationService - Автоматизация развертывания VPN нод (Reality Mode)
Расширяет существующий NodeManager с automation capabilities
"""

import structlog
import asyncio
import json
import subprocess
import tempfile
import os
import secrets
import base64
import random
import string
import httpx
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from string import Template
import textwrap

from services.node_manager import NodeManager
from services.node_manager import NodeConfig as NodeManagerConfig
from models.vpn_node import VPNNode, NodeMode

logger = structlog.get_logger(__name__)

class DeploymentMethod(Enum):
    """Методы развертывания ноды"""
    SSH = "ssh"

class DeploymentStatus(Enum):
    """Статусы развертывания"""
    PENDING = "pending"
    DETECTING = "detecting"
    INSTALLING = "installing"
    CONFIGURING = "configuring"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"

class NodeDeploymentConfig:
    """Конфигурация для автоматизированного развертывания ноды (Reality Mode)"""
    
    def __init__(
        self,
        # SSH данные (обязательные)
        ssh_host: str,
        ssh_user: str = "root",
        ssh_password: Optional[str] = None,
        
        # Дополнительные настройки
        name: Optional[str] = None,
        location: Optional[str] = None,
        custom_port: int = 443,
        sni_mask: str = "apple.com",
        auto_add_to_balancer: bool = True,
        random_port: bool = False,
        random_password: bool = False,
        random_slug: bool = False
    ):
        self.ssh_host = ssh_host
        self.ssh_user = ssh_user
        self.ssh_password = ssh_password
        
        # Генерируем уникальное название если не указано
        if name:
            self.name = name
        else:
            # Используем IP + случайный суффикс для уникальности
            ip_suffix = ssh_host.replace('.', '-')
            random_suffix = secrets.token_hex(4)
            self.name = f"Auto-Node-{ip_suffix}-{random_suffix}"
        
        self.location = location or "Auto-detected"
        
        # Порт X3UI панели
        if random_port:
            self.panel_port = random.randint(2001, 4999)
        else:
            self.panel_port = custom_port or 2053
        
        # Пароль X3UI панели
        if random_password:
            self.panel_password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
        else:
            self.panel_password = "admin"
        
        # Слаг (доп путь) панели
        if random_slug:
            self.panel_slug = ''.join(random.choices(string.ascii_lowercase + string.digits, k=12))
        else:
            self.panel_slug = ""
        
        self.custom_port = self.panel_port
        self.sni_mask = sni_mask
        self.auto_add_to_balancer = auto_add_to_balancer
        
        # Reality параметры (генерируются на сервере во время деплоя)
        self.public_key = None
        self.private_key = None
        self.short_id = self._generate_short_id()
        
        # Random настройки
        self.random_port = random_port
        self.random_password = random_password
        self.random_slug = random_slug
    
    def _generate_reality_keys(self) -> tuple[str, str]:
        """Генерация X25519 ключей для Reality через SSH на сервере"""
        # Ключи будут сгенерированы на сервере через SSH команду
        # где уже установлен xray после инсталляции
        return None, None  # Будет заполнено позже через SSH
    
    # УДАЛЕН: старый метод _generate_fallback_keys() генерировал неправильные 44-символьные ключи
    # Теперь используем только RealityKeyGenerator с правильной SSH генерацией
    
    def _generate_short_id(self) -> str:
        """Генерация short ID для Reality"""
        # Short ID должен быть 8 hex символов
        return secrets.token_hex(4)

class DeploymentProgress:
    """Отслеживание прогресса развертывания"""
    
    def __init__(self, deployment_id: str):
        self.deployment_id = deployment_id
        self.status = DeploymentStatus.PENDING
        self.percentage = 0
        self.current_step = ""
        self.logs = []
        self.error = None
        self.start_time = datetime.utcnow()
        self.end_time = None
        self.node_id = None
        self.node_data = None

    def update(self, status: DeploymentStatus, percentage: int, step: str, log_message: str = None):
        """Обновление прогресса"""
        self.status = status
        self.percentage = percentage
        self.current_step = step
        
        if log_message:
            timestamp = datetime.utcnow().strftime("%H:%M:%S")
            self.logs.append(f"[{timestamp}] {log_message}")
        
        if status in [DeploymentStatus.COMPLETED, DeploymentStatus.FAILED]:
            self.end_time = datetime.utcnow()

    def set_error(self, error: str):
        """Установка ошибки"""
        self.error = error
        self.status = DeploymentStatus.FAILED
        self.end_time = datetime.utcnow()
        timestamp = datetime.utcnow().strftime("%H:%M:%S")
        self.logs.append(f"[{timestamp}] ❌ ОШИБКА: {error}")

    def set_completed(self, node: "VPNNode"):
        """Установка успешного завершения"""
        self.status = DeploymentStatus.COMPLETED
        self.end_time = datetime.utcnow()
        self.node_id = node.id
        self.node_data = {
            "id": node.id,
            "name": node.name,
            "x3ui_url": node.x3ui_url,
            "location": node.location
        }
        timestamp = datetime.utcnow().strftime("%H:%M:%S")
        self.logs.append(f"[{timestamp}] ✅ Успешно завершено! Нода добавлена с ID: {node.id}")

    def to_dict(self) -> Dict[str, Any]:
        """Конвертация в dict для API responses"""
        return {
            "deployment_id": self.deployment_id,
            "status": self.status.name,
            "percentage": self.percentage,
            "current_step": self.current_step,
            "logs": self.logs[-50:],  # Последние 50 записей
            "error": self.error,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "node_id": self.node_id,
            "duration_seconds": (
                (self.end_time or datetime.utcnow()) - self.start_time
            ).total_seconds() if self.start_time else 0,
            "node_data": self.node_data
        }

class NodeAutomationService:
    """Сервис автоматизации развертывания VPN нод (Reality Mode)"""
    
    # Глобальный реестр всех деплоев
    _global_deployments: Dict[str, DeploymentProgress] = {}
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.node_manager = NodeManager(db_session)
        self.active_deployments = NodeAutomationService._global_deployments
    
    async def start_automated_deployment(self, config: NodeDeploymentConfig) -> str:
        """Запуск автоматизированного развертывания"""
        deployment_id = f"deploy_{int(datetime.utcnow().timestamp())}_{secrets.token_hex(4)}"
        progress = DeploymentProgress(deployment_id)
        
        self.active_deployments[deployment_id] = progress
        
        # Запускаем развертывание в фоне
        asyncio.create_task(self._execute_deployment(config, progress))
        
        logger.info("Started automated deployment", deployment_id=deployment_id, host=config.ssh_host)
        return deployment_id
    
    async def get_deployment_progress(self, deployment_id: str) -> Optional[Dict[str, Any]]:
        """Получение прогресса развертывания"""
        progress = self.active_deployments.get(deployment_id)
        return progress.to_dict() if progress else None
    
    async def validate_deployment_config(self, config: NodeDeploymentConfig) -> Dict[str, Any]:
        """Валидация конфигурации развертывания"""
        try:
            # Тестируем SSH подключение
            test_result = await self._test_ssh_connection(config)
            
            if test_result["success"]:
                return {
                    "success": True,
                    "message": "SSH подключение успешно установлено",
                    "server_info": test_result.get("server_info", {})
                }
            else:
                return {
                    "success": False,
                    "error": test_result.get("error", "Неизвестная ошибка SSH")
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"Ошибка валидации: {str(e)}"
            }
    
    async def _test_ssh_connection(self, config: NodeDeploymentConfig) -> Dict[str, Any]:
        """Тестирование SSH подключения"""
        logger.info("Testing SSH connection", host=config.ssh_host)
        return await self._run_ssh_command(config, "echo 'SSH connection successful'")
    
    async def _run_ssh_command(self, config: NodeDeploymentConfig, command: str, timeout: int = 60) -> Dict[str, Any]:
        """Унифицированный метод для выполнения SSH команд"""
        ssh_command = [
            "sshpass", "-p", config.ssh_password,
            "ssh",
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            f"{config.ssh_user}@{config.ssh_host}",
            command
        ]
        try:
            process = await asyncio.create_subprocess_exec(
                *ssh_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)

            if process.returncode == 0:
                return {"success": True, "stdout": stdout.decode('utf-8', errors='ignore')}
            else:
                return {"success": False, "error": stderr.decode('utf-8', errors='ignore')}
        except asyncio.TimeoutError:
            return {"success": False, "error": f"Команда превысила таймаут {timeout}с"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _execute_deployment(self, config: NodeDeploymentConfig, progress: DeploymentProgress):
        """Полный цикл развертывания ноды"""
        try:
            # 1. Проверка SSH и сбор информации о системе
            progress.update(DeploymentStatus.DETECTING, 10, "Проверка SSH и окружения")
            env_info = await self._detect_environment(config)
            if not env_info.get("success"):
                raise Exception(f"Ошибка проверки окружения: {env_info.get('error', 'Неизвестная ошибка')}")
            progress.update(DeploymentStatus.DETECTING, 20, "Окружение проверено", f"OS: {env_info.get('os_info', 'N/A')}, Arch: {env_info.get('arch', 'N/A')}")

            # 2. Генерация установочного скрипта
            progress.update(DeploymentStatus.INSTALLING, 30, "Генерация установочного скрипта")
            script_content = await self._generate_installer_script(config, env_info)
            progress.update(DeploymentStatus.INSTALLING, 40, "Скрипт сгенерирован")

            # 3. Выполнение скрипта через SSH
            progress.update(DeploymentStatus.INSTALLING, 50, "Запуск установки X3UI панели")
            success = await self._deploy_via_ssh(config, script_content, progress)
            if not success:
                raise Exception("Ошибка во время выполнения SSH-скрипта")
            progress.update(DeploymentStatus.INSTALLING, 80, "Установка X3UI панели завершена")

            # 4. Генерация Reality ключей на сервере
            progress.update(DeploymentStatus.CONFIGURING, 82, "Генерация Reality ключей на сервере")
            await self._generate_reality_keys_on_server(config, progress)
            progress.update(DeploymentStatus.CONFIGURING, 84, f"Reality ключи сгенерированы: {config.public_key[:20]}...")

            # 5. Получение актуальных данных (порт, слаг) и health check
            progress.update(DeploymentStatus.CONFIGURING, 85, "Получение актуальных данных панели")
            live_xui_config = await self._get_live_xui_config(config, progress)
            
            progress.update(DeploymentStatus.VALIDATING, 90, "Проверка доступности панели")
            await self._health_check_panel(config, live_xui_config, progress)
            
            # 6. Финализация и сохранение ноды в БД
            progress.update(DeploymentStatus.COMPLETED, 95, "Сохранение ноды в базу данных")
            node = await self._finalize_deployment(config, progress, live_xui_config)
            
            if not node:
                raise Exception("Не удалось сохранить ноду в базу данных")

            progress.set_completed(node)
            logger.info("Deployment completed successfully", deployment_id=progress.deployment_id, node_id=node.id)

        except Exception as e:
            error_message = f"Ошибка развертывания: {e}"
            logger.error(error_message, deployment_id=progress.deployment_id, exc_info=True)
            progress.set_error(error_message)
    
    async def _detect_environment(self, config: NodeDeploymentConfig) -> Dict[str, Any]:
        """Определение ОС и архитектуры через SSH"""
        logger.info("Detecting environment", host=config.ssh_host)
        command = "echo 'OS:' $(uname -s) 'ARCH:' $(uname -m)"
        result = await self._run_ssh_command(config, command)

        if not result["success"]:
            return result

        try:
            output = result["stdout"]
            os_info = output.split("OS:")[1].split("ARCH:")[0].strip()
            arch = output.split("ARCH:")[1].strip()
            return {"success": True, "os_info": os_info, "arch": arch}
        except IndexError:
            return {"success": False, "error": f"Не удалось распознать вывод: {output}"}
    
    async def _generate_reality_keys_on_server(self, config: NodeDeploymentConfig, progress: DeploymentProgress):
        """Генерация Reality ключей через улучшенный генератор на сервере"""
        logger.info("Starting Reality key generation via SSH", host=config.ssh_host)
        
        try:
            # Импортируем новый генератор ключей
            from services.reality_key_generator import RealityKeyGenerator
            
            progress.update(DeploymentStatus.CONFIGURING, 82, "Генерация Reality ключей...")
            
            # Сначала пробуем локальную генерацию
            keys = RealityKeyGenerator.generate_keys()
            
            # Если локальная генерация не удалась, используем SSH
            if keys.generation_method == "failed":
                logger.info("Local generation failed, trying SSH generation", host=config.ssh_host)
                progress.update(DeploymentStatus.CONFIGURING, 83, "Локальная генерация не удалась, пробуем SSH...")
                
                keys_result = await RealityKeyGenerator.generate_keys_via_ssh(
                    ssh_host=config.ssh_host,
                    ssh_user=config.ssh_user,
                    ssh_password=config.ssh_password
                )
                
                if keys_result:
                    keys = keys_result
                else:
                    raise Exception("Не удалось сгенерировать Reality ключи ни локально, ни через SSH")
            
            # Валидируем сгенерированные ключи
            if not RealityKeyGenerator.validate_keys(keys.private_key, keys.public_key):
                raise Exception("Сгенерированные ключи не прошли валидацию")
            
            # Сохраняем ключи в config
            config.private_key = keys.private_key
            config.public_key = keys.public_key
            
            logger.info("Reality keys generated successfully", 
                       public_key=keys.public_key[:20] + "...",
                       private_key=keys.private_key[:20] + "...",
                       method=keys.generation_method,
                       host=config.ssh_host)
            
            progress.update(DeploymentStatus.CONFIGURING, 84, 
                          f"Reality ключи сгенерированы ({keys.generation_method}): {keys.public_key[:20]}...")
            return
            
        except Exception as error:
            logger.error("Reality key generation failed completely", error=str(error), host=config.ssh_host)
            progress.set_error(f"Не удалось сгенерировать Reality ключи: {error}")
            raise Exception(f"Критическая ошибка генерации Reality ключей: {error}")
    
    async def _get_live_xui_config(self, config: NodeDeploymentConfig, progress: DeploymentProgress) -> Dict[str, Any]:
        """Получает настройки панели X-UI через команду x-ui setting -show."""
        
        progress.update(DeploymentStatus.CONFIGURING, 86, "Чтение конфигурации панели через x-ui команду")
        
        # Используем команду x-ui setting -show вместо прямого SQL запроса
        settings_result = await self._run_ssh_command(config, "/usr/local/x-ui/x-ui setting -show")
        
        if not settings_result["success"]:
            error_msg = f"Не удалось получить настройки панели: {settings_result.get('error', 'no output')}"
            progress.update(DeploymentStatus.FAILED, 87, "Ошибка чтения настроек", error_msg)
            raise Exception(error_msg)

        settings_output = settings_result.get("stdout", "").strip()
        
        if not settings_output:
            error_msg = "Настройки панели не найдены"
            progress.update(DeploymentStatus.FAILED, 87, "Ошибка: настройки пусты", error_msg)
            raise Exception(error_msg)
        
        # Парсим вывод x-ui setting -show
        port = None
        slug = ""
        
        for line in settings_output.split('\n'):
            line = line.strip()
            if line.startswith('port:'):
                port_str = line.replace('port:', '').strip()
                try:
                    port = int(port_str)
                except ValueError:
                    progress.update(DeploymentStatus.CONFIGURING, 87, f"Неверный формат порта: '{port_str}', используем порт по умолчанию 54321")
                    port = 54321
            elif line.startswith('webBasePath:'):
                slug = line.replace('webBasePath:', '').strip()
        
        # Если порт не найден, используем значение по умолчанию
        if port is None:
            progress.update(DeploymentStatus.CONFIGURING, 87, "Порт не найден в настройках, используем 54321 по умолчанию")
            port = 54321
        
        # Удаляем лидирующий слэш, если он есть, для консистентности
        if slug.startswith('/'):
            slug = slug[1:]

        progress.update(DeploymentStatus.CONFIGURING, 88, f"Панель найдена: порт={port}, slug={slug if slug else 'отсутствует'}")
        return {"port": port, "slug": slug}

    async def _health_check_panel(self, config: NodeDeploymentConfig, live_xui_config: Dict[str, Any], progress: DeploymentProgress):
        """Проверяет доступность панели после установки."""
        port = live_xui_config['port']
        slug = live_xui_config['slug']
        
        # Собираем URL, корректно обрабатывая slug
        base_url = f"http://{config.ssh_host}:{port}"
        
        # ИСПРАВЛЕНИЕ БАГА: Корректная обработка slug
        if slug and slug.strip():
            clean_slug = slug.strip().strip('/')
            login_url = f"{base_url}/{clean_slug}/login"
        else:
            login_url = f"{base_url}/login"

        progress.update(DeploymentStatus.VALIDATING, 91, f"Проверка доступности по URL: {login_url}")

        async with httpx.AsyncClient(verify=False) as client:
            for i in range(10):  # Пробуем 10 раз с задержкой
                try:
                    response = await client.get(login_url, timeout=5)
                    if response.status_code == 200:
                        progress.update(DeploymentStatus.VALIDATING, 94, "Панель успешно ответила", f"Статус код: {response.status_code}")
                        return
                except (httpx.ConnectError, httpx.ReadTimeout) as e:
                    progress.update(DeploymentStatus.VALIDATING, 92, f"Панель еще не доступна, попытка {i+1}/10...", f"Ошибка: {e}")
                    await asyncio.sleep(3) # Ждем 3 секунды перед следующей попыткой
        
        error_msg = "Панель не ответила после установки в течение 30 секунд."
        progress.update(DeploymentStatus.FAILED, 94, "Health check провален", error_msg)
        raise Exception(error_msg)

    async def _generate_installer_script(self, config: NodeDeploymentConfig, env_info: Dict[str, Any]) -> str:
        """Генерация установочного скрипта для X3UI."""
        
        script = textwrap.dedent(f"""
            #!/bin/bash
            set -e
            set -o pipefail

            echo "--- Starting X3UI Panel Installation ---"

            # Принудительно освобождаем apt сразу
            echo "Освобождаем apt принудительно..."
            pkill -f apt-get || true
            pkill -f dpkg || true
            pkill -f unattended-upgrade || true
            sleep 3
            
            # Удаляем все файлы блокировки
            rm -f /var/lib/apt/lists/lock
            rm -f /var/lib/dpkg/lock
            rm -f /var/lib/dpkg/lock-frontend
            rm -f /var/cache/apt/archives/lock
            
            # Настраиваем dpkg и apt
            dpkg --configure -a || true
            
            echo "Обновляем список пакетов..."
            export DEBIAN_FRONTEND=noninteractive
            apt-get update -y
            
            echo "Устанавливаем необходимые пакеты..."
            apt-get install -y curl wget socat sudo unzip

            # Останавливаем существующий X3UI если он запущен
            echo "Останавливаем существующий X3UI..."
            systemctl stop x-ui || true
            systemctl disable x-ui || true
            pkill -f x-ui || true
            sleep 3

            # Загружаем и устанавливаем X3UI напрямую
            echo "Скачиваем 3x-ui..."
            cd /tmp
            
            # Определяем архитектуру
            ARCH=$(uname -m)
            case $ARCH in
                x86_64) ARCH="amd64" ;;
                aarch64) ARCH="arm64" ;;
                *) echo "Неподдерживаемая архитектура: $ARCH"; exit 1 ;;
            esac
            
            # Скачиваем последнюю версию 3x-ui
            curl -L -o 3x-ui.tar.gz "https://github.com/mhsanaei/3x-ui/releases/latest/download/x-ui-linux-$ARCH.tar.gz"
            tar -xzf 3x-ui.tar.gz
            
            # Создаем директории
            mkdir -p /usr/local/x-ui
            mkdir -p /etc/systemd/system
            
            # Удаляем старые файлы если они существуют
            rm -f /usr/local/x-ui/x-ui
            rm -rf /usr/local/x-ui/*
            
            # Копируем файлы
            cp -r x-ui/* /usr/local/x-ui/
            chmod +x /usr/local/x-ui/x-ui
            
            # Создаем символическую ссылку
            ln -sf /usr/local/x-ui/x-ui /usr/local/bin/x-ui
            
            # Создаем systemd service
            cat > /etc/systemd/system/x-ui.service << 'EOF'
[Unit]
Description=x-ui service
Documentation=https://github.com/mhsanaei/3x-ui
After=network.target nss-lookup.target

[Service]
User=root
WorkingDirectory=/usr/local/x-ui
ExecStart=/usr/local/x-ui/x-ui run
Restart=on-failure
RestartPreventExitStatus=1
RestartSec=5s
NoNewPrivileges=true
ReadWritePaths=/usr/local/x-ui

[Install]
WantedBy=multi-user.target
EOF

            echo "--- Installation complete, starting configuration ---"
            
            # Устанавливаем официальный Xray для генерации ключей Reality
            echo "Installing official Xray for Reality key generation..."
            curl -L -o xray.zip 'https://github.com/XTLS/Xray-core/releases/download/v25.6.8/Xray-linux-64.zip'
            unzip -o -q xray.zip
            chmod +x xray
            mv xray /usr/local/bin/
            rm -f xray.zip geoip.dat geosite.dat
            echo "Official Xray installed successfully"
            
            # Включаем и запускаем сервис
            systemctl daemon-reload
            systemctl enable x-ui
            systemctl start x-ui
            
            # Ждем запуска
            sleep 5
            
            # Устанавливаем пароль администратора
            echo "Setting admin password..."
            /usr/local/x-ui/x-ui setting -username admin -password '{config.panel_password}'
            
            # Устанавливаем slug (web base path) если он задан
            echo "Setting web base path (slug)..."
            /usr/local/x-ui/x-ui setting -webBasePath '{config.panel_slug}'
            
            echo "--- Restarting x-ui to apply settings ---"
            systemctl restart x-ui
            
            echo "--- Verifying password change ---"
            sleep 3
            /usr/local/x-ui/x-ui setting -show

            echo "--- Waiting for panel to restart (10 seconds) ---"
            sleep 10

            echo "--- Script finished successfully ---"
            echo ""
            echo "=== X3UI PANEL INFORMATION ==="
            if [ -n "{config.panel_slug}" ]; then
                echo "Panel URL: http://{config.ssh_host}:{config.panel_port}/{config.panel_slug}"
            else
                echo "Panel URL: http://{config.ssh_host}:{config.panel_port}"
            fi
            echo "Username: admin"
            echo "Password: {config.panel_password}"
            echo "Web Base Path: {config.panel_slug}"
            echo "SSH Host: {config.ssh_host}"
            echo "SSH User: {config.ssh_user}"
            echo "=== END PANEL INFORMATION ==="
            echo ""
            
            # Cleanup
            cd /
            rm -rf /tmp/3x-ui.tar.gz /tmp/x-ui
        """)
        
        return script

    async def _deploy_via_ssh(self, config: NodeDeploymentConfig, script_content: str, progress: DeploymentProgress) -> bool:
        """Развертывание через SSH"""
        
        # Создаем временный файл для скрипта
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=".sh") as tmp_script:
            tmp_script.write(script_content)
            local_script_path = tmp_script.name
        
        remote_script_path = f"/tmp/deploy_{secrets.token_hex(8)}.sh"

        try:
            # Копируем скрипт на удаленный сервер
            progress.update(DeploymentStatus.INSTALLING, 55, "Копирование скрипта на сервер")
            scp_command = [
                "sshpass", "-p", config.ssh_password, "scp",
                "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
                local_script_path, f"{config.ssh_user}@{config.ssh_host}:{remote_script_path}"
            ]
            process = await asyncio.create_subprocess_exec(*scp_command, stderr=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE)
            stdout, stderr = await process.communicate()
            if process.returncode != 0:
                error_msg = f"Ошибка копирования скрипта: {stderr.decode()}"
                logger.error("SCP failed", command=" ".join(scp_command), error=error_msg)
                progress.set_error(error_msg)
                return False
            
            # Делаем скрипт исполняемым
            progress.update(DeploymentStatus.INSTALLING, 60, "Установка прав на выполнение скрипта")
            chmod_result = await self._run_ssh_command(config, f"chmod +x {remote_script_path}")
            if not chmod_result["success"]:
                error_msg = f"Ошибка установки прав: {chmod_result.get('error', 'Unknown error')}"
                logger.error("Chmod failed", error=error_msg)
                progress.set_error(error_msg)
                return False

            # Запускаем скрипт
            progress.update(DeploymentStatus.INSTALLING, 65, "Запуск установочного скрипта")
            ssh_command_exec = [
                "sshpass", "-p", config.ssh_password, "ssh",
                "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
                f"{config.ssh_user}@{config.ssh_host}", remote_script_path
            ]
            
            logger.info("Starting SSH script execution", command=" ".join(ssh_command_exec))
            
            process = await asyncio.create_subprocess_exec(
                *ssh_command_exec,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE  # ИЗМЕНЕНИЕ: отдельно логируем stderr
            )

            # Читаем stdout и stderr параллельно
            stdout_lines = []
            stderr_lines = []
            
            async def read_stdout():
                while True:
                    line = await process.stdout.readline()
                    if not line:
                        break
                    decoded_line = line.decode('utf-8', errors='ignore').strip()
                    stdout_lines.append(decoded_line)
                    if decoded_line:  # Только непустые строки
                        progress.update(DeploymentStatus.INSTALLING, 
                                      min(progress.percentage + 1, 80), 
                                      "Выполнение установки...", 
                                      decoded_line)
            
            async def read_stderr():
                while True:
                    line = await process.stderr.readline()
                    if not line:
                        break
                    decoded_line = line.decode('utf-8', errors='ignore').strip()
                    stderr_lines.append(decoded_line)
                    if decoded_line:  # Логируем ошибки
                        logger.warning("SSH script stderr", line=decoded_line)
            
            # Запускаем чтение stdout и stderr параллельно
            await asyncio.gather(read_stdout(), read_stderr())
            await process.wait()
            
            # Детальное логирование результата
            full_stdout = "\n".join(stdout_lines)
            full_stderr = "\n".join(stderr_lines)
            
            logger.info("SSH script execution completed", 
                       returncode=process.returncode,
                       stdout_length=len(full_stdout),
                       stderr_length=len(full_stderr))
            
            if process.returncode != 0:
                error_msg = f"Скрипт установки завершился с ошибкой (код: {process.returncode})"
                if full_stderr:
                    error_msg += f"\nОшибки: {full_stderr}"
                if full_stdout:
                    error_msg += f"\nВывод: {full_stdout[-1000:]}"  # Последние 1000 символов вывода
                
                logger.error("SSH script failed", 
                           returncode=process.returncode,
                           stderr=full_stderr,
                           stdout_tail=full_stdout[-500:] if full_stdout else "")
                
                progress.set_error(error_msg)
                return False

            progress.update(DeploymentStatus.INSTALLING, 79, "Установочный скрипт выполнен")
            logger.info("SSH script succeeded", stdout_lines_count=len(stdout_lines))
            return True

        except Exception as e:
            error_msg = f"Исключение при выполнении SSH: {str(e)}"
            logger.error("SSH deployment exception", error=str(e), exc_info=True)
            progress.set_error(error_msg)
            return False
        finally:
            # Удаляем временные файлы
            try:
                os.remove(local_script_path)
                await self._run_ssh_command(config, f"rm -f {remote_script_path}")
            except Exception as cleanup_error:
                logger.warning("Cleanup error", error=str(cleanup_error))

    async def _get_actual_password(self, config: NodeDeploymentConfig) -> str:
        """Получает реальный пароль панели X-UI"""
        # Сначала проверяем заданный пароль
        try:
            result = await self._run_ssh_command(config, "/usr/local/x-ui/x-ui setting -show")
            if result.get("success"):
                output = result.get("stdout", "")
                # Ищем строку с паролем
                for line in output.split('\n'):
                    if line.startswith('password:'):
                        actual_password = line.replace('password:', '').strip()
                        return actual_password
        except Exception:
            pass
        
        # Если не удалось получить, возвращаем заданный
        return config.panel_password

    async def _finalize_deployment(
        self, 
        config: NodeDeploymentConfig, 
        progress: DeploymentProgress,
        live_xui_config: Dict[str, Any]
    ) -> Optional[VPNNode]:
        """Финализация развертывания и сохранение в БД"""
        
        port = live_xui_config['port']
        slug = live_xui_config['slug']

        # Собираем URL, корректно обрабатывая slug
        base_url = f"http://{config.ssh_host}:{port}"
        
        # ИСПРАВЛЕНИЕ БАГА: Корректная обработка slug без повреждения http://
        if slug and slug.strip():
            # Убираем лидирующие и завершающие слэши из slug
            clean_slug = slug.strip().strip('/')
            api_url = f"{base_url}/{clean_slug}"
        else:
            api_url = base_url

        # Получаем реальный пароль панели
        progress.update(DeploymentStatus.CONFIGURING, 95, "Получение реального пароля панели")
        actual_password = await self._get_actual_password(config)
        progress.update(DeploymentStatus.CONFIGURING, 96, f"Используется пароль для подключения: {actual_password}")

        # Создаем конфигурацию для NodeManager  
        node_manager_config = NodeManagerConfig(
            name=config.name,
            x3ui_url=api_url,
            x3ui_username="admin",
            x3ui_password=actual_password,  # Используем реальный пароль
            location=config.location,
            description=f"Auto-deployed Reality node via SSH on {config.ssh_host}"
        )
        
        # Добавляем в модель VPNNode специфичные для Reality поля
        node_data_for_creation = {
            "mode": NodeMode.reality,
            "public_key": config.public_key,
            "short_id": config.short_id,
            "sni_mask": config.sni_mask
        }

        try:
            progress.update(DeploymentStatus.COMPLETED, 98, "Добавление ноды в базу данных через NodeManager")
            
            # Используем node_manager для создания ноды, передавая доп. параметры
            new_node = await self.node_manager.create_node(
                node_manager_config, 
                **node_data_for_creation
            )
            
            if not new_node:
                raise Exception("NodeManager.create_node вернул None")

            progress.update(DeploymentStatus.COMPLETED, 99, f"Нода создана с ID {new_node.id}. Создаю Reality inbound...")
            
            # Создаем Reality inbound через универсальный сервис С ПРАВИЛЬНЫМИ КЛЮЧАМИ
            try:
                from services.reality_inbound_service import RealityInboundService
                
                logger.info("Creating Reality inbound with generated keys", 
                           public_key=config.public_key[:20] + "...",
                           private_key=config.private_key[:20] + "...")
                
                inbound_created = await RealityInboundService.create_reality_inbound(
                    node=new_node,
                    port=443,  # ВСЕГДА используем порт 443 для маскировки под HTTPS
                    sni_mask=config.sni_mask,
                    remark=f"Auto-Reality-{config.name}",
                    private_key=config.private_key,  # ПЕРЕДАЕМ СГЕНЕРИРОВАННЫЙ ПРИВАТНЫЙ КЛЮЧ
                    public_key=config.public_key     # ПЕРЕДАЕМ СГЕНЕРИРОВАННЫЙ ПУБЛИЧНЫЙ КЛЮЧ
                )
                
                if inbound_created:
                    progress.update(DeploymentStatus.COMPLETED, 100, f"Нода {new_node.id} успешно развернута с Reality inbound")
                else:
                    progress.update(DeploymentStatus.COMPLETED, 100, f"Нода {new_node.id} создана, но Reality inbound не удалось создать")
                    
            except Exception as e:
                logger.error("Error creating Reality inbound via universal service", 
                           node_id=new_node.id, 
                           error=str(e))
                progress.update(DeploymentStatus.COMPLETED, 100, f"Нода {new_node.id} создана, но ошибка при создании Reality inbound")
            
            return new_node
        except Exception as e:
            error_msg = f"Критическая ошибка при сохранении ноды в БД: {e}"
            logger.error(error_msg, exc_info=True)
            progress.set_error(error_msg)
            return None

# Старый метод _create_reality_inbound удален - заменен универсальным RealityInboundService 