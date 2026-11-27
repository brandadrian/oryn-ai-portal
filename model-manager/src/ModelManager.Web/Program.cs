using Microsoft.Extensions.Options;
using ModelManager.Adapters.Ollama;
using ModelManager.Web.Endpoints;
using ModelManager.Web.Infrastructure;
using ModelManager.Core;
using ModelManager.Core.Services;

var builder = WebApplication.CreateBuilder(args);

// technical log: timestamp;loglevel;message
builder.Logging.ClearProviders();
builder.Logging.AddConsole(o => o.FormatterName = CsvLogFormatter.Name);
builder.Logging.AddConsoleFormatter<CsvLogFormatter, Microsoft.Extensions.Logging.Console.ConsoleFormatterOptions>();

// configuration (appsettings.json + env Manager__*), validated at startup
builder.Services.AddOptions<ModelManagerOptions>()
    .Bind(builder.Configuration.GetSection(ModelManagerOptions.Section))
    .ValidateDataAnnotations()
    .ValidateOnStart();

// loading a large model can take minutes
builder.Services.AddHttpClient<IOllamaClient, OllamaClient>((sp, c) =>
{
    c.BaseAddress = new Uri(sp.GetRequiredService<IOptions<ModelManagerOptions>>().Value.OllamaUrl);
    c.Timeout = TimeSpan.FromMinutes(10);
});
builder.Services.AddScoped<ModelService>();
builder.Services.AddSingleton<IOllamaRestarter, HostAgentRestarter>();

var app = builder.Build();

app.UseMiddleware<BasicAuthMiddleware>();
app.UseDefaultFiles();
app.UseStaticFiles();
app.MapModelEndpoints();

app.Run();
