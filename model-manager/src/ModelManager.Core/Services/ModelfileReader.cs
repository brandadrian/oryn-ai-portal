using ModelManager.Core.Models;

namespace ModelManager.Core.Services;

/// <summary>
/// Reads the header of *.Modelfile files:
/// first non-separator comment line is the model name, then a "# WOFÜR" block up to the next empty "#" line.
/// </summary>
public static class ModelfileReader
{
    public static IReadOnlyList<ConfiguredModel> ReadDirectory(string dir)
    {
        if (!Directory.Exists(dir)) return [];
        return Directory.GetFiles(dir, "*.Modelfile")
            .Order(StringComparer.Ordinal)
            .Select(f => Parse(File.ReadLines(f).Take(60).ToList(), Path.GetFileName(f)))
            .OfType<ConfiguredModel>()
            .ToList();
    }

    public static ConfiguredModel? Parse(IEnumerable<string> lines, string fileName)
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

        return new ConfiguredModel(name, description, fileName);
    }
}
