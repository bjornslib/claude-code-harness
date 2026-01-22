# Research with Colleagues Workflow

## Always Research Implementation Approaches with Colleagues Before Coding

**Use Perplexity and Brave Search as your co-workers to discuss ideas, validate approaches, and discover best practices.**

## Core Research Protocol

### Research-First Principle
1. **ALWAYS research** implementation approaches with colleagues before coding
2. **Check completed tasks** in Tasks.csv for similar implementations  
3. **Validate technical decisions** and best practices with search tools
4. **Research current API changes** and compatibility issues
5. **Discuss architecture choices** and technology selection

## Perplexity Colleague Modes

### Standard Mode - Quick Technical Questions
```python
# Tool: mcp__perplexity-ask__perplexity_ask
# Use for: API research, quick clarifications, specific technical questions

mcp__perplexity-ask__perplexity_ask([{
  "role": "user", 
  "content": "What's the current OpenAI GPT-4.1 model name for API calls in 2025?"
}])
```

### Pro Mode - In-Depth Architecture Discussions  
```python
# Tool: mcp__perplexity-ask__perplexity_research
# Use for: Technology comparisons, architectural decisions, comprehensive analysis

mcp__perplexity-ask__perplexity_research([{
  "role": "user",
  "content": "Compare vector databases for production LLM applications: performance, cost, scalability considerations for 2025"
}])
```

### Deep Research Mode - Complex Technical Analysis
```python  
# Tool: mcp__perplexity-ask__perplexity_reason
# Use for: Complex technical analysis, comprehensive solution design, research synthesis

mcp__perplexity-ask__perplexity_reason([{
  "role": "user", 
  "content": "Analyze optimal architecture patterns for LLM-first applications: agent coordination, tool integration, performance optimization, and production deployment strategies"
}])
```

## Brave Search Colleague

### Web Research for Current Information
```python
# Tool: mcp__brave-search__brave_web_search  
# Use for: Documentation, library updates, current best practices, compatibility

mcp__brave-search__brave_web_search(
  query="React hooks best practices 2025",
  count=10
)

mcp__brave-search__brave_web_search(
  query="Claude Code slash commands project organization 2025", 
  count=8
)
```

### Local Business/Service Research
```python
# Tool: mcp__brave-search__brave_local_search
# Use for: Local services, business information, geographic-specific queries

mcp__brave-search__brave_local_search(
  query="AI/ML consulting services near San Francisco",
  count=5  
)
```

## Research Workflows by Task Type

### Architecture Research
```bash
# 1. Start with Perplexity for technical analysis
"Hey colleague! I'm designing a microservices architecture for an LLM application. What are the current best practices for service communication, data consistency, and deployment patterns in 2025?"

# 2. Follow up with Brave Search for specific tools/frameworks
"microservices communication patterns LLM applications 2025"

# 3. Deep dive with Perplexity for comprehensive analysis
"Analyze the tradeoffs between synchronous vs asynchronous communication patterns in LLM microservices, considering latency, reliability, and complexity factors"
```

### Technology Selection Research
```bash
# 1. Brave Search for current landscape
"Python vector database libraries 2025 performance comparison"

# 2. Perplexity for detailed analysis  
"Compare Pinecone vs Weaviate vs Chroma for production vector search: cost, performance, feature completeness"

# 3. Perplexity Deep Research for comprehensive evaluation
"Comprehensive analysis of vector database selection criteria for LLM applications: technical requirements, operational complexity, scaling considerations, and cost optimization strategies"
```

### Implementation Pattern Research
```bash
# 1. Check completed tasks for internal patterns
"Show completed tasks from Tasks.csv where Description contains 'vector search'"

# 2. Perplexity for best practices
"What are the current best practices for implementing semantic search with BM25 hybrid approaches in Python?"

# 3. Brave Search for specific libraries
"BM25 semantic search hybrid implementation Python 2025"
```

### API Integration Research  
```bash
# 1. Brave Search for current API documentation
"OpenAI GPT-4.1 API documentation 2025"

# 2. Perplexity for integration patterns
"Best practices for OpenAI API integration: error handling, rate limiting, cost optimization"

# 3. Research compatibility and changes
"OpenAI API changes 2025 breaking changes migration guide"
```

## Research Conversation Patterns

### Collaborative Discussion Style
```markdown
"Hey colleague! I'm working on [SPECIFIC_TASK]. I'm considering [APPROACH_A] vs [APPROACH_B]. 

Context: [RELEVANT_PROJECT_DETAILS]
Requirements: [SPECIFIC_NEEDS]
Constraints: [LIMITATIONS]

What's your take on the tradeoffs? Any recent developments or best practices I should consider?"
```

### Technical Validation
```markdown
"I'm planning to implement [TECHNICAL_APPROACH] for [USE_CASE]. 

My reasoning: [YOUR_ANALYSIS]
Concerns: [POTENTIAL_ISSUES]

Does this approach make sense given current 2025 best practices? Any better alternatives or gotchas I should know about?"
```

### Architecture Review
```markdown
"I'm designing a system with these components: [SYSTEM_OVERVIEW]

The key decisions I'm making:
1. [DECISION_1] because [REASONING_1]
2. [DECISION_2] because [REASONING_2]  
3. [DECISION_3] because [REASONING_3]

Can you review this architecture and suggest improvements? Any modern patterns I'm missing?"
```

## Integration with Context7

### Framework-Specific Research
```python
# 1. Resolve library first
mcp__context7__resolve-library-id("react")

# 2. Get documentation  
mcp__context7__get-library-docs(
  context7CompatibleLibraryID="/facebook/react",
  topic="hooks performance optimization"
)

# 3. Validate with colleagues
"Based on React documentation, I'm implementing [APPROACH]. Is this following current React best practices for [USE_CASE]?"
```

## Advanced Research Strategies

### Parallel Research
```bash
# Research same topic with multiple colleagues simultaneously
# Use Claude Code's concurrent execution capabilities

# Perplexity research
mcp__perplexity-ask__perplexity_research([{"role": "user", "content": "LLM agent coordination patterns 2025"}])

# Brave Search research (parallel)
mcp__brave-search__brave_web_search("LLM agent coordination patterns frameworks 2025", count=10)

# Context7 research (parallel)  
mcp__context7__get-library-docs("/anthropic/claude", topic="agent coordination")
```

### Iterative Research Refinement
```bash
# 1. Initial broad research
"What are the current approaches to LLM application architecture?"

# 2. Refine based on findings
"You mentioned agent-centric design. Can you elaborate on tool integration patterns specifically?"

# 3. Deep dive into specifics  
"For the PydanticAI pattern you described, what are the best practices for structured outputs and dependency injection?"
```

### Cross-Reference Validation
```bash
# 1. Research with Perplexity
"Best practices for Redis streaming with Python asyncio applications"

# 2. Validate with Brave Search
"Redis asyncio Python streaming best practices 2025 examples"

# 3. Check Context7 for framework-specific guidance
mcp__context7__get-library-docs("/redis/redis-py", topic="asyncio streaming")

# 4. Synthesize findings
"Based on research from multiple sources, the consensus seems to be [SYNTHESIS]. Does this align with your understanding?"
```

## Research Quality Indicators

### Good Research Questions
✅ **Specific and contextual**: Include your use case and constraints
✅ **Current**: Ask about 2025 best practices and recent developments  
✅ **Comparative**: Ask for tradeoff analysis between options
✅ **Practical**: Focus on implementation guidance and real-world usage
✅ **Validation-seeking**: Ask colleagues to review your approach

### Poor Research Questions  
❌ **Too broad**: "How do I build an AI application?"
❌ **Outdated**: Not specifying current year or version requirements
❌ **Implementation-specific**: Very detailed code questions better suited for documentation
❌ **Closed-ended**: Yes/no questions that don't generate discussion
❌ **Assumption-laden**: Questions that assume a specific approach without exploration

## Command Line Usage

### Use with argument support
```bash
/project:workflow/research-colleagues perplexity  # Focus on Perplexity research patterns
/project:workflow/research-colleagues brave       # Focus on Brave Search workflows  
/project:workflow/research-colleagues both        # Combined research strategies
```

## Research Documentation

### Document Key Insights
When research yields important findings:
1. **Update task Description** with research insights
2. **Add to Planning.md** if architecturally significant
3. **Create memory** via Serena if valuable for future tasks
4. **Share in webhook** if relevant to project stakeholders

### Research-to-Implementation Flow
```bash
# 1. Research phase
"Research approach with colleagues..."

# 2. Document findings
"Update task 42 in Tasks.csv: Description='Research complete: Consensus on BM25+semantic hybrid approach with Cohere reranking based on colleague analysis and 2025 best practices'"

# 3. Implementation phase with validated approach
"Proceeding with implementation using research-validated approach..."
```

**🤝 Treat Perplexity and Brave Search as experienced colleagues - engage them in thoughtful technical discussions before implementing any significant functionality.**