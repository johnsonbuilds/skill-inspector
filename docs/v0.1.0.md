# Skill Inspector

## Vision

Skill Inspector is a CLI tool that helps users understand what their AI agents are actually learning.

Modern agents such as Hermes generate large numbers of assets and store them as "skills".

However, many of these assets are not executable skills. They may actually be:

* Knowledge
* Workflows
* User Preferences
* Reference Materials
* Executable Skills

Skill Inspector analyzes these assets, classifies them, detects duplication, and generates governance recommendations.

The long-term goal is to become the observability and governance layer for AI-generated assets.

---

# Design Principles

## Principle 1: Read-only First

Skill Inspector does not modify user assets.

V1 only:

* Scan
* Analyze
* Report

No automatic changes.

No file modifications.

No deletions.

No merges.

---

## Principle 2: Agent-Agnostic

Skill Inspector must not depend on Hermes internals.

Use adapters.

Future support:

* Hermes
* OpenClaw
* Claude Skills
* Cursor Rules
* Generic Markdown Assets

---

## Principle 3: LLM Optional

V1 must work without any API key.

Classification should be rule-based.

Future versions may optionally use:

* Hermes-configured models
* OpenAI
* Anthropic
* Gemini
* Ollama

---

# High-Level Architecture

┌───────────────────────┐
│ CLI                   │
└──────────┬────────────┘
│
▼
┌───────────────────────┐
│ Adapter Layer         │
└──────────┬────────────┘
│
▼
┌───────────────────────┐
│ Asset Loader          │
└──────────┬────────────┘
│
▼
┌───────────────────────┐
│ Classification Engine │
└──────────┬────────────┘
│
▼
┌───────────────────────┐
│ Similarity Engine     │
└──────────┬────────────┘
│
▼
┌───────────────────────┐
│ Report Generator      │
└───────────────────────┘

---

# Core Concepts

## Asset

Generic representation of an AI-generated artifact.

Fields:

```python
class Asset:
    id: str
    name: str
    path: str
    source: str

    content: str

    metadata: dict

    asset_type: AssetType | None
```

## AssetType

```python
from enum import Enum

class AssetType(Enum):
    KNOWLEDGE = "knowledge"

    WORKFLOW = "workflow"

    EXECUTABLE_SKILL = "executable_skill"

    PREFERENCE = "preference"

    REFERENCE = "reference"

    UNKNOWN = "unknown"
```

---

# Adapter System

## Base Adapter

```python
class BaseAdapter:

    def discover_assets(self) -> list[Asset]:
        pass
```

---

## Hermes Adapter

Responsibilities:

* Locate ~/.hermes/skills
* Parse SKILL.md
* Extract metadata
* Create Asset objects

```python
class HermesAdapter(BaseAdapter):
    pass
```

---

## Future Adapters

```python
class OpenClawAdapter(BaseAdapter):
    pass

class ClaudeSkillAdapter(BaseAdapter):
    pass

class CursorRuleAdapter(BaseAdapter):
    pass
```

---

# Classification Engine

## V1

Rule-Based

No LLM required.

### Executable Skill Signals

Contains:

* input
* output
* steps
* procedure
* script
* action

Examples:

* deploy application
* create database
* backup system

---

### Knowledge Signals

Contains:

* best practices
* lessons learned
* strategy
* guidelines

Examples:

* growth tactics
* marketing strategy
* debugging notes

---

### Preference Signals

Contains:

* user likes
* writing style
* communication preferences

Examples:

* concise answers
* avoid emojis

---

### Workflow Signals

Contains:

* repeatable process
* multi-step methodology

Examples:

* launch checklist
* content publishing process

---

# Similarity Engine

Purpose:

Detect duplicate or overlapping assets.

V1:

Use:

* TF-IDF
* cosine similarity

Libraries:

```python
scikit-learn
```

Output:

```python
DuplicateCluster:
    asset_a
    asset_b
    score
```

---

# Statistics Engine

Generate:

```python
total_assets

knowledge_count

workflow_count

executable_count

preference_count

reference_count

unknown_count
```

Percentages included.

---

# Report Generator

Output:

report.md

Example:

# Skill Inspector Report

Generated:
2026-06-18

## Asset Distribution

Knowledge: 58%

Workflow: 23%

Preference: 11%

Executable Skill: 8%

## Duplicate Candidates

* growth-marketing
* indie-hacker-growth

Similarity: 84%

## Recommendations

* Merge 4 growth-related assets
* Archive 2 inactive assets

---

# CLI Design

## Scan

```bash
skill-inspector scan
```

Default:

Auto-detect Hermes.

---

## Explicit Path

```bash
skill-inspector scan ~/.hermes/skills
```

---

## Generate Report

```bash
skill-inspector report
```

---

## Show Asset Types

```bash
skill-inspector classify
```

---

## Detect Duplicates

```bash
skill-inspector duplicates
```

---

# Project Structure

skill_inspector/

├── cli.py

├── adapters/

│   ├── base.py

│   └── hermes.py

├── models/

│   ├── asset.py

│   └── asset_type.py

├── classifiers/

│   └── rules.py

├── similarity/

│   └── tfidf.py

├── reporting/

│   └── markdown.py

├── scanners/

│   └── loader.py

└── tests/

---

# Dependencies

Core:

```bash
typer
pydantic
pyyaml
rich
markdown
```

Similarity:

```bash
scikit-learn
```

Optional Future:

```bash
sentence-transformers
openai
anthropic
```

---

# Roadmap

## v0.1

* Hermes Adapter
* Asset Loader
* Rule Classifier
* Markdown Report

## v0.2

* Duplicate Detection
* Similarity Scoring

## v0.3

* LLM Classification
* Hermes Config Integration

## v0.4

* Governance Recommendations

## v0.5

* OpenClaw Support
* Claude Skills Support

## v1.0

* Agent Asset Governance Platform
* Web Dashboard
* Asset Health Scores
* Asset Graph Visualization

---

# Success Criteria

The first successful run should answer:

"What is my agent actually learning?"

Example output:

Total Assets: 47

Knowledge: 29
Workflow: 10
Preference: 5
Executable Skills: 3

Duplicate Clusters: 4

Potential Governance Issues:

* Skill inflation detected
* High knowledge-to-skill ratio
* Multiple overlapping growth assets
