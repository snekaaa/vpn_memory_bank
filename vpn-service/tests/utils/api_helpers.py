import httpx
from typing import Dict, Any, Optional

async def make_api_request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    data: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None
) -> httpx.Response:
    """Утилита для выполнения API запросов"""
    if headers is None:
        headers = {"Content-Type": "application/json"}
    
    if method.upper() == "GET":
        response = await client.get(url, headers=headers)
    elif method.upper() == "POST":
        response = await client.post(url, json=data, headers=headers)
    elif method.upper() == "PUT":
        response = await client.put(url, json=data, headers=headers)
    elif method.upper() == "DELETE":
        response = await client.delete(url, headers=headers)
    else:
        raise ValueError(f"Unsupported HTTP method: {method}")
    
    return response

def validate_api_response(response: httpx.Response, expected_status: int = 200) -> Dict[str, Any]:
    """Утилита для валидации API ответов"""
    assert response.status_code == expected_status, f"Expected {expected_status}, got {response.status_code}"
    
    try:
        data = response.json()
    except Exception as e:
        raise AssertionError(f"Response is not valid JSON: {e}")
    
    return data

def validate_success_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """Утилита для валидации успешных ответов"""
    assert "success" in data, "Response missing 'success' field"
    assert data["success"] is True, f"Expected success=True, got {data['success']}"
    assert "data" in data, "Response missing 'data' field"
    
    return data["data"] 