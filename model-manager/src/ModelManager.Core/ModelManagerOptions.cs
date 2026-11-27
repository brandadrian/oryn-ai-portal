using System.ComponentModel.DataAnnotations;

namespace ModelManager.Core;

/// <summary>Configuration section "Manager" (appsettings.json or env Manager__*).</summary>
public sealed class ModelManagerOptions
{
    public const string Section = "Manager";

    [Required, Url] public string OllamaUrl { get; set; } = "";

    /// <summary>Directory with the *.Modelfile files.</summary>
    [Required] public string ModelsDir { get; set; } = "";

    /// <summary>Ollama keep_alive used when loading, e.g. "24h" or "-1" (forever).</summary>
    [Required] public string KeepAlive { get; set; } = "24h";

    /// <summary>
    /// Directory shared with the host agent (restart.request / status.json).
    /// Empty: restart is not available.
    /// </summary>
    public string RestartDir { get; set; } = "";

    [Required] public string User { get; set; } = "";

    [Required, MinLength(8)] public string Password { get; set; } = "";
}
