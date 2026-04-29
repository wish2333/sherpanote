# DevPack - VibeCoding Resource Kit

> Documentation-first development flow resource package for AI-assisted coding.

## Quick Start

```bash
# 1. Copy this package to your project root
cp -r devpack/ /path/to/your-project/

# 2. Copy CLAUDE.md to project root (if not already there)
cp devpack/CLAUDE.md ./CLAUDE.md

# 3. Move .claude/ contents into project's .claude/ directory
cp -r devpack/.claude/* ./.claude/

# 4. Move docs/ into project root
cp -r devpack/docs/* ./docs/

# 5. Customize CLAUDE.md with your project info
#    Edit: project name, tech stack, AI behavior rules

# 6. Fill in docs/PRD.md with your requirements
#    Describe what you want to build in natural language

# 7. Start coding with Claude Code
#    AI will follow the constitution, invoke skills, and evolve via feedback
```

## Architecture

```
devpack/
  CLAUDE.md                    # Constitution - AI behavior rules (copy to project root)
  docs/                        # Documentation layer
    PRD.md                     # Product Requirements (What & Why)
    design/                    # Design artifacts (How)
      system_design.md         # Architecture and module design
      state_machine.md         # State machine definitions
      data_models/             # Data model field definitions (CSV)
        _template.csv
    procedures/                # Workflow definitions
      workflow_index.md        # Master index with version tracking
      _template.md             # Workflow file template
    business_rules.md          # Domain business rules
    dev_guide.md               # Development guide and conventions
    changelog.md               # Version change log
  .claude/
    rules/                     # Rules layer (extends global rules)
      coding-style.md          # Code style conventions
      testing.md               # Testing requirements
      git-workflow.md          # Git conventions
      security.md              # Security requirements
      performance.md           # Performance guidelines
      patterns.md              # Design patterns to follow
    skills/                    # Project-specific skill templates
      bug-fixer.md             # Systematic debugging (4-phase method)
      doc-sync.md              # Auto-sync docs from commit/release info
    feedback/                  # Evolution layer (feedback-driven improvement)
      index.md                 # Central feedback index
      raw/                     # Raw feedback records
        _template.md           # Feedback file template
      graduated/               # Rules promoted from feedback
```

## Three-Layer Architecture

### Layer 1: Constitution (`CLAUDE.md`)
The "supreme law" - defines AI behavior, document priority, and directory conventions.
AI reads this first at every session start.

### Layer 2: Skills

#### Project Skills (`.claude/skills/`)
Reusable task templates specific to this project:
- `/bug-fixer` - 4-phase systematic debugging
- `/doc-sync` - Auto-sync documentation from user-provided commit/release info

#### ECC Skills (External)
Battle-tested skills from the ECC toolkit:
- `ecc:feature-dev` - End-to-end feature development with planning
- `ecc:code-review` - Quality, security, performance review

### Layer 3: Feedback System (`.claude/feedback/`)
The evolution engine. System improves over time:
1. **Record** - User corrections captured into `feedback/raw/`
2. **Index** - `feedback/index.md` tracks occurrence counts
3. **Graduate** - Signals appearing 3+ times auto-promote to `rules/`
4. **Propagate** - New sessions automatically follow graduated rules

## Release Flow

Releases are **manual**, performed by the user. After releasing:

```
[User commits/releases]
      |
      v
[User provides commit message or release info to AI]
      |
      v
[AI invokes /doc-sync]
      |
      v
[Auto-updated: changelog, procedures, business_rules, data_models, etc.]
```

## Document Priority

When AI needs to decide between conflicting information:

1. `docs/PRD.md` (Requirements - highest)
2. `docs/design/` (Design artifacts)
3. `docs/procedures/` (Workflows)
4. `docs/business_rules.md` (Domain rules)
5. `.claude/rules/` (Coding standards)
6. Source code (Lowest - code should match docs, not vice versa)

## Key Principles

- **AI is the primary audience** - All documents are written for AI consumption
- **Docs are the constitution** - Code must conform to documentation
- **Feedback-driven evolution** - The system improves with every interaction
- **Sub-agent isolation** - Each task starts fresh, no inherited context pollution
- **One change at a time** - Change one thing, verify, then proceed
- **Manual release, auto sync** - User controls releases, AI keeps docs in sync

## Customization Guide

1. **Project-specific**: Edit `CLAUDE.md` with your project name, tech stack, domain
2. **Domain rules**: Fill `docs/business_rules.md` with your business logic
3. **Data models**: Add CSV files to `docs/design/data_models/`
4. **Workflows**: Add markdown files to `docs/procedures/`
5. **Coding style**: Adjust `.claude/rules/coding-style.md`
6. **Skills**: Extend or modify skills in `.claude/skills/`
