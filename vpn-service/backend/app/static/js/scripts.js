// VPN Admin Scripts
console.log('VPN Admin loaded');

// Admin Dashboard Scripts

// Rebalance nodes
document.addEventListener('DOMContentLoaded', function() {
    const rebalanceBtn = document.getElementById('startRebalance');
    if (rebalanceBtn) {
        rebalanceBtn.addEventListener('click', function() {
            fetch('/admin/nodes/rebalance', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            })
            .then(response => response.json())
            .then(data => {
                let modal = bootstrap.Modal.getInstance(document.getElementById('rebalanceModal'));
                modal.hide();
                
                if (data.success) {
                    showAlert('success', 'Ребалансировка успешно запущена!');
                    setTimeout(() => location.reload(), 2000);
                } else {
                    showAlert('danger', 'Ошибка: ' + data.reason);
                }
            });
        });
    }
    
    // Health check
    const healthCheckBtn = document.getElementById('startHealthCheck');
    if (healthCheckBtn) {
        healthCheckBtn.addEventListener('click', function() {
            fetch('/admin/nodes/check-all-health', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            })
            .then(response => response.json())
            .then(data => {
                let modal = bootstrap.Modal.getInstance(document.getElementById('healthCheckModal'));
                modal.hide();
                
                showAlert('success', 'Проверка здоровья запущена для ' + Object.keys(data).length + ' нод!');
                setTimeout(() => location.reload(), 2000);
            });
        });
    }

    // Test node connection
    const testNodeBtns = document.querySelectorAll('.test-node-btn');
    testNodeBtns.forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            const nodeId = this.dataset.nodeId;
            const statusElement = document.getElementById('node-status-' + nodeId);
            
            if (statusElement) {
                statusElement.innerHTML = '<span class="spinner-border spinner-border-sm" role="status"></span> Проверка...';
            }
            
            fetch(`/admin/nodes/${nodeId}/test`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            })
            .then(response => response.json())
            .then(data => {
                if (statusElement) {
                    if (data.success) {
                        statusElement.innerHTML = '<span class="text-success"><i class="bi bi-check-circle"></i> Подключение успешно</span>';
                    } else {
                        statusElement.innerHTML = '<span class="text-danger"><i class="bi bi-x-circle"></i> Ошибка подключения</span>';
                    }
                }
            });
        });
    });

    // Delete node confirmation
    const deleteNodeBtns = document.querySelectorAll('.delete-node-btn');
    deleteNodeBtns.forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            if (confirm('Вы уверены, что хотите удалить эту ноду?')) {
                const nodeId = this.dataset.nodeId;
                const form = document.getElementById('delete-node-form-' + nodeId);
                if (form) {
                    form.submit();
                }
            }
        });
    });
});

// Helper function to show alerts
function showAlert(type, message) {
    const alertContainer = document.getElementById('alert-container');
    if (!alertContainer) return;
    
    const alert = document.createElement('div');
    alert.className = `alert alert-${type} alert-dismissible fade show`;
    alert.role = 'alert';
    alert.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    alertContainer.appendChild(alert);
    
    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        const bsAlert = bootstrap.Alert.getInstance(alert);
        if (bsAlert) {
            bsAlert.close();
        } else {
            alert.remove();
        }
    }, 5000);
}

// Общие функции для админ-панели

document.addEventListener('DOMContentLoaded', function() {
    // Инициализация всплывающих подсказок
    initializeTooltips();
    
    // Обработка кнопок ребалансировки и проверки здоровья
    setupNodeManagementButtons();
    
    // Настройка обработчиков для AJAX запросов
    setupAjaxHandlers();
    
    // Инициализация обработчиков для модальных окон
    setupModalHandlers();
});

// Инициализация всплывающих подсказок Bootstrap
function initializeTooltips() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

// Настройка кнопок управления нодами
function setupNodeManagementButtons() {
    // Кнопка запуска ребалансировки
    const rebalanceButton = document.getElementById('startRebalance');
    if (rebalanceButton) {
        rebalanceButton.addEventListener('click', function() {
            // Показываем индикатор загрузки
            this.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Выполняется...';
            this.disabled = true;
            
            // Отправляем запрос на ребалансировку
            fetch('/admin/nodes/rebalance', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            })
            .then(response => response.json())
            .then(data => {
                // Закрываем модальное окно
                const modal = bootstrap.Modal.getInstance(document.getElementById('rebalanceModal'));
                modal.hide();
                
                // Показываем уведомление
                showNotification(data.success ? 'success' : 'danger', 
                                data.message || 'Ребалансировка выполнена');
                
                // Перезагружаем страницу для обновления данных
                setTimeout(() => {
                    window.location.reload();
                }, 1500);
            })
            .catch(error => {
                console.error('Error:', error);
                showNotification('danger', 'Ошибка при выполнении ребалансировки');
                
                // Восстанавливаем кнопку
                this.innerHTML = 'Запустить';
                this.disabled = false;
            });
        });
    }
    
    // Кнопка проверки здоровья
    const healthCheckButton = document.getElementById('startHealthCheck');
    if (healthCheckButton) {
        healthCheckButton.addEventListener('click', function() {
            // Показываем индикатор загрузки
            this.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Выполняется...';
            this.disabled = true;
            
            // Отправляем запрос на проверку здоровья
            fetch('/admin/nodes/check-all-health', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            })
            .then(response => response.json())
            .then(data => {
                // Закрываем модальное окно
                const modal = bootstrap.Modal.getInstance(document.getElementById('healthCheckModal'));
                modal.hide();
                
                // Показываем уведомление
                showNotification(data.success ? 'success' : 'danger', 
                                data.message || 'Проверка здоровья выполнена');
                
                // Перезагружаем страницу для обновления данных
                setTimeout(() => {
                    window.location.reload();
                }, 1500);
            })
            .catch(error => {
                console.error('Error:', error);
                showNotification('danger', 'Ошибка при выполнении проверки здоровья');
                
                // Восстанавливаем кнопку
                this.innerHTML = 'Запустить';
                this.disabled = false;
            });
        });
    }
}

// Настройка обработчиков AJAX запросов
function setupAjaxHandlers() {
    // Обработка деактивации VPN ключа
    document.querySelectorAll('.deactivate-key-btn').forEach(button => {
        button.addEventListener('click', function() {
            const keyId = this.getAttribute('data-key-id');
            
            fetch(`/admin/api/vpn-keys/${keyId}/deactivate`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                }
            })
            .then(response => response.json())
            .then(data => {
                showNotification('success', 'Ключ деактивирован');
                // Обновляем статус в таблице
                const statusCell = document.querySelector(`#key-${keyId}-status`);
                if (statusCell) {
                    statusCell.innerHTML = '<span class="badge bg-secondary">inactive</span>';
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showNotification('danger', 'Ошибка при деактивации ключа');
            });
        });
    });
    
    // Обработка блокировки/разблокировки пользователя
    document.querySelectorAll('.toggle-user-block-btn').forEach(button => {
        button.addEventListener('click', function() {
            const userId = this.getAttribute('data-user-id');
            const isBlocked = this.getAttribute('data-is-blocked') === 'true';
            
            fetch(`/admin/api/users/${userId}`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    is_blocked: !isBlocked
                })
            })
            .then(response => response.json())
            .then(data => {
                showNotification('success', isBlocked ? 'Пользователь разблокирован' : 'Пользователь заблокирован');
                // Обновляем статус в таблице и кнопку
                const statusCell = document.querySelector(`#user-${userId}-status`);
                if (statusCell) {
                    statusCell.innerHTML = isBlocked 
                        ? '<span class="badge bg-success">активен</span>' 
                        : '<span class="badge bg-danger">заблокирован</span>';
                }
                
                this.setAttribute('data-is-blocked', (!isBlocked).toString());
                this.innerHTML = isBlocked 
                    ? '<i class="bi bi-lock-fill"></i>' 
                    : '<i class="bi bi-unlock-fill"></i>';
                this.title = isBlocked ? 'Заблокировать' : 'Разблокировать';
            })
            .catch(error => {
                console.error('Error:', error);
                showNotification('danger', 'Ошибка при изменении статуса пользователя');
            });
        });
    });
}

// Настройка обработчиков для модальных окон
function setupModalHandlers() {
    // Обработка закрытия модальных окон
    document.querySelectorAll('.modal').forEach(modal => {
        modal.addEventListener('hidden.bs.modal', function() {
            // Сбрасываем состояние кнопок при закрытии модального окна
            const actionButtons = this.querySelectorAll('.btn-primary');
            actionButtons.forEach(button => {
                if (button.getAttribute('data-original-html')) {
                    button.innerHTML = button.getAttribute('data-original-html');
                    button.removeAttribute('data-original-html');
                }
                button.disabled = false;
            });
        });
    });
}

// Функция для отображения уведомлений
function showNotification(type, message) {
    const alertContainer = document.getElementById('alert-container');
    if (!alertContainer) return;
    
    const alertElement = document.createElement('div');
    alertElement.className = `alert alert-${type} alert-dismissible fade show`;
    alertElement.role = 'alert';
    alertElement.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    alertContainer.appendChild(alertElement);
    
    // Автоматическое скрытие уведомления через 5 секунд
    setTimeout(() => {
        const alert = bootstrap.Alert.getOrCreateInstance(alertElement);
        alert.close();
    }, 5000);
} 