using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Serialization;
using ModelManager.Core.Models;
using ModelManager.Core.Services;

namespace ModelManager.Adapters.Ollama;

/// <summary>Ollama REST API: /api/tags, /api/ps, /api/generate.</summary>
public sealed class OllamaClient(HttpClient http) : IOllamaClient
{
    private sealed record ListResponse<T>(T[]? Models);
    private sealed record Tag(string Name, long Size);
    private sealed record Running(
        string Name,
        long Size,
        [property: JsonPropertyName("size_vram")] long SizeVram,
        [property: JsonPropertyName("expires_at")] DateTimeOffset ExpiresAt);

    public async Task<IReadOnlyList<InstalledModel>> GetInstalledAsync(CancellationToken ct)
    {
        var res = await http.GetFromJsonAsync<ListResponse<Tag>>("/api/tags", ct);
        return (res?.Models ?? []).Select(t => new InstalledModel(t.Name, t.Size)).ToList();
    }

    public async Task<IReadOnlyList<LoadedModel>> GetLoadedAsync(CancellationToken ct)
    {
        var res = await http.GetFromJsonAsync<ListResponse<Running>>("/api/ps", ct);
        return (res?.Models ?? []).Select(r => new LoadedModel(r.Name, r.Size, r.SizeVram, r.ExpiresAt)).ToList();
    }

    public async Task<OllamaResult> SetKeepAliveAsync(string model, string keepAlive, CancellationToken ct)
    {
        // without a prompt Ollama only loads/unloads the model; keep_alive as number or duration string
        object keep = int.TryParse(keepAlive, out var seconds) ? seconds : keepAlive;
        using var res = await http.PostAsJsonAsync("/api/generate",
            new { model, keep_alive = keep, stream = false }, ct);
        if (res.IsSuccessStatusCode) return OllamaResult.Ok();

        var body = await res.Content.ReadAsStringAsync(ct);
        return new OllamaResult(false, (int)res.StatusCode, ReadError(body));
    }

    private static string ReadError(string body)
    {
        try
        {
            using var doc = JsonDocument.Parse(body);
            if (doc.RootElement.TryGetProperty("error", out var e) && e.GetString() is { } msg) return msg;
        }
        catch (JsonException) { }
        return body;
    }
}
