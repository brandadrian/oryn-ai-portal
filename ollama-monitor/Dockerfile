# OllamaMonitor als Linux-Container.
# Im Container fehlen die Windows-Leistungsindikatoren (CPU, RAM, GPU-Last, VRAM).
# Tokens, Anfragen, Geschwindigkeit und geladene Modelle funktionieren (server.log + /api/ps).
FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /src
COPY src/OllamaMonitor/OllamaMonitor.csproj src/OllamaMonitor/
RUN dotnet restore src/OllamaMonitor/OllamaMonitor.csproj
COPY src/ src/
RUN dotnet publish src/OllamaMonitor/OllamaMonitor.csproj -c Release -o /app --no-restore

FROM mcr.microsoft.com/dotnet/runtime:10.0
WORKDIR /app
COPY --from=build /app .
ENTRYPOINT ["dotnet", "OllamaMonitor.dll"]
