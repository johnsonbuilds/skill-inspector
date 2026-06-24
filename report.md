# Skill Inspector Report (Package-Aware)

## Summary

- **Total Categories**: 19
- **Total Skill Packages**: 70
- **Total Assets**: 415
- **Duplicate Clusters**: 0

## Skill Utilization Summary

Installed Skills: 70

Used Skills: 4

Unused Skills: 66

Utilization Rate: 5.7%

## Library Health Score

**Overall Health: 67 / 100**

- **Structure**: 21 / 25
- **Maintainability**: 13 / 25
- **Reusability**: 21 / 25
- **Duplication**: 12 / 25

## Governance Summary

• Only 5.7% of installed skills have ever been executed.

• 66 skills have never been executed.

• `productivity/powerpoint` is the largest unused package by complexity (135).

• `creative/popular-web-designs` has the lowest health score at 48 / 100.

• Library health is below target at 67 / 100.

## Runtime Governance

### Most Used Skills

Only 4 of 70 installed skills have ever been executed.

| Skill | Uses | Views | Last Used |
| ----- | ---: | ----: | --------- |
| `governance/skill-health-check` | 5 | 5 | 2026-06-24 |
| `creative/wavespeed` | 2 | 2 | 2026-06-17 |
| `dogfood` | 2 | 2 | 2026-06-12 |
| `autonomous-ai-agents/hermes-agent` | 1 | 1 | 2026-06-22 |

### Recently Used Skills

Skills executed within the last 3 days.

| Skill | Last Used |
| ----- | --------- |
| `governance/skill-health-check` | 2026-06-24 |
| `autonomous-ai-agents/hermes-agent` | 2026-06-22 |

### Unused High-Cost Skills

66 installed skills have no recorded executions. The table shows the top 10 by complexity.

| Skill | Category | Complexity | References | Templates | Scripts |
| ----- | -------- | ----------: | ----------: | ---------: | --------: |
| `productivity/powerpoint` | productivity | 135 | 0 | 0 | 44 |
| `creative/popular-web-designs` | creative | 108 | 0 | 54 | 0 |
| `research/research-paper-writing` | research | 99 | 9 | 45 | 0 |
| `creative/comfyui` | creative | 54 | 4 | 0 | 11 |
| `creative/baoyu-infographic` | creative | 46 | 45 | 0 | 0 |
| `creative/p5js` | creative | 25 | 10 | 1 | 4 |
| `creative/touchdesigner-mcp` | creative | 24 | 21 | 0 | 1 |
| `creative/manim-video` | creative | 18 | 14 | 0 | 1 |
| `red-teaming/godmode` | red-teaming | 18 | 2 | 2 | 4 |
| `productivity/google-workspace` | productivity | 13 | 1 | 0 | 4 |

### Category Utilization

15 categories have 0% utilization and are collapsed from the table.

| Category | Utilization | Used / Total |
| -------- | ----------: | ------------ |
| dogfood | 100% | 1 / 1 |
| governance | 100% | 1 / 1 |
| autonomous-ai-agents | 25% | 1 / 4 |
| creative | 6% | 1 / 17 |

## Cleanup Priorities

If you only clean up a few packages first, start with the highest-scoring unused packages below.

| Rank | Package | Priority Score | Reason |
| ----: | ------- | -------------: | ------ |
| 1 | `creative/popular-web-designs` | 110 | Unused + Complexity 108 + Health 48 + 2 risk signals |
| 2 | `productivity/powerpoint` | 95 | Unused + Complexity 135 + 2 risk signals |
| 3 | `research/research-paper-writing` | 85 | Unused + Complexity 99 + 2 risk signals |
| 4 | `creative/comfyui` | 85 | Unused + Complexity 54 + 2 risk signals |
| 5 | `creative/touchdesigner-mcp` | 75 | Unused + Complexity 24 + 2 risk signals |
| 6 | `creative/baoyu-infographic` | 75 | Unused + Complexity 46 + 2 risk signals |
| 7 | `creative/p5js` | 65 | Unused + Complexity 25 + 1 risk signal |
| 8 | `yuanbao` | 40 | Unused |
| 9 | `software-development/test-driven-development` | 40 | Unused |
| 10 | `software-development/systematic-debugging` | 40 | Unused |

## Governance Recommendations

### Split monolithic package
- **Scope**: `creative/popular-web-designs`
- **Severity**: Critical
- **Description**: `creative/popular-web-designs` has complexity 108 with 54 templates, 0 references, 0 scripts.
- **Action**: Consider splitting into smaller focused packages. Move templates/references into a dedicated knowledge package. Keep executable scripts in the core skill.

### Split monolithic package
- **Scope**: `productivity/powerpoint`
- **Severity**: Critical
- **Description**: `productivity/powerpoint` has complexity 135 with 0 templates, 0 references, 44 scripts.
- **Action**: Consider splitting into smaller focused packages. Move templates/references into a dedicated knowledge package. Keep executable scripts in the core skill.

### Move references into dedicated knowledge package
- **Scope**: `creative/baoyu-infographic`
- **Severity**: High
- **Description**: `creative/baoyu-infographic` has 45 reference files.
- **Action**: Extract reference materials into a separate knowledge-base package to reduce the main skill's complexity.

### Split monolithic package
- **Scope**: `creative/comfyui`
- **Severity**: High
- **Description**: `creative/comfyui` has complexity 54 with 0 templates, 4 references, 11 scripts.
- **Action**: Consider splitting into smaller focused packages. Move templates/references into a dedicated knowledge package. Keep executable scripts in the core skill.

### Split template library into dedicated package
- **Scope**: `creative/popular-web-designs`
- **Severity**: High
- **Description**: `creative/popular-web-designs` has 54 template files.
- **Action**: Create a dedicated template-library package and move templates there. The main skill should reference the library rather than contain all templates.

### Move references into dedicated knowledge package
- **Scope**: `creative/touchdesigner-mcp`
- **Severity**: High
- **Description**: `creative/touchdesigner-mcp` has 21 reference files.
- **Action**: Extract reference materials into a separate knowledge-base package to reduce the main skill's complexity.

### Split monolithic package
- **Scope**: `research/research-paper-writing`
- **Severity**: High
- **Description**: `research/research-paper-writing` has complexity 99 with 45 templates, 9 references, 0 scripts.
- **Action**: Consider splitting into smaller focused packages. Move templates/references into a dedicated knowledge package. Keep executable scripts in the core skill.

### Split template library into dedicated package
- **Scope**: `research/research-paper-writing`
- **Severity**: High
- **Description**: `research/research-paper-writing` has 45 template files.
- **Action**: Create a dedicated template-library package and move templates there. The main skill should reference the library rather than contain all templates.

### Review unused skills for archival
- **Scope**: `[library-wide]`
- **Severity**: High
- **Description**: Only 5.7% of installed skills are actively used. 66 skills have never been used.
- **Action**: Consider archiving or removing unused skills. Review large unused packages before adding new skills.

### Skill utilization is below 10%
- **Scope**: `[library-wide]`
- **Severity**: High
- **Description**: Only 5.7% of installed skills are actively used. Large portions of the library may no longer provide value.
- **Action**: Review the unused skills list and consider removing or archiving skills that are no longer relevant to your workflow.

Additional Recommendations Hidden

- Medium: 5
- Low: 7

## Highest Risk Packages

| Rank | Package | Category | Health | Complexity | Risk Factors |
|---:|---|---|---:|---:|---|
| 1 | `creative/popular-web-designs` | creative | 48 / 100 | 108 | High complexity (108); Template bloat (54 templates) |
| 2 | `research/research-paper-writing` | research | 60 / 100 | 99 | High complexity (99); Template bloat (45 templates) |
| 3 | `productivity/powerpoint` | productivity | 62 / 100 | 135 | High complexity (135); Script bloat (44 scripts) |
| 4 | `creative/comfyui` | creative | 71 / 100 | 54 | High complexity (54); Script bloat (11 scripts) |
| 5 | `creative/baoyu-infographic` | creative | 73 / 100 | 46 | High complexity (46); Reference bloat (45 references) |
| 6 | `creative/touchdesigner-mcp` | creative | 79 / 100 | 24 | High complexity (24); Reference bloat (21 references) |
| 7 | `creative/p5js` | creative | 90 / 100 | 25 | High complexity (25) |
| 8 | `mlops/huggingface-hub` | mlops | 91 / 100 | 0 | - |
| 9 | `creative/humanizer` | creative | 93 / 100 | 1 | - |
| 10 | `creative/manim-video` | creative | 93 / 100 | 18 | - |

## Most Valuable Packages

| Rank | Package | Category | Health | Value Score | Drivers |
|---:|---|---|---:|---:|---|
| 1 | `research/research-paper-writing` | research | 60 / 100 | 120 | 9 references, high template density, workflow |
| 2 | `productivity/powerpoint` | productivity | 62 / 100 | 118 | script-heavy, executable skill |
| 3 | `creative/baoyu-infographic` | creative | 73 / 100 | 117 | 45 references, workflow, good health |
| 4 | `creative/comfyui` | creative | 71 / 100 | 97 | 4 references, script-heavy, executable skill, good health |
| 5 | `creative/popular-web-designs` | creative | 48 / 100 | 88 | high template density, health penalty |
| 6 | `creative/p5js` | creative | 90 / 100 | 79 | 10 references, 1 templates, executable skill, good health |
| 7 | `creative/touchdesigner-mcp` | creative | 79 / 100 | 79 | 21 references, executable skill, good health |
| 8 | `creative/manim-video` | creative | 93 / 100 | 75 | 14 references, executable skill, good health |
| 9 | `red-teaming/godmode` | red-teaming | 98 / 100 | 64 | 2 references, 2 templates, executable skill, good health |
| 10 | `productivity/google-workspace` | productivity | 98 / 100 | 53 | 1 references, executable skill, good health |

---

## Package Type Distribution

- **Knowledge**: 9 (13%)
- **Workflow**: 15 (21%)
- **Executable Skill**: 45 (64%)
- **Reference Material**: 1 (1%)

## Asset Distribution

- **References**: 131
- **Templates**: 111
- **Scripts**: 77
- **Assets**: 26

## Category Breakdown

### apple
*Apple / macOS skills — tools that interact with the Mac desktop (Finder,
native apps) or system features (accessibility, screenshots).*
- **5** skill packages
  - Executable Skill: 5
### autonomous-ai-agents
*---
description: Skills for spawning and orchestrating autonomous AI coding agents and multi-agent workflows — running independent agent processes, delegating tasks, and coordinating parallel workstre*
- **4** skill packages
  - Knowledge: 1
  - Executable Skill: 3
### creative
*---
description: Creative content generation — ASCII art, hand-drawn style diagrams, and visual design tools.
---*
- **17** skill packages
  - Knowledge: 4
  - Workflow: 4
  - Executable Skill: 9
### data-science
*---
description: Skills for data science workflows — interactive exploration, Jupyter notebooks, data analysis, and visualization.
---*
- **1** skill packages
  - Executable Skill: 1
### devops
- **2** skill packages
  - Knowledge: 1
  - Workflow: 1
### dogfood
- **1** skill packages
  - Workflow: 1
### email
*---
description: Skills for sending, receiving, searching, and managing email from the terminal.
---*
- **1** skill packages
  - Executable Skill: 1
### github
*---
description: GitHub workflow skills for managing repositories, pull requests, code reviews, issues, and CI/CD pipelines using the gh CLI and git via terminal.
---*
- **6** skill packages
  - Workflow: 1
  - Executable Skill: 5
### governance
- **1** skill packages
  - Executable Skill: 1
### media
*---
description: Skills for working with media content — YouTube transcripts, GIF search, music generation, and audio visualization.
---*
- **4** skill packages
  - Workflow: 1
  - Executable Skill: 3
### mlops
*---
description: Knowledge and Tools for Machine Learning Operations - tools and frameworks for training, fine-tuning, deploying, and optimizing ML/AI models
---*
- **1** skill packages
  - Reference Material: 1
### note-taking
*---
description: Note taking skills, to save information, assist with research, and collab on multi-session planning and information sharing.
---*
- **1** skill packages
  - Workflow: 1
### productivity
*---
description: Skills for document creation, presentations, spreadsheets, and other productivity workflows.
---*
- **8** skill packages
  - Workflow: 2
  - Executable Skill: 6
### red-teaming
- **1** skill packages
  - Executable Skill: 1
### research
*---
description: Skills for academic research, paper discovery, literature review, domain reconnaissance, market data, content monitoring, and scientific knowledge retrieval.
---*
- **5** skill packages
  - Workflow: 1
  - Executable Skill: 4
### smart-home
*---
description: Skills for controlling smart home devices — lights, switches, sensors, and home automation systems.
---*
- **1** skill packages
  - Executable Skill: 1
### social-media
*---
description: Skills for interacting with social platforms and social-media workflows — posting, reading, monitoring, and account operations.
---*
- **1** skill packages
  - Executable Skill: 1
### software-development
- **9** skill packages
  - Knowledge: 3
  - Workflow: 3
  - Executable Skill: 3
### yuanbao
- **1** skill packages
  - Executable Skill: 1

## Duplicate Skill Packages

No duplicate skill packages detected.
