# Skill Inspector

**Governance for Hermes Skills.**

As AI agents accumulate skills, templates, references, scripts, and knowledge, a new problem emerges:

**Skill Sprawl.**

We have tools to create skills.

We have tools to run agents.

But we don't have tools to understand, audit, and govern skill libraries.

Skill Inspector helps answer:

* What skills does my agent actually have?
* Is my skill library healthy?
* Which skills are becoming too large?
* Are there duplicate or overlapping skills?
* How is knowledge organized inside Hermes?

---

## Features

### Skill Library Health Score

Evaluate the overall health of a Hermes skill library.

Example:

```text
Overall Health: 66 / 100

Structure: 21 / 25
Maintainability: 13 / 25
Reusability: 20 / 25
Duplication: 12 / 25
```

---

### Package Analysis

Analyze Hermes skills as Skill Packages:

```text
Category
  ↓
Skill Package
  ↓
References / Templates / Scripts / Assets
```

Understand:

* Skill distribution
* Category breakdown
* Asset composition
* Package complexity

---

### Risk Detection

Automatically detect:

* Monolithic skill packages
* Reference bloat
* Template bloat
* Script bloat
* Duplicate skill packages
* Category concentration

---

### Governance Recommendations

Generate actionable recommendations:

```text
Split oversized packages

Reduce template bloat

Merge overlapping skills

Improve executable skill coverage
```

---

## Example Findings

A typical report may reveal:

```text
74 Skill Packages

418 Assets

Top Risk Package:
popular-web-designs

54 templates

Health Score:
66 / 100
```

---

## Why Skill Inspector?

As Hermes skill libraries grow, agents accumulate:

* Skills
* References
* Templates
* Scripts
* Assets

Without governance, skill libraries become:

* Difficult to understand
* Hard to maintain
* Redundant
* Less reusable

Skill Inspector provides observability and governance for agent assets.

---

## Installation

```bash
git clone https://github.com/YOUR_GITHUB/skill-inspector.git

cd skill-inspector

pip install -e .
```

---

## Usage

### Package Analysis

```bash
skill-inspector scan-packages
```

Generate a full governance report.

---

### Health Report

```bash
skill-inspector health
```

Generate a health-focused report.

---

## Configuration

By default Skill Inspector reads:

```text
/opt/data/config.yaml
/opt/data/skills/
```

The model configuration is reused directly from Hermes.

Example:

```yaml
model:
  provider: ${LLM_PROVIDER}
  base_url: ${LLM_BASE_URL}
  default: ${LLM_MODEL_ID}
  api_key: ${LLM_API_KEY}
```

---

## Supported Providers

Skill Inspector automatically reuses the model configured for Hermes.

Supported providers:

* OpenAI
* OpenRouter
* Anthropic
* Ollama
* Any OpenAI-compatible API

---

## Architecture

```text
Category
  ↓
Skill Package
  ↓
References
Templates
Scripts
Assets
```

Core modules:

* hermes
* package_classifier
* package_duplicates
* package_report
* health
* governance

---

## Roadmap

### v0.3

* Health Score
* Risk Analysis
* Governance Recommendations

### v0.4

* Improved skill taxonomy
* Better package archetypes
* Enhanced governance rules

### v0.5

* Continuous monitoring
* Historical trend analysis
* Skill governance dashboard

---

## Open Source

Skill Inspector is open source.

Contributions, ideas, bug reports, and governance experiments are welcome.

If you're exploring how AI agents accumulate, organize, and maintain skills over time, we'd love to hear your findings.

---

## About

Skill Inspector was created to explore a simple question:

> As AI agents accumulate hundreds of skills, templates, references, and scripts, how do we keep them understandable, maintainable, and healthy?

The project focuses on **Agent Asset Governance** for Hermes and other agent ecosystems.

---

## License

Apache License 2.0
