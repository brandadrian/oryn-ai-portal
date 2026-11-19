---
name: dotnet-create-solution
description: Create a simple .NET solution with the project structure and documentation conventions.
---

# Create a .NET solution

Use the requested product name. Choose the host template for the requested
application, such as a console app, web API, or worker.

```text
<repository-name>/
  src/
    <Product>.sln or <Product>.slnx
    <Product>/               Host
    <Product>.Core/          Logic, models, interfaces
    <Product>.<Adapter>/     One project per external system, when needed
  tests/
    <Product>.Tests/
  files/                     File-based configuration, inputs, outputs, when needed
  docs/
  .gitignore
  README.md
```

Use a kebab-case repository name and PascalCase product and project names.
Keep tests outside `src`. The host references Core and any adapters; adapters
reference Core. Core must not depend on adapters. Add adapters only when needed.

For example, create a console application named `MyProduct`:

```powershell
dotnet new sln -n MyProduct -o src
dotnet new console -n MyProduct -o src\MyProduct
dotnet new classlib -n MyProduct.Core -o src\MyProduct.Core
dotnet new xunit -n MyProduct.Tests -o tests\MyProduct.Tests
dotnet add src\MyProduct\MyProduct.csproj reference src\MyProduct.Core\MyProduct.Core.csproj
dotnet add tests\MyProduct.Tests\MyProduct.Tests.csproj reference src\MyProduct.Core\MyProduct.Core.csproj
cd src
dotnet sln add MyProduct\MyProduct.csproj MyProduct.Core\MyProduct.Core.csproj ..\tests\MyProduct.Tests\MyProduct.Tests.csproj
dotnet build
dotnet test
```

The solution extension depends on the installed .NET SDK. Use another host
template when appropriate. Keep the host focused on startup and input/output;
put application logic in Core.

Create a root README and `docs` using the
[software-documentation skill](../software-documentation/SKILL.md).
Ignore `bin`, `obj`, `logs`, `data`, and local settings. If configuration is
needed, commit an `appsettings.example.json` with placeholders, document its
settings, and keep local settings out of Git.

Keep technical logs separate from data output. Use
`timestamp;loglevel;message`, with `command`, execution `id`, and `event`
fields in the message. Never log secrets or full payloads.
