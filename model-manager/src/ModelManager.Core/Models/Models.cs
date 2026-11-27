namespace ModelManager.Core.Models;

/// <summary>A model defined by a Modelfile in the models directory.</summary>
public sealed record ConfiguredModel(string Name, string Description, string File, int? NumCtx = null);

/// <summary>A model installed in Ollama (/api/tags).</summary>
public sealed record InstalledModel(string Name, long Size);

/// <summary>A model currently loaded in Ollama (/api/ps).</summary>
public sealed record LoadedModel(string Name, long Size, long SizeVram, DateTimeOffset ExpiresAt, int? ContextLength = null);

/// <summary>Combined view of a model for the UI.</summary>
public sealed record ModelStatus(
    string Name,
    string? Description,
    string? File,
    bool Configured,
    bool Installed,
    long? Size,
    bool Loaded,
    long? SizeVram,
    int? GpuPercent,
    DateTimeOffset? ExpiresAt,
    int? ContextLength);

/// <summary>State of the Ollama restart done by the host agent (scripts/ollama-restart-agent.ps1).</summary>
public sealed record RestartStatus(bool Available, string State, string? Message, DateTimeOffset? At);

/// <summary>Result of a load or unload call.</summary>
public sealed record OllamaResult(bool Success, int StatusCode, string? Error)
{
    public static OllamaResult Ok() => new(true, 200, null);
}
