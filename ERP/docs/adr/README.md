# Architecture Decision Records (ADRs)

This directory contains Architecture Decision Records (ADRs) documenting significant architectural decisions made in the Himalytix ERP project.

## What is an ADR?

An Architecture Decision Record (ADR) is a document that captures an important architectural decision made along with its context and consequences.

## ADR Index

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| [0001](0001-multi-tenancy-architecture.md) | Multi-Tenancy Architecture | Accepted | 2024-Q3 |
| [0002](0002-internationalization-localization.md) | Internationalization and Localization Strategy | Accepted | 2024-Q4 |
| [0003](0003-technology-stack.md) | Technology Stack Selection | Accepted | 2024-Q1 |

## Creating a New ADR

1. Copy `template.md` to a new file: `000N-short-title.md`
2. Fill in all sections (use the template as a guide)
3. Number sequentially (e.g., 0004, 0005, etc.)
4. Update this README with the new ADR entry
5. Commit with message: `docs: add ADR-000N [title]`

## ADR Lifecycle

* **Proposed**: Under discussion, not yet decided
* **Accepted**: Decision made and implemented
* **Deprecated**: No longer relevant, but kept for historical context
* **Superseded**: Replaced by a newer ADR (link to the replacement)

## Review Schedule

ADRs should be reviewed:
- **Annually**: During architecture review sessions
- **On-demand**: When new information challenges the decision
- **Before major releases**: Ensure decisions still align with project goals

## References

- [ADR GitHub Organization](https://adr.github.io/)
- [Documenting Architecture Decisions](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)
