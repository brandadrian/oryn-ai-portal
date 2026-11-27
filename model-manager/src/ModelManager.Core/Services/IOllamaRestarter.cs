using ModelManager.Core.Models;

namespace ModelManager.Core.Services;

/// <summary>Restarts the native Ollama on the host (frees VRAM and RAM completely).</summary>
public interface IOllamaRestarter
{
    RestartStatus GetStatus();

    /// <summary>Requests a restart; false if restart is not available or already pending.</summary>
    Task<bool> RequestAsync(string id, CancellationToken ct);
}
