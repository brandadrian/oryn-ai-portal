---
name: dotnet-create-solution
description: Create a simple .NET solution with a clean project structure and documentation conventions.
---

# Create a .NET solution

Use the requested product name. Choose the appropriate host template, such as console, web API, worker, or MCP server.

## Structure

```text
<repository-name>/
  src/
    <Product>.sln or <Product>.slnx
    <Product>.Api/             API
    <Product>.Core/            Logic, models, interfaces
    <Product>.Data/            Database, repositories, migrations
    <Product>.Contracts/       DTOs, requests, responses
    <Product>.Shared/          Common utilities and extensions
    <Product>.Adapters.<Name>/ External integrations and for example external APIs

  tests/
    <Product>.Tests/

  files/                       Configuration, inputs, outputs
  docs/
  .gitignore
  README.md
```

Use kebab-case for the repository name and PascalCase for product and project names.

Keep tests outside `src`.

## Responsibilities

- **Api:** REST endpoints, MCP endpoints, authentication, startup, dependency injection.
- **Core:** Application logic, business rules, models, interfaces, workers.
- **Data:** Application database access, EF Core/Dapper, repositories, migrations.
- **Contracts:** Shared DTOs, API requests, responses, and message contracts.
- **Shared:** Reusable technical helpers, extensions, and constants.
- **Adapters:** External systems such as Jira, Ollama, Loki, MySQL, and MCP tools.

REST and MCP endpoints may share the same API host. Separate them only when independent deployment is needed.

## Dependencies

- Host references Core and required projects.
- Data references Core.
- Adapters reference Core.
- Core must not depend on Host, Data, or Adapters.
- Contracts and Shared should remain independent.
- Avoid circular dependencies and unnecessary references.

Only create Data, Contracts, Shared, and Adapters when needed.

## Example

Create a web API named `MyProduct`:

```powershell
dotnet new sln -n MyProduct -o src
dotnet new webapi -n MyProduct.Api -o src/MyProduct.Api
dotnet new classlib -n MyProduct.Core -o src/MyProduct.Core
dotnet new xunit -n MyProduct.Tests -o tests/MyProduct.Tests

dotnet add src/MyProduct.Api/MyProduct.Api.csproj reference src/MyProduct.Core/MyProduct.Core.csproj
dotnet add tests/MyProduct.Tests/MyProduct.Tests.csproj reference src/MyProduct.Core/MyProduct.Core.csproj

cd src
dotnet sln add MyProduct.Api/MyProduct.Api.csproj MyProduct.Core/MyProduct.Core.csproj ../tests/MyProduct.Tests/MyProduct.Tests.csproj

dotnet build
dotnet test
```

Add optional projects and their references only when needed.

The solution extension depends on the installed .NET SDK. Use another host template when appropriate.

## Documentation

Create a root README and `docs` using the [software-documentation skill](../software-documentation/SKILL.md).

Document setup, configuration, architecture, and usage.

## Configuration

Ignore `bin`, `obj`, `logs`, `data`, and local settings.

If configuration is needed, provide `appsettings.example.json` with placeholders. Never commit secrets.

## Logging

Keep technical logs separate from data output.

Use `timestamp;loglevel;message`, including `command`, execution `id`, and `event` when applicable.

Never log secrets or full sensitive payloads.

## Principles

- Keep it simple.
- One clear responsibility per project.
- No unnecessary abstractions.
- No circular dependencies.
- Add projects only when needed.
- Keep Core independent of infrastructure.
