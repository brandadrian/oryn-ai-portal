---
name: software-documentation
description: Write simple, structured software documentation for a project.
---

# Software documentation

Write in English, keep it concise, and document verified facts only. Do not
invent requirements or decisions; mark unresolved questions as open.

Create a root `README.md` with a short description, status, overview, setup,
usage, configuration, logging, and links to the detailed documentation.
Include only sections relevant to the project.

Use this structure for detailed documentation:

```text
docs/
  README.md
  software-requirements-specification.md
  software-architecture-specification.md   Optional
  adr/
    README.md
    0001-short-title.md
  test-cases/
    README.md
    <module>/
      TC-<MODULE>-001-short-title.md
```

- `docs/README.md`: system purpose, status, a simple context diagram, and links.
- Requirements: scope, stakeholders, use cases, functional and non-functional
  requirements with IDs and Shall/Should/May weights, assumptions, and open issues.
- Architecture: when useful, show containers and the main runtime flow,
  including errors. Document component details alongside the code.
- ADRs: record significant decisions with status, date, author, context,
  decision, and consequences. Index them in `adr/README.md`.
- Test cases: group and index manual cases by module, link requirement IDs, and
  describe preconditions, steps, expected results, and postconditions.

Use Mermaid for diagrams when helpful. Do not create example ADRs or test cases
that describe decisions or behavior that do not exist.
