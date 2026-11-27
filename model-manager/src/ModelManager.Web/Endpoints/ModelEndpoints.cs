using ModelManager.Core.Models;
using ModelManager.Core.Services;

namespace ModelManager.Web.Endpoints;

public sealed record ModelRequest(string Name);

public static class ModelEndpoints
{
    public static void MapModelEndpoints(this WebApplication app)
    {
        var api = app.MapGroup("/api");

        api.MapGet("/models", async (ModelService service, CancellationToken ct) =>
            Results.Ok(await service.GetModelsAsync(ct)));

        // name in the body: model names can contain "/" (e.g. hf.co/...)
        // not bound to the request: if the browser reloads or closes, Ollama keeps loading
        // (a cancelled request makes Ollama abort the load, HTTP 499)
        api.MapPost("/load", (ModelRequest req, ModelService service, ILogger<ModelService> log) =>
            Run("load", req, () => service.LoadAsync(req.Name, CancellationToken.None), log));

        api.MapPost("/unload", (ModelRequest req, ModelService service, ILogger<ModelService> log) =>
            Run("unload", req, () => service.UnloadAsync(req.Name, CancellationToken.None), log));

        // restart of the native Ollama through the host agent (scripts/ollama-restart-agent.ps1)
        api.MapGet("/restart", (IOllamaRestarter restarter) => Results.Ok(restarter.GetStatus()));

        api.MapPost("/restart", async (IOllamaRestarter restarter, ILogger<ModelService> log, CancellationToken ct) =>
        {
            var id = Guid.NewGuid().ToString("N")[..8];
            if (!await restarter.RequestAsync(id, ct))
            {
                log.LogWarning("command=restart;id={Id};event=rejected;state={State}", id, restarter.GetStatus().State);
                return Results.Conflict(new { error = "Neustart nicht verfügbar oder läuft schon" });
            }
            log.LogInformation("command=restart;id={Id};event=requested", id);
            return Results.Accepted();
        });
    }

    private static async Task<IResult> Run(string command, ModelRequest req, Func<Task<OllamaResult>> action, ILogger log)
    {
        if (string.IsNullOrWhiteSpace(req.Name)) return Results.BadRequest(new { error = "name fehlt" });

        var id = Guid.NewGuid().ToString("N")[..8];
        log.LogInformation("command={Command};id={Id};event=start;model={Model}", command, id, req.Name);
        var result = await action();
        if (result.Success)
        {
            log.LogInformation("command={Command};id={Id};event=done;model={Model}", command, id, req.Name);
            return Results.Ok();
        }

        log.LogWarning("command={Command};id={Id};event=failed;model={Model};status={Status};error={Error}",
            command, id, req.Name, result.StatusCode, result.Error);
        return Results.Json(new { error = result.Error }, statusCode: result.StatusCode);
    }
}
