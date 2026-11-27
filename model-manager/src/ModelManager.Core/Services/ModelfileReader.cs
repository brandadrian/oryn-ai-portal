using ModelManager.Core.Models;

namespace ModelManager.Core.Services;

/// <summary>
/// Reads the header of *.Modelfile files:
/// first non-separator comment line is the model name, then a "# WOFÜR" block up to the next empty "#" line;
/// the context comes from "PARAMETER num_ctx".
/// </summary>
public static class ModelfileReader
{
    public static IReadOnlyList<ConfiguredModel> ReadDirectory(string dir)
    {
        if (!Directory.Exists(dir)) return [];
        return Directory.GetFiles(dir, "*.Modelfile")
            .Order(StringComparer.Ordinal)
            .Select(f => Parse(File.ReadAllLines(f), Path.GetFileName(f)))
            .OfType<ConfiguredModel>()
            .ToList();
    }

    public static ConfiguredModel? Parse(IReadOnlyList<string> lines, string fileName)
    {
        var header = lines
            .TakeWhile(l => l.StartsWith('#') || l.Trim().Length == 0)
            .Select(l => l.TrimStart('#').Trim())
            .ToList();

        var name = header.FirstOrDefault(l => l.Length > 0 && !l.StartsWith('='));
        if (string.IsNullOrEmpty(name) || name.Contains(' ')) return null;

        var start = header.FindIndex(l => l.StartsWith("WOFÜR", StringComparison.OrdinalIgnoreCase));
        var description = start < 0
            ? ""
            : string.Join(" ", header.Skip(start + 1).TakeWhile(l => l.Length > 0));

        return new ConfiguredModel(name, description, fileName, ReadNumCtx(lines));
    }

    /// <summary>"PARAMETER num_ctx 131072" (last one wins, like in Ollama).</summary>
    private static int? ReadNumCtx(IEnumerable<string> lines) => lines
        .Select(l => l.Trim().Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries))
        .Where(p => p.Length >= 3
                    && p[0].Equals("PARAMETER", StringComparison.OrdinalIgnoreCase)
                    && p[1].Equals("num_ctx", StringComparison.OrdinalIgnoreCase))
        .Select(p => int.TryParse(p[2], out var n) ? n : (int?)null)
        .LastOrDefault(n => n is not null);
}
