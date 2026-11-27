using System.Text.Json;
using Microsoft.Extensions.Options;
using ModelManager.Core;
using ModelManager.Core.Models;
using ModelManager.Core.Services;

namespace ModelManager.Adapters.Ollama;

/// <summary>
/// Talks to scripts/ollama-restart-agent.ps1 on Windows through a shared directory:
/// writes restart.request, the agent restarts Ollama and writes status.json.
/// </summary>
public sealed class HostAgentRestarter(IOptions<ModelManagerOptions> options) : IOllamaRestarter
{
    private static readonly TimeSpan AgentTimeout = TimeSpan.FromSeconds(15);
    private sealed record AgentStatus(string? State, string? Message, DateTimeOffset? At);

    private string Dir => options.Value.RestartDir;
    private bool Available => Dir.Length > 0 && Directory.Exists(Dir);
    private string RequestFile => Path.Combine(Dir, "restart.request");
    private string StatusFile => Path.Combine(Dir, "status.json");

    public RestartStatus GetStatus()
    {
        if (!Available) return new RestartStatus(false, "unavailable", null, null);

        if (File.Exists(RequestFile))
        {
            var since = File.GetLastWriteTimeUtc(RequestFile);
            var stale = DateTime.UtcNow - since > AgentTimeout;
            return new RestartStatus(true, "pending",
                stale ? "Restart-Agent reagiert nicht (scripts\\install-ollama-restart-agent.ps1)" : "Neustart angefordert",
                new DateTimeOffset(since, TimeSpan.Zero));
        }

        if (!File.Exists(StatusFile)) return new RestartStatus(true, "idle", null, null);
        try
        {
            var s = JsonSerializer.Deserialize<AgentStatus>(File.ReadAllText(StatusFile).TrimStart('﻿'),
                new JsonSerializerOptions(JsonSerializerDefaults.Web));
            return new RestartStatus(true, s?.State ?? "idle", s?.Message, s?.At);
        }
        catch (Exception e) when (e is IOException or JsonException)
        {
            // agent may be writing the file right now
            return new RestartStatus(true, "running", null, null);
        }
    }

    public async Task<bool> RequestAsync(string id, CancellationToken ct)
    {
        if (!Available) return false;
        var state = GetStatus().State;
        if (state is "pending" or "running") return false;
        await File.WriteAllTextAsync(RequestFile, id, ct);
        return true;
    }
}
