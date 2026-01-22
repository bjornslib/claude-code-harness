# Comprehensive Testing Requirements and Validation

## Testing Philosophy

**Test everything you change. Never skip testing. Quality is non-negotiable.**

### Core Testing Principles
1. **Test real functionality** - Never use mock implementations
2. **Test incrementally** - Document processor → Vector store → Agents → Full pipeline
3. **Validate with real data** - Use actual project data and scenarios
4. **Document test results** with specific metrics in task descriptions
5. **Test before marking tasks complete** - No exceptions

## Pre-Testing Requirements

### Environment Validation
```bash
# Verify all services are running
curl -s http://localhost:8000/health || echo "Main orchestrator down"
curl -s http://localhost:5185/health || echo "User chat service down"  
curl -s http://localhost:5184/health || echo "Education verification down"

# Check database connectivity
python -c "import asyncpg; print('Database connectivity OK')"

# Verify Redis connection
redis-cli ping || echo "Redis not available"
```

### Lint and Type Checking (MANDATORY)
```bash
# Run lint checks - must pass before testing
ruff check . || echo "Lint errors found - fix before testing"
ruff format . || echo "Format issues found"

# Run type checking - must pass
mypy . || echo "Type errors found - fix before testing"

# Python-specific checks
black --check . || echo "Code formatting issues"
isort --check-only . || echo "Import sorting issues"
```

## Testing Levels

### 1. Unit Testing

**Test individual components in isolation:**
```python
# Test agent outputs with structured validation
def test_university_agent_output():
    result = await university_agent.run(
        "Find University of Melbourne", 
        output_type=UniversityResult
    )
    assert isinstance(result, UniversityResult)
    assert result.confidence >= 0.0
    assert result.university_name is not None

# Test Pydantic model validation
def test_verification_result_schema():
    result = VerificationResult(
        status="verified",
        confidence=0.95,
        university_name="Harvard University"
    )
    assert result.confidence == 0.95
    assert result.status in ["verified", "unverified", "insufficient_data"]
```

### 2. Integration Testing

**Test component interactions:**
```python
# Test MCP tool integration
async def test_mcp_tool_integration():
    agent = Agent(model=model, mcp_servers=[user_chat_mcp])
    async with agent.run_mcp_servers():
        result = await agent.run("Search for university verification process")
        # Verify tool calls appear in terminal output
        # Verify real MCP communication occurred
        assert result is not None

# Test database integration
async def test_database_operations():
    async with get_database_pool() as pool:
        result = await pool.fetchrow("SELECT * FROM universities LIMIT 1")
        assert result is not None
```

### 3. Service Integration Testing

**Test inter-service communication:**
```python
# Test service coordination
async def test_service_workflow():
    # Test main orchestrator → user chat service
    response = await http_client.post("/api/chat", json={
        "message": "Tell me about university verification"
    })
    assert response.status_code == 200
    
    # Test main orchestrator → education verification
    response = await http_client.post("/api/verify-education", json={
        "university": "Harvard University"
    })
    assert response.status_code == 200
```

### 4. End-to-End Testing

**Test complete user workflows:**
```python
# Test complete verification workflow
async def test_complete_verification_workflow():
    # 1. User submits verification request
    response = await submit_verification_request("MIT", user_data)
    
    # 2. System processes through all services
    verification_id = response["verification_id"]
    
    # 3. Check final result
    result = await get_verification_result(verification_id)
    assert result["status"] in ["verified", "unverified", "pending"]
    assert "university_contacts" in result
```

## Testing Categories by Component

### Vector Search Testing
```python
# Test Enhanced Vector Pipeline
def test_vector_search_accuracy():
    test_cases = [
        ("MIT", "Massachusetts Institute of Technology"),
        ("Uni of Melbourne", "University of Melbourne"),
        ("Massachusets Institute", "Massachusetts Institute of Technology"),  # Misspelling
        ("Harvard", "Harvard University")
    ]
    
    for query, expected in test_cases:
        result = await vector_search_agent.run(query)
        assert result.university_name == expected
        assert result.confidence > 0.8
```

### Agent Behavior Testing
```python
# Test LLM-first architecture patterns
def test_agent_tool_selection():
    # Test that agents choose tools naturally
    result = await orchestrator_agent.run(
        "I need help with university verification"
    )
    # Should have called education verification tools
    tool_calls = extract_tool_calls(result.messages)
    assert any("verify_education" in call for call in tool_calls)

def test_agent_decision_consistency():
    # Test same input produces consistent decisions
    query = "Verify Harvard University degree"
    results = []
    for _ in range(5):
        result = await decision_agent.run(query)
        results.append(result.decision)
    
    # Should be consistent (allowing for minor variations)
    assert len(set(results)) <= 2  # Allow some variation
```

### Redis Streaming Testing
```python
# Test real-time progress updates
async def test_redis_streaming():
    thread_id = "test-thread-123"
    
    # Start workflow that publishes events
    workflow_task = asyncio.create_task(
        run_user_chat_workflow(query="test", thread_id=thread_id)
    )
    
    # Listen for Redis events
    events = []
    async def event_listener():
        async for event in redis_stream_listener(thread_id):
            events.append(event)
            if len(events) >= 3:  # Expected number of events
                break
    
    listener_task = asyncio.create_task(event_listener())
    
    # Wait for completion
    await asyncio.gather(workflow_task, listener_task)
    
    # Verify events were published
    assert len(events) >= 3
    assert any("Aura: 🔍 Searching" in event.message for event in events)
```

## Performance Testing

### Latency Requirements
```python
# Test response time requirements
async def test_response_latency():
    start_time = time.time()
    result = await university_search("Harvard University")
    end_time = time.time()
    
    latency = end_time - start_time
    assert latency < 2.0  # Must respond within 2 seconds
    assert result.confidence > 0.8
```

### Load Testing
```python
# Test concurrent request handling
async def test_concurrent_requests():
    queries = ["MIT", "Harvard", "Stanford", "Yale", "Princeton"]
    tasks = [university_search(query) for query in queries]
    
    start_time = time.time()
    results = await asyncio.gather(*tasks)
    end_time = time.time()
    
    # All should complete successfully
    assert all(r.confidence > 0.5 for r in results)
    
    # Concurrent processing should be faster than sequential
    total_time = end_time - start_time
    assert total_time < len(queries) * 0.5  # Parallelization benefit
```

### Memory Usage Testing
```python
# Test memory efficiency with large datasets
def test_memory_usage():
    import psutil
    process = psutil.Process()
    
    initial_memory = process.memory_info().rss
    
    # Load large dataset
    universities = load_complete_university_dataset()  # 10,000+ universities
    
    # Process with agent
    results = []
    for uni in universities[:100]:  # Test sample
        result = await agent.run(f"Normalize: {uni.name}")
        results.append(result)
    
    final_memory = process.memory_info().rss
    memory_increase = final_memory - initial_memory
    
    # Memory increase should be reasonable (< 500MB for this test)
    assert memory_increase < 500 * 1024 * 1024
```

## Testing Frameworks and Tools

### Pytest Configuration
```python
# conftest.py
import pytest
import asyncio
from pathlib import Path

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
async def test_agent():
    """Provide a test agent with proper configuration."""
    agent = Agent(
        model="claude-3.5-sonnet",
        mcp_servers=[test_mcp_server],
        system_prompt="Test agent for validation"
    )
    async with agent.run_mcp_servers():
        yield agent

@pytest.fixture
async def database_pool():
    """Provide a test database connection pool."""
    pool = await create_database_pool(test_config)
    yield pool
    await pool.close()
```

### Test Data Management
```python
# Test data should be realistic but controlled
TEST_UNIVERSITIES = [
    {"name": "Massachusetts Institute of Technology", "aliases": ["MIT", "M.I.T."]},
    {"name": "Harvard University", "aliases": ["Harvard"]},
    {"name": "University of Melbourne", "aliases": ["UMelb", "Uni of Melbourne"]},
]

@pytest.fixture
def test_university_data():
    return TEST_UNIVERSITIES
```

## Regression Testing

### Behavioral Consistency Testing
```python
# Test that changes don't break existing functionality
def test_university_matching_regression():
    """Ensure university matching still works after changes."""
    test_cases = load_regression_test_cases()
    
    for case in test_cases:
        result = await university_agent.run(case.input)
        assert result.university_name == case.expected_output
        assert result.confidence >= case.minimum_confidence
```

### Performance Regression Testing
```python
def test_performance_regression():
    """Ensure performance hasn't degraded."""
    baseline_metrics = load_baseline_performance()
    
    current_metrics = measure_current_performance()
    
    # Allow 10% degradation tolerance
    for metric_name, baseline_value in baseline_metrics.items():
        current_value = current_metrics[metric_name]
        degradation = (current_value - baseline_value) / baseline_value
        assert degradation < 0.1, f"{metric_name} degraded by {degradation:.2%}"
```

## Testing Quality Gates

### Pre-Commit Testing
```bash
# Required tests before any commit
pytest tests/unit/ -v
pytest tests/integration/ -v  
python test_critical_workflows.py
```

### Pre-Deployment Testing
```bash
# Comprehensive testing before deployment
pytest tests/ -v --coverage=90
python test_end_to_end.py
python test_performance_benchmarks.py
python test_security_validation.py
```

### Continuous Testing
```bash
# Automated testing in CI/CD
pytest tests/ --junitxml=results.xml
python test_monitoring_integration.py
python validate_deployment_health.py
```

## Error Condition Testing

### Edge Case Validation
```python
# Test error handling and edge cases
def test_edge_cases():
    edge_cases = [
        "",  # Empty input
        "   ",  # Whitespace only
        "University of 🎓 Special Characters",
        "A" * 1000,  # Very long input
        "UniversityThatDoesNotExist",
        None,  # Null input
    ]
    
    for case in edge_cases:
        result = await robust_agent.run(case)
        # Should handle gracefully, not crash
        assert result is not None
        assert result.error_handled == True
```

### Network Failure Testing
```python
# Test behavior when external services fail
async def test_service_failure_handling():
    # Simulate database failure
    with mock_database_failure():
        result = await university_search("Harvard")
        assert result.fallback_used == True
        assert result.confidence >= 0.5  # Still provides value
    
    # Simulate Redis failure
    with mock_redis_failure():
        result = await workflow_with_streaming("test query")
        assert result.completed == True  # Graceful degradation
```

## Documentation Testing

### Code Example Validation
```python
# Test that documentation examples actually work
def test_documentation_examples():
    """Ensure code examples in docs are valid."""
    examples = extract_code_examples_from_docs()
    
    for example in examples:
        # Attempt to execute example code
        try:
            exec(example.code)
            assert True  # Executed successfully
        except Exception as e:
            pytest.fail(f"Documentation example failed: {e}")
```

## Test Result Documentation

### Test Metrics Reporting
```python
# Document test results in task descriptions
def generate_test_report(test_results):
    return f"""
Testing Complete:
- Unit Tests: {test_results.unit_tests.passed}/{test_results.unit_tests.total} passed
- Integration Tests: {test_results.integration.passed}/{test_results.integration.total} passed
- Performance: Average latency {test_results.performance.avg_latency:.2f}s
- Coverage: {test_results.coverage:.1%}
- Edge Cases: {test_results.edge_cases.passed}/{test_results.edge_cases.total} handled

Quality Gates: {'✅ PASSED' if test_results.all_passed else '❌ FAILED'}
"""
```

### Task Description Updates
```bash
# Update task with test results
"Update task 42 in Tasks.csv: Description='Implementation complete with comprehensive testing: 95% test coverage, 100% unit tests passed, 95% integration tests passed, average latency 150ms (below 2s target), all edge cases handled gracefully. Quality gates passed, ready for deployment.'"
```

## Command Line Usage

### Use with argument support
```bash
/project:development/testing-protocol unit         # Focus on unit testing
/project:development/testing-protocol integration  # Focus on integration testing  
/project:development/testing-protocol validation   # Focus on validation and quality gates
```

## Integration with Other Commands

### Testing Workflow
```bash
# Complete testing workflow
/project:workflow/processes | /project:development/testing-protocol | /project:workflow/completion-protocol

# Test-driven development
/project:development/testing-protocol unit | /project:development/llm-first-architecture | /project:workflow/completion-protocol
```

**🧪 Comprehensive testing is non-negotiable. Test everything you change, document results, and ensure quality gates pass before marking any task complete.**