# LLM-First Architecture Principles and Anti-Patterns

## Core Philosophy: Trust the LLM's Intelligence

**The fundamental shift from traditional programming to LLM-first architecture is trusting agent reasoning over hardcoded logic.**

### Architectural Philosophy
- **LEVERAGE LLM STRENGTHS**: Use agents for unstructured reasoning, pattern recognition, and context-driven tasks
- **AVOID HARDCODED LOGIC**: Never implement programmatically what an LLM can reason about naturally
- **TRUST AGENT DECISION-MAKING**: Design clear instructions and let agents make intelligent choices
- **EXAMPLE**: Instead of hardcoded fuzzy matching algorithms, load complete datasets into agent context and let the LLM find the best match

## When to Use LLM Agents vs Traditional Code

### USE LLM AGENTS FOR ✅
- **Pattern Matching**: University name variations, fuzzy entity matching, semantic understanding
- **Context-Aware Decisions**: Complex business rules that depend on nuanced understanding
- **Data Interpretation**: Processing unstructured text, understanding user intent, classification
- **Dynamic Workflows**: Decision trees that are too complex to hardcode
- **Natural Language Processing**: Parsing, categorization, sentiment analysis, content generation
- **Tool Orchestration**: Let agents decide which tools to use and when based on context
- **Entity Resolution**: Matching variations to canonical forms (MIT → Massachusetts Institute of Technology)
- **Quality Assessment**: Evaluating completeness, accuracy, relevance of responses
- **Content Enrichment**: Adding context, metadata, related information

### USE TRADITIONAL CODE FOR ⚙️
- **Deterministic Operations**: Date calculations, mathematical operations, field validation
- **Performance-Critical Tasks**: High-frequency operations requiring sub-second response
- **Compliance Requirements**: Operations requiring exact, auditable, repeatable results
- **Simple Conditionals**: Basic if/then logic with clear, unchanging rules
- **Data Structure Management**: ETL operations, schema validation, database operations
- **API Communication**: Request/response handling, authentication, rate limiting
- **Configuration Management**: Environment variables, connection settings, deployment configs

## Natural Tool Integration Hierarchy

### FIRST CHOICE: Single Agent with Natural Tool Access
```python
agent = Agent(model=model, mcp_servers=[...], system_prompt=prompt)
async with agent.run_mcp_servers():
    result = await agent.run(user_query)  # Agent decides tools naturally
```

### SECOND CHOICE: Shared Agent Across Graph Nodes
```python
# Graph nodes use shared agent for natural tool integration
async with shared_agent.run_mcp_servers():
    graph_result = await graph.run(initial_node, state=state)
```

### NEVER: Manual Tool Orchestration or Mock Implementations

## Implementation Patterns

### Data Loading Pattern
```python
# ❌ BAD: Hardcoded fuzzy matching
def find_university(query, universities):
    for uni in universities:
        if fuzzy_match(query, uni.name) > 0.8:
            return uni

# ✅ GOOD: LLM agent with complete data
agent_prompt = f"""
Universities available:
{complete_csv_data}

Find the best match for: {query}
Handle variations like MIT = Massachusetts Institute of Technology naturally.
"""
result = await agent.run(agent_prompt, output_type=UniversityMatch)
```

### Structured Decision Pattern
```python
# ❌ BAD: Hardcoded decision tree
if confidence > 0.8:
    action = "approve"
elif confidence > 0.5:
    action = "review"
else:
    action = "reject"

# ✅ GOOD: Agent decision with structured output
class DecisionResult(BaseModel):
    action: Literal["approve", "review", "reject"]
    reasoning: str
    confidence: float

result = await decision_agent.run(query, output_type=DecisionResult)
```

### Natural Prompting Strategies
```python
# ❌ BAD: Hardcoded tool decision
if "university" in query:
    result = await call_verify_education_tool(query)

# ✅ GOOD: Natural agent reasoning
prompt = f"""
User needs: {query}

Available tools:
- verify_education: For university verification and contact details
- search_knowledge_base: For RMI services and procedures

Analyze the request and use appropriate tools to provide comprehensive response.
"""
result = await agent.run(prompt)
```

## CRITICAL Anti-Patterns (NEVER DO THESE)

### ❌ Tool Integration Anti-Patterns

**NEVER MANUALLY IMPLEMENT TOOL CALLS**
```python
# ❌ WRONG: Manual tool execution
def _execute_tool(tool_name, args):
    if tool_name == "search":
        return mock_search_result()
    
def _call_mcp_tool(tool, params):
    return {"mock": "response"}
```

**NEVER CONSTRAIN AGENT TOOL ACCESS**
```python
# ❌ WRONG: Manual tool orchestration
if input_type == "university":
    tools = ["verify_education"]
else:
    tools = ["search_knowledge_base"]
```

**NEVER CREATE MOCK IMPLEMENTATIONS**
```python
# ❌ WRONG: Mock responses for development
def mock_university_search(query):
    return {"university": "Mock University", "confidence": 0.9}
```

### ✅ CORRECT: Natural Agent Integration
```python
# ✅ RIGHT: Let agents discover and use tools naturally
agent = Agent(model=model, mcp_servers=[eddy_validate, user_chat])
async with agent.run_mcp_servers():
    result = await agent.run(user_query)  # Agent decides everything
```

### ❌ Data Processing Anti-Patterns

**NEVER PRE-FILTER WHEN AGENTS CAN HANDLE COMPLETE DATA**
```python
# ❌ WRONG: Filtering before agent processing
filtered_universities = [u for u in universities if similarity(query, u.name) > 0.3]
result = await agent.run(f"Find match in: {filtered_universities}")

# ✅ RIGHT: Let agent handle complete dataset
result = await agent.run(f"Find best match for '{query}' in: {complete_universities}")
```

**NEVER HARDCODE WHAT AGENTS CAN REASON ABOUT**
```python
# ❌ WRONG: Hardcoded pattern matching
def normalize_university_name(name):
    if "MIT" in name or "Massachusetts Institute" in name:
        return "Massachusetts Institute of Technology"
    # ... hundreds of hardcoded rules

# ✅ RIGHT: Agent reasoning with examples
prompt = f"""
Normalize this university name: {name}
Examples: MIT → Massachusetts Institute of Technology
Handle all variations naturally.
"""
```

### ❌ Decision Logic Anti-Patterns

**NEVER IMPLEMENT COMPLEX CONDITIONALS FOR AGENT DECISIONS**
```python
# ❌ WRONG: Complex business logic
def should_approve_verification(data):
    if data.confidence > 0.8 and data.source in TRUSTED_SOURCES:
        if data.verification_type == "degree" and data.graduation_year > 1990:
            return True
    return False

# ✅ RIGHT: Agent decision with context
class ApprovalResult(BaseModel):
    should_approve: bool
    reasoning: str
    risk_level: Literal["low", "medium", "high"]

result = await approval_agent.run(f"""
Evaluate this verification data: {data}
Consider confidence, source trustworthiness, verification type, and timing.
""", output_type=ApprovalResult)
```

## Structured Output Requirements

### Always Use Pydantic Models
```python
# ✅ Required pattern for all agent interactions
class UniversityVerificationResult(BaseModel):
    university_name: str
    verification_status: Literal["verified", "unverified", "insufficient_data"]
    confidence_score: float
    contact_information: Optional[ContactInfo]
    verification_details: str
    next_steps: List[str]

# Use with agents
result = await agent.run(prompt, output_type=UniversityVerificationResult)
```

### Dependency Injection Pattern
```python
# ✅ Context7 best practices for agent dependencies
@dataclass
class ValidationDependencies:
    database_pool: DatabasePool
    vector_store: VectorStore
    config: AppConfig

agent = Agent[ValidationDependencies, ValidationResult](
    model=model,
    deps=deps,
    system_prompt=prompt
)
```

## Error Handling and Fallback Strategies

### Graceful Degradation
```python
# ✅ Design fallback chains when agents fail
try:
    result = await primary_agent.run(query, output_type=StructuredResult)
    if result.confidence < 0.7:
        result = await fallback_agent.run(enhanced_query, output_type=StructuredResult)
except AgentError:
    result = await simple_search(query)  # Traditional fallback
```

### Confidence-Based Decision Making
```python
# ✅ Use agent-provided confidence for flow control
result = await agent.run(query, output_type=ConfidenceResult)
if result.confidence > 0.8:
    return result.answer
elif result.confidence > 0.5:
    return await human_review_required(result)
else:
    return await escalate_to_expert(query)
```

### Retry Patterns
```python
# ✅ Re-prompt agents with additional context
for attempt in range(3):
    result = await agent.run(prompt, output_type=StructuredResult)
    if result.is_valid():
        return result
    prompt += f"\nPrevious attempt failed: {result.error}. Please retry with more precision."
```

## Multi-Agent Coordination Patterns

### Single Agent for Focused Tasks
Use one agent when domain is narrow and well-defined:
```python
# ✅ University verification specialist
university_agent = Agent(
    model=model,
    mcp_servers=[education_verification_mcp],
    system_prompt="You are an expert at university verification and contact validation."
)
```

### Specialist Agent Delegation
```python
# ✅ Expert agents for specific domains
search_agent = Agent(..., system_prompt="Expert at semantic search and retrieval")
validation_agent = Agent(..., system_prompt="Expert at data validation and verification")
formatting_agent = Agent(..., system_prompt="Expert at response formatting and presentation")
```

### Orchestrator Pattern
```python
# ✅ Main agent coordinates specialists
orchestrator_prompt = f"""
You coordinate specialist agents for complex tasks.
Available specialists: search, validation, formatting
Delegate appropriately based on task requirements.
"""
```

## Testing Agent Behavior

### Behavioral Regression Tests
```python
# ✅ Test agent decision consistency
def test_university_matching_consistency():
    test_cases = [
        ("MIT", "Massachusetts Institute of Technology"),
        ("Harvard", "Harvard University"),
        ("Uni of Melbourne", "University of Melbourne")
    ]
    
    for input_name, expected in test_cases:
        result = await agent.run(f"Normalize: {input_name}")
        assert result.normalized_name == expected
```

### Adversarial Testing
```python
# ✅ Test edge cases and error conditions
edge_cases = [
    "",  # Empty input
    "XYZ University That Doesn't Exist",  # Non-existent
    "Harvard Yale MIT",  # Multiple universities
    "University of 🎓",  # Special characters
]
```

### Output Validation
```python
# ✅ Automate Pydantic schema validation
def test_agent_output_structure():
    result = await agent.run(query, output_type=UniversityResult)
    assert isinstance(result, UniversityResult)
    assert result.confidence >= 0.0 and result.confidence <= 1.0
    assert result.university_name is not None
```

## Real-World LLM-First Examples

### University Name Matching (CSV Search Implementation)
```python
# ❌ OLD APPROACH: Complex vector search with similarity thresholds
vector_results = await vector_search(university_name, threshold=0.5)
if vector_results:
    validation = await validate_university_match(query, vector_results[0])
    if validation.confidence > 0.7:
        return vector_results[0]

# ✅ NEW APPROACH: Load complete CSV, let agent decide
csv_data = load_university_csv()  # Complete dataset
prompt = f"""
Universities available:
{csv_data}

Find the best match for: {university_name}
Handle variations like MIT = Massachusetts Institute of Technology naturally.
"""
result = await csv_query_agent.run(prompt, output_type=CSVQueryResult)
```

### Data Processing and Enrichment
```python
# ❌ BAD: Complex parsing logic
def extract_verification_requirements(text):
    requirements = []
    if "transcript" in text.lower():
        requirements.append("Official Transcript")
    if "degree" in text.lower() and "certificate" in text.lower():
        requirements.append("Degree Certificate")
    # ... more hardcoded rules

# ✅ GOOD: Agent understanding of context
class VerificationRequirements(BaseModel):
    documents: List[str]
    process_steps: List[str]
    estimated_time: str
    special_notes: str

result = await extraction_agent.run(f"""
Extract verification requirements from this university policy text:
{policy_text}

Identify required documents, process steps, timing, and special considerations.
""", output_type=VerificationRequirements)
```

## Development & Debugging Best Practices

### MCP Tool Visibility Requirements
**ALWAYS ensure tool execution visibility for development:**
```python
# ✅ Proper MCP lifecycle management
async with agent.run_mcp_servers():
    result = await agent.run(query)
    # Check terminal output for tool discovery and execution logs
    # Verify real MCP server communication (no mocks)
    # Use result.all_messages() to inspect tool call flow
```

### Red Flags for Constrained Agents
**If you observe any of these, you've constrained the agent:**
- **No tool execution logs** in terminal output
- **Mock or simulated responses** instead of real MCP calls
- **Hardcoded tool selection** based on input parsing
- **Manual tool result formatting** instead of agent processing
- **Missing `run_mcp_servers()` context** in execution flow

### Recovery Patterns
**If you've constrained an agent:**
1. **Identify the constraint** (manual calls, hardcoded decisions, mocks)
2. **Restore natural agent flow** with comprehensive prompts
3. **Verify MCP lifecycle** with `.run_mcp_servers()` wrapper
4. **Test tool visibility** in terminal output
5. **Validate real server communication** (no mocks)

## Success Patterns Summary

✅ **Load complete context**: Give agents full datasets to reason over rather than filtered subsets
✅ **Clear instructions**: Write detailed system prompts that explain the task and expected behavior
✅ **Structured contracts**: Use Pydantic models as clear interfaces between code and agents
✅ **Intelligent delegation**: Let agents choose tools and escalation paths based on context
✅ **Confidence-driven fallbacks**: Build robust fallback chains triggered by agent confidence levels
✅ **Natural tool integration**: Trust agents to discover and use tools appropriately
✅ **Agent-centric design**: Build systems where agents make decisions, not hardcoded logic

**🏗️ LLM-First Architecture transforms traditional programming from rule-based systems to intelligent, context-aware agents that reason naturally about complex problems.**