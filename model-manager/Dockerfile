FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /repo
COPY Directory.Build.props ./
COPY src/ModelManager.Core/ModelManager.Core.csproj src/ModelManager.Core/
COPY src/ModelManager.Adapters.Ollama/ModelManager.Adapters.Ollama.csproj src/ModelManager.Adapters.Ollama/
COPY src/ModelManager.Web/ModelManager.Web.csproj src/ModelManager.Web/
RUN dotnet restore src/ModelManager.Web/ModelManager.Web.csproj
COPY src/ src/
RUN dotnet publish src/ModelManager.Web/ModelManager.Web.csproj -c Release -o /app --no-restore

FROM mcr.microsoft.com/dotnet/aspnet:10.0-alpine
WORKDIR /app
COPY --from=build /app .
ENV ASPNETCORE_HTTP_PORTS=8080
EXPOSE 8080
ENTRYPOINT ["dotnet", "ModelManager.Web.dll"]
