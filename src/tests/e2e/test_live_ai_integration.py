"""Integration tests using LocalAI for real prompt testing."""

import pytest
import asyncio
from app.services.local_ai import LocalAI

HTTP_200_OK = 200
HTTP_201_CREATED = 201


@pytest.fixture(scope="session")
async def local_ai(localai_container):
    client = await LocalAI.setup()
    yield client
    await client.close()
    localai_container.stop()


async def simulate_real_browser_task(client, auth_headers, local_ai, task_description: str):
    response = client.post(
        "/api/v1/browsers",
        json={"browser_type": "chrome", "count": 1},
        headers=auth_headers,
    )
    assert response.status_code in (HTTP_200_OK, HTTP_201_CREATED)
    browser_id = response.json()["browser_ids"][0]
    try:
        context = (
            "You are a browser automation assistant. Generate Selenium commands "
            "to accomplish the given task. Use only standard Selenium WebDriver commands."
        )
        ai_response = await local_ai.generate(
            prompt=task_description, context=context, temperature=0.3
        )
        assert any(
            cmd in ai_response.lower() for cmd in ["find_element", "click", "send_keys", "submit"]
        ), f"AI response doesn't contain Selenium commands: {ai_response}"
        command_response = client.post(
            f"/api/v1/browsers/{browser_id}/execute",
            json={"command": ai_response},
            headers=auth_headers,
        )
        assert command_response.status_code == HTTP_200_OK
        return command_response.json()
    finally:
        client.delete(f"/api/v1/browsers/{browser_id}", headers=auth_headers)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_login_automation(client, auth_headers, local_ai):
    result = await simulate_real_browser_task(
        client,
        auth_headers,
        local_ai,
        """Navigate to a login page and:\n1. Find username field\n2. Enter 'testuser'\n3. Find password field\n4. Enter 'testpass'\n5. Click login button""",
    )
    assert result["status"] == "success"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_form_filling(client, auth_headers, local_ai):
    result = await simulate_real_browser_task(
        client,
        auth_headers,
        local_ai,
        """Fill out a contact form with:\n- Name: John Doe\n- Email: john@example.com\n- Message: Hello World\nThen submit the form.""",
    )
    assert result["status"] == "success"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_dynamic_content(client, auth_headers, local_ai):
    result = await simulate_real_browser_task(
        client,
        auth_headers,
        local_ai,
        """Wait for a dynamic element to load:\n1. Wait for element with class 'dynamic-content'\n2. Verify it's visible\n3. Click on it""",
    )
    assert result["status"] == "success"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_complex_workflow(client, auth_headers, local_ai):
    result = await simulate_real_browser_task(
        client,
        auth_headers,
        local_ai,
        """Perform an e-commerce workflow:\n1. Navigate to products page\n2. Filter by category 'Electronics'\n3. Sort by price descending\n4. Add first item to cart\n5. Proceed to checkout""",
    )
    assert result["status"] == "success"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_error_recovery(client, auth_headers, local_ai):
    result = await simulate_real_browser_task(
        client,
        auth_headers,
        local_ai,
        """Handle a potentially missing element:\n1. Try to find an element that might not exist\n2. If not found, use an alternative selector\n3. If still not found, log an error\n4. Continue with the next step""",
    )
    assert result["status"] == "success"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_concurrent_tasks(client, auth_headers, local_ai):
    tasks = [
        simulate_real_browser_task(
            client, auth_headers, local_ai, "Click all pagination buttons one by one"
        ),
        simulate_real_browser_task(
            client, auth_headers, local_ai, "Sort table by different columns"
        ),
    ]
    results = await asyncio.gather(*tasks)
    assert all(r["status"] == "success" for r in results)
