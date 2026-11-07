using System.Text;

namespace OllamaMonitor.Logs;

/// <summary>
/// Liest neue Zeilen einer Logdatei. Startet am Dateiende (alte Zeilen nicht doppelt zählen)
/// und öffnet die Datei neu, wenn Ollama sie beim Neustart rotiert (Datei wird kürzer).
/// </summary>
public sealed class LogTailer(string logPath) : IDisposable
{
    private FileStream? _stream;
    private StreamReader? _reader;
    private readonly StringBuilder _partial = new();

    public IEnumerable<string> ReadNewLines()
    {
        if (_stream is null)
        {
            if (!Open(fromEnd: true)) yield break;
        }
        else if (FileLength() is long len && len < _stream.Position)
        {
            // Rotiert: neue Datei von vorne lesen
            Close();
            if (!Open(fromEnd: false)) yield break;
        }

        string? line;
        while ((line = ReadLineOrPartial()) is not null)
        {
            if (line.Length > 0) yield return line;
        }
    }

    /// <summary>Gibt nur vollständige Zeilen zurück; eine halb geschriebene Zeile wird gepuffert.</summary>
    private string? ReadLineOrPartial()
    {
        while (true)
        {
            var c = _reader!.Read();
            if (c == -1) return null;
            if (c == '\n')
            {
                var s = _partial.ToString().TrimEnd('\r');
                _partial.Clear();
                return s;
            }
            _partial.Append((char)c);
        }
    }

    private bool Open(bool fromEnd)
    {
        if (!File.Exists(logPath)) return false;
        _stream = File.Open(logPath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete);
        if (fromEnd) _stream.Seek(0, SeekOrigin.End);
        _reader = new StreamReader(_stream, Encoding.UTF8, false, 4096, leaveOpen: true);
        _partial.Clear();
        return true;
    }

    private long? FileLength()
    {
        try { return new FileInfo(logPath).Length; } catch { return null; }
    }

    private void Close()
    {
        _reader?.Dispose(); _reader = null;
        _stream?.Dispose(); _stream = null;
    }

    public void Dispose() => Close();
}
