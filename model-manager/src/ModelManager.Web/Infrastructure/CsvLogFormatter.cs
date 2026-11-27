using Microsoft.Extensions.Logging.Abstractions;
using Microsoft.Extensions.Logging.Console;

namespace ModelManager.Web.Infrastructure;

/// <summary>Console log line: timestamp;loglevel;message</summary>
public sealed class CsvLogFormatter() : ConsoleFormatter(Name)
{
    public new const string Name = "csv";

    public override void Write<TState>(in LogEntry<TState> entry, IExternalScopeProvider? scopeProvider, TextWriter writer)
    {
        var message = entry.Formatter(entry.State, entry.Exception);
        if (entry.Exception is not null) message += " " + entry.Exception.Message;
        writer.WriteLine($"{DateTimeOffset.Now:yyyy-MM-ddTHH:mm:ss.fffzzz};{entry.LogLevel};{message.ReplaceLineEndings(" ")}");
    }
}
