# skill-inspector

Skill Inspector audits a Hermes skill library and answers: **"What is my agent actually learning?"**

It is a governance and observability CLI, not a skill generator or skill executor.

## Usage

```bash
skill-inspector scan
```

By default the scanner reads Hermes assets from `/opt/data`:

- `/opt/data/config.yaml`
- `/opt/data/skills/`

The Hermes model configuration is read from `config.yaml` and environment variables are expanded, for example:

```yaml
model:
  provider: ${LLM_PROVIDER}
  base_url: ${LLM_BASE_URL}
  default: ${LLM_MODEL_ID}
  api_key: ${LLM_API_KEY}
```

The scan prints a summary and writes `report.md`.

## Supported providers

Skill Inspector reuses the model configured for Hermes and supports:

- OpenAI-compatible chat APIs, including OpenAI and OpenRouter
- Anthropic Messages API
- Ollama chat API

## Architecture

The MVP is intentionally modular:

- `cli`: command-line entry point
- `hermes`: Hermes configuration and asset adapter
- `llm`: LLM classification and embedding clients
- `duplicates`: cosine-similarity duplicate clustering
- `report`: Markdown report generation
