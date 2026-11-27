using System.Security.Cryptography;
using System.Text;
using Microsoft.Extensions.Options;
using ModelManager.Core;

namespace ModelManager.Api.Infrastructure;

/// <summary>HTTP Basic Auth for the whole app (UI + API), constant-time comparison.</summary>
public sealed class BasicAuthMiddleware(RequestDelegate next, IOptions<ModelManagerOptions> options)
{
    private readonly byte[] _user = Hash(options.Value.User);
    private readonly byte[] _password = Hash(options.Value.Password);

    public Task InvokeAsync(HttpContext context)
    {
        if (IsAuthorized(context.Request.Headers.Authorization.ToString())) return next(context);

        context.Response.StatusCode = StatusCodes.Status401Unauthorized;
        context.Response.Headers.WWWAuthenticate = "Basic realm=\"Oryn Model-Manager\"";
        return context.Response.WriteAsync("Login erforderlich");
    }

    private bool IsAuthorized(string header)
    {
        if (!header.StartsWith("Basic ", StringComparison.Ordinal)) return false;

        string decoded;
        try { decoded = Encoding.UTF8.GetString(Convert.FromBase64String(header[6..])); }
        catch (FormatException) { return false; }

        var sep = decoded.IndexOf(':');
        if (sep < 0) return false;

        // always run both comparisons (no short-circuit)
        var userOk = CryptographicOperations.FixedTimeEquals(Hash(decoded[..sep]), _user);
        var passOk = CryptographicOperations.FixedTimeEquals(Hash(decoded[(sep + 1)..]), _password);
        return userOk & passOk;
    }

    private static byte[] Hash(string value) => SHA256.HashData(Encoding.UTF8.GetBytes(value));
}
