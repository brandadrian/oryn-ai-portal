using Microsoft.Extensions.Options;
using ModelManager.Core.Models;

namespace ModelManager.Core.Services;

public sealed class ModelService(IOllamaClient ollama, IOptions<ModelManagerOptions> options)
{
    /// <summary>Configured models first (in file order), then other installed models.</summary>
    public async Task<IReadOnlyList<ModelStatus>> GetModelsAsync(CancellationToken ct)
    {
        var configured = ModelfileReader.ReadDirectory(options.Value.ModelsDir);
        var installed = await ollama.GetInstalledAsync(ct);
        var loaded = await ollama.GetLoadedAsync(ct);
        return Merge(configured, installed, loaded);
    }

    public Task<OllamaResult> LoadAsync(string model, CancellationToken ct) =>
        ollama.SetKeepAliveAsync(model, options.Value.KeepAlive, ct);

    public Task<OllamaResult> UnloadAsync(string model, CancellationToken ct) =>
        ollama.SetKeepAliveAsync(model, "0", ct);

    public static IReadOnlyList<ModelStatus> Merge(
        IReadOnlyList<ConfiguredModel> configured,
        IReadOnlyList<InstalledModel> installed,
        IReadOnlyList<LoadedModel> loaded)
    {
        var names = configured.Select(c => c.Name)
            .Concat(installed.Select(i => i.Name))
            .Concat(loaded.Select(l => l.Name))
            .Distinct();

        return names.Select(name =>
        {
            var cfg = configured.FirstOrDefault(c => c.Name == name);
            var inst = installed.FirstOrDefault(i => i.Name == name);
            var run = loaded.FirstOrDefault(l => l.Name == name);
            return new ModelStatus(name, cfg?.Description, cfg?.File, cfg is not null,
                inst is not null || run is not null, inst?.Size,
                run is not null, run?.SizeVram, GpuPercent(run), run?.ExpiresAt);
        }).ToList();
    }

    /// <summary>Share of the loaded model in VRAM (100 = fully on the GPU, less = partly on the CPU).</summary>
    private static int? GpuPercent(LoadedModel? run) =>
        run is null || run.Size <= 0 ? null : (int)Math.Round(100.0 * run.SizeVram / run.Size);
}
