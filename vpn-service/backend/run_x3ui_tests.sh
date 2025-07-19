#!/bin/bash

# Скрипт для запуска тестов API 3xUI панели
# Убедитесь что настроили URL панели в test_x3ui_api_methods.py

echo "🚀 Starting X3UI API Tests"
echo "========================="

# Проверяем что мы в правильной директории
if [ ! -f "test_x3ui_api_methods.py" ]; then
    echo "❌ Error: test_x3ui_api_methods.py not found"
    echo "Please run this script from vpn-service/backend/ directory"
    exit 1
fi

# Проверяем Python зависимости
echo "🔍 Checking Python environment..."
python3 -c "import asyncio, aiohttp, structlog" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ Error: Missing Python dependencies"
    echo "Please install: pip install asyncio aiohttp structlog"
    exit 1
fi

echo "✅ Python environment OK"

# Запускаем тесты
echo ""
echo "⚠️  IMPORTANT NOTES:"
echo "1. Make sure to configure real X3UI panel URL in test_x3ui_api_methods.py"
echo "2. This test will create and delete test clients on your panel"
echo "3. Make sure the panel is accessible and credentials are correct"
echo ""

read -p "Continue with testing? (y/N): " response
if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    echo ""
    echo "🧪 Running X3UI API Tests..."
    echo "========================="
    
    python3 test_x3ui_api_methods.py
    
    # Проверяем код возврата
    if [ $? -eq 0 ]; then
        echo ""
        echo "✅ Tests completed successfully!"
        echo ""
        echo "📋 Next steps:"
        echo "1. Review test results above"
        echo "2. If all tests passed, proceed to VPNAccessControlService implementation"
        echo "3. If tests failed, fix API issues before continuing"
    else
        echo ""
        echo "❌ Tests failed or were interrupted"
        echo ""
        echo "🔧 Troubleshooting:"
        echo "1. Check X3UI panel URL and credentials"
        echo "2. Verify panel is running and accessible"
        echo "3. Check network connectivity"
        echo "4. Review error messages above"
    fi
else
    echo "Testing cancelled."
    exit 0
fi 