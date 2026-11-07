using System.Globalization;
using System.Text.RegularExpressions;
using OllamaMonitor.Metrics;

namespace OllamaMonitor.Logs;

/// <summary>
/// Liest die llama.cpp-Zeilen aus Ollamas server.log, z.B.:
///   slot print_timing: id 0 | task 1217 | prompt eval time = 3030.71 ms /  1291 tokens (2.35 ms per token, 425.97 tokens per second)
///   slot print_timing: id 0 | task 1217 |        eval time = 4141.66 ms /   170 tokens (24.51 ms per token,  40.80 tokens per second)
///   slot      release: id 0 | task 1217 | stop processing: n_tokens = 100655, truncated = 0
/// Die Zeilen enthalten keinen Modellnamen: wir nehmen das Modell, das laut /api/ps geladen ist.
/// </summary>
public sealed class LogParser(Telemetry tel)
{
    private static readonly Regex PromptEval = new(
        @"\|\s*prompt eval time =\s*(?<ms>[\d.]+) ms /\s*(?<n>\d+) tokens.*?(?<tps>[\d.]+) tokens per second",
        RegexOptions.Compiled);

    private static readonly Regex OutputEval = new(
        @"\|\s*eval time =\s*(?<ms>[\d.]+) ms /\s*(?<n>\d+) tokens.*?(?<tps>[\d.]+) tokens per second",
        RegexOptions.Compiled);

    private static readonly Regex StopProcessing = new(
        @"stop processing: n_tokens =\s*(?<n>\d+), truncated =\s*(?<t>\d+)", RegexOptions.Compiled);

    // z.B. "llama-server model predicted to exceed available memory, evicting"
    private static readonly Regex Eviction = new(@"\bevicting\b", RegexOptions.Compiled);
    private static readonly Regex Failure = new(@"failed to load model", RegexOptions.Compiled | RegexOptions.IgnoreCase);

    private double _promptMs;

    public void Parse(string line)
    {
        var m = PromptEval.Match(line);
        if (m.Success)
        {
            var model = CurrentModel();
            _promptMs = D(m, "ms");
            tel.PromptTokens.Add(long.Parse(m.Groups["n"].Value), model);
            tel.TokensPerSecond.Record(D(m, "tps"), model, new("phase", "prompt"));
            return;
        }

        m = OutputEval.Match(line);
        if (m.Success)
        {
            var model = CurrentModel();
            tel.OutputTokens.Add(long.Parse(m.Groups["n"].Value), model);
            tel.TokensPerSecond.Record(D(m, "tps"), model, new("phase", "output"));
            tel.RequestDuration.Record((_promptMs + D(m, "ms")) / 1000.0, model);
            tel.Requests.Add(1, model, new("status", "ok"));
            _promptMs = 0;
            return;
        }

        m = StopProcessing.Match(line);
        if (m.Success)
        {
            var model = CurrentModel();
            tel.PromptSize.Record(long.Parse(m.Groups["n"].Value), model);
            if (m.Groups["t"].Value != "0") tel.TruncatedPrompts.Add(1, model);
            return;
        }

        if (Eviction.IsMatch(line))
            tel.Evictions.Add(1);

        if (Failure.IsMatch(line))
            tel.LoadFailures.Add(1);
    }

    private KeyValuePair<string, object?> CurrentModel()
    {
        var models = tel.Current.Models;
        var name = models.Count == 1 ? models[0].Name : models.Count == 0 ? "unbekannt" : "mehrere";
        return new("model", name);
    }

    private static double D(Match m, string g) => double.Parse(m.Groups[g].Value, CultureInfo.InvariantCulture);
}
