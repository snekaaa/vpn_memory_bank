"""
RealityKeyGenerator - Надежная генерация X25519-ключей для Reality
Использует только правильные методы генерации 43-символьных xray ключей
"""

import structlog
import subprocess
import base64
import asyncio
from typing import Tuple, Optional, Dict
from dataclasses import dataclass

logger = structlog.get_logger(__name__)

@dataclass
class RealityKeys:
    """Класс для хранения Reality ключей"""
    private_key: str
    public_key: str
    generation_method: str  # "xray_local", "xray_ssh", "failed"
    
    def to_dict(self) -> Dict[str, str]:
        return {
            "private_key": self.private_key,
            "public_key": self.public_key,
            "generation_method": self.generation_method
        }

class RealityKeyGenerator:
    """Генератор X25519-ключей для Reality с правильными методами"""
    
    @staticmethod
    def generate_keys() -> RealityKeys:
        """
        Генерация X25519 ключей для Reality:
        1. xray x25519 локально
        2. Если не получилось → ошибка (SSH генерация должна вызываться отдельно)
        """
        
        # Попробовать xray x25519 локально
        keys = RealityKeyGenerator._try_xray_subprocess()
        if keys:
            logger.info("Reality keys generated via local xray", 
                       public_key=keys.public_key[:20] + "...")
            return keys
        
        # Если локальная генерация не удалась
        logger.error("Local xray generation failed - use generate_keys_via_ssh() for remote generation")
        return RealityKeys(
            private_key="",
            public_key="",
            generation_method="failed"
        )
    
    @staticmethod
    async def generate_keys_via_ssh(ssh_host: str, ssh_user: str, ssh_password: str) -> Optional[RealityKeys]:
        """Генерация ключей через SSH на сервере"""
        try:
            logger.info("Generating Reality keys via SSH", host=ssh_host)
            
            # SSH команда для генерации ключей
            ssh_command = [
                "sshpass", "-p", ssh_password, "ssh",
                "-o", "StrictHostKeyChecking=no", 
                "-o", "UserKnownHostsFile=/dev/null",
                "-o", "ConnectTimeout=10",
                f"{ssh_user}@{ssh_host}",
                "xray x25519"
            ]
            
            process = await asyncio.create_subprocess_exec(
                *ssh_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
            
            if process.returncode == 0:
                output = stdout.decode().strip()
                private_key = None
                public_key = None
                
                for line in output.split('\n'):
                    line = line.strip()
                    if line.startswith('Private key:'):
                        private_key = line.split(':', 1)[1].strip()
                    elif line.startswith('Public key:'):
                        public_key = line.split(':', 1)[1].strip()
                
                if private_key and public_key and len(private_key) == 43 and len(public_key) == 43:
                    logger.info("Reality keys generated successfully via SSH",
                               host=ssh_host,
                               public_key=public_key[:20] + "...")
                    return RealityKeys(
                        private_key=private_key,
                        public_key=public_key,
                        generation_method="xray_ssh"
                    )
                else:
                    logger.error("Invalid keys received via SSH",
                               private_len=len(private_key) if private_key else 0,
                               public_len=len(public_key) if public_key else 0)
            else:
                logger.error("SSH xray command failed",
                           returncode=process.returncode,
                           stderr=stderr.decode())
        
        except Exception as e:
            logger.error("SSH key generation failed", error=str(e), host=ssh_host)
        
        return None
    
    @staticmethod
    def _try_xray_subprocess() -> Optional[RealityKeys]:
        """Попытка генерации через локальный xray x25519"""
        try:
            logger.debug("Attempting key generation via local xray")
            
            result = subprocess.run(
                ['xray', 'x25519'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                output = result.stdout.strip()
                private_key = None
                public_key = None
                
                for line in output.split('\n'):
                    line = line.strip()
                    if line.startswith('Private key:'):
                        private_key = line.split(':', 1)[1].strip()
                    elif line.startswith('Public key:'):
                        public_key = line.split(':', 1)[1].strip()
                
                if private_key and public_key:
                    # Валидация длины ключей (xray возвращает 43 символа)
                    if len(private_key) == 43 and len(public_key) == 43:
                        return RealityKeys(
                            private_key=private_key,
                            public_key=public_key,
                            generation_method="xray_local"
                        )
                    else:
                        logger.warning("Invalid key length from local xray",
                                     private_len=len(private_key),
                                     public_len=len(public_key))
            else:
                logger.warning("Local xray x25519 returned non-zero exit code",
                             returncode=result.returncode,
                             stderr=result.stderr)
                
        except FileNotFoundError:
            logger.debug("Local xray binary not found")
        except subprocess.TimeoutExpired:
            logger.warning("Local xray x25519 timeout")
        except Exception as e:
            logger.warning("Local xray subprocess failed", error=str(e))
        
        return None
    
    @staticmethod
    def validate_keys(private_key: str, public_key: str) -> bool:
        """Валидация Reality ключей - ТОЛЬКО 43-символьные xray ключи"""
        if not private_key or not public_key:
            logger.warning("Empty keys provided")
            return False
            
        # xray ключи должны быть ровно 43 символа (НЕ 44!)
        if len(private_key) != 43 or len(public_key) != 43:
            logger.warning("Invalid key length - xray keys must be exactly 43 characters", 
                         private_len=len(private_key),
                         public_len=len(public_key))
            return False
        
        # Проверяем что это валидные URL-safe base64 символы без паддинга
        import string
        valid_chars = string.ascii_letters + string.digits + '-_'
        
        if not all(c in valid_chars for c in private_key):
            logger.warning("Private key contains invalid characters")
            return False
            
        if not all(c in valid_chars for c in public_key):
            logger.warning("Public key contains invalid characters")
            return False
        
        logger.debug("Keys validation passed", 
                    private_len=len(private_key),
                    public_len=len(public_key))
        return True
    
    @staticmethod
    def is_44_char_base64_key(key: str) -> bool:
        """Проверяет является ли ключ старым 44-символьным base64 форматом"""
        if len(key) != 44:
            return False
        if not key.endswith('='):
            return False
        try:
            base64.b64decode(key)
            return True
        except:
            return False
    
    @staticmethod
    def convert_44_to_43_char_key(key_44: str) -> Optional[str]:
        """Конвертирует 44-символьный base64 ключ в 43-символьный xray формат"""
        try:
            if not RealityKeyGenerator.is_44_char_base64_key(key_44):
                return None
            
            # Убираем паддинг '=' и заменяем символы для URL-safe
            key_43 = key_44.rstrip('=').replace('+', '-').replace('/', '_')
            
            if len(key_43) == 43:
                logger.info("Converted 44-char key to 43-char format")
                return key_43
            
        except Exception as e:
            logger.error("Failed to convert key format", error=str(e))
        
        return None 