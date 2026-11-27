using ModelManager.Core.Models;

namespace ModelManager.Core.Services;

public interface IOllamaClient
{
    Task<IReadOnlyList<InstalledModel>> GetInstalledAsync(CancellationToken ct);
    Task<IReadOnlyList<LoadedModel>> GetLoadedAsync(CancellationToken ct);

    /// <summary>Loads (keepAlive &gt; 0) or unloads (keepAlive "0") a model without generating text.</summary>
    Task<OllamaResult> SetKeepAliveAsync(string model, string keepAlive, CancellationToken ct);
}
