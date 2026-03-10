# Research: Groq gpt-oss-20b Model

## Executive Summary

The **gpt-oss-20b** model (technically 20.9B parameters) is an open-weight large language model developed by OpenAI. It delivers near-parity with OpenAI's o4-mini on core reasoning benchmarks while running efficiently on consumer hardware. When deployed on Groq's LPU (Language Processing Unit), it achieves exceptional inference speeds, making it ideal for latency-sensitive applications.

---

## Technical Specifications

| Parameter | Value |
|-----------|-------|
| Parameters | 20.9B (approximately 21B) |
| Architecture | GPT-style with alternating dense and locally banded sparse attention |
| Context Window | 128,000 tokens (128k) |
| Memory Requirement | ~16GB VRAM (can run on consumer hardware) |
| License | Apache 2.0 (open-weight, deployable) |

---

## Architecture Details

- **Attention Pattern**:Alternating dense and locally banded sparse attention (following GPT-3 approach)
- **Position Embeddings**: Rotary Positional Embeddings (RoPE) with YaRN technique for extended context
- **Attention Implementation**: Grouped-Query Attention (GQA) with 8 keys/values per 64 query heads
- **Optimization**: MoE sparsity combined with optimized attention patterns

The 128k context window enables processing of entire scientific articles or lengthy clinical records in a single input.

---

## Performance Benchmarks

| Benchmark | Score |
|-----------|-------|
| MMLU | 85.3% |
| AIME 2024 | 96% |

---

## Inference Performance on Groq LPU

| Setting | Tokens/Second |
|---------|---------------|
| Groq (high) | 883.3 t/s |
| Groq (medium) | 283 t/s |
| DeepInfra (high) | 101.6 t/s (8.7x slower than Groq) |

Local GPU performance (3090/4090):
- Single 3090: ~160 t/s
- Single 4090: ~160 t/s

The performance drop from Groq's 250+ t/s to ~160 t/s local is considered acceptable for use cases requiring data sovereignty.

---

## Comparison with OpenAI Models

| Model | Relative Performance |
|-------|---------------------|
| gpt-oss-20b ≈ | OpenAI o3-mini |
| gpt-oss-20b near-parity | OpenAI o4-mini |

---

## Key Features

1. **Variable Reasoning Modes**: Groq supports low, medium, and high reasoning modes to balance performance and latency
2. **Open-Weight**: Apache 2.0 licensed for edge deployment
3. **On-Device Capability**: Runs on consumer hardware with 16GB memory
4. **Ultra-Low Latency**: Groq's LPU provides sub-100ms first-token latency
5. **Scalability**: 120B variant runs on single 80GB GPU; 20B variant runs on 16GB devices

---

## Use Cases

- **Edge Deployment**: Ideal for on-device use cases due to low memory footprint
- **Local Inference**: Rapid iteration without costly infrastructure
- **Latency-Sensitive Applications**: Chatbots, real-time reasoning, interactive applications
- **Enterprise**: Local LLM deployment with data sovereignty requirements
- **Content Moderation**: gpt-oss-safeguard-20b variant specialized for content evaluation

---

## API Integration (Groq)

The model is accessible via Groq's API with the following characteristics:

- Model identifier: `gpt-oss-20b`
- Available through OpenAI-compatible API interface
- Multiple reasoning modes configurable via API parameters

---

## References

1. [GroqDocs - GPT-OSS 20B](https://console.groq.com/docs/model/openai/gpt-oss-20b)
2. [Introducing GPT-OSS - OpenAI](https://openai.com/index/introducing-gpt-oss/)
3. [LLM Leaderboard - GPT-OSS-20B](https://llmleaderboard.ai/model/gpt-oss-20b/)
4. [LLM Stats - GPT-OSS 20B](https://llm-stats.com/models/gpt-oss-20b)
5. [IntuitionLabs - GPT-OSS Technical Overview](https://intuitionlabs.ai/articles/openai-gpt-oss-open-weight-models)
6. [Reddit - Benchmarking Groq vs Local](https://www.reddit.com/r/LocalLLaMA/comments/1q8wksa/benchmarking_groq_vs_local_for_gptoss20b_what_tps/)
7. [Artificial Analysis - GPT-OSS-20B Providers](https://artificialanalysis.ai/models/gpt-oss-20b/providers)
8. [DB Reunig - Initial Thoughts on GPT-OSS](https://www.dbreunig.com/2025/08/05/initial-thoughts-on-gpt-oss.html)

---

## Research Date

2026-03-11
