using ModelManager.Core.Models;
using ModelManager.Core.Services;

namespace ModelManager.Tests;

public class ModelServiceTests
{
    [Fact]
    public void Merge_ConfiguredFirst_ThenOtherInstalled()
    {
        var expires = DateTimeOffset.Parse("2026-11-28T18:00:00+01:00");
        var result = ModelService.Merge(
            [new ConfiguredModel("a:1", "A", "a.Modelfile", 4096), new ConfiguredModel("b:1", "B", "b.Modelfile", 8192)],
            [new InstalledModel("c:1", 10), new InstalledModel("a:1", 20)],
            [new LoadedModel("a:1", 40, 30, expires, 2048)]);

        Assert.Equal(["a:1", "b:1", "c:1"], result.Select(m => m.Name));

        var a = result[0];
        Assert.True(a.Configured && a.Installed && a.Loaded);
        Assert.Equal(20, a.Size);
        Assert.Equal(30, a.SizeVram);
        Assert.Equal(expires, a.ExpiresAt);
        Assert.Equal(75, a.GpuPercent);
        Assert.Equal(2048, a.ContextLength);   // loaded value wins over the Modelfile

        var b = result[1];
        Assert.True(b.Configured);
        Assert.False(b.Installed);
        Assert.False(b.Loaded);
        Assert.Equal(8192, b.ContextLength);

        var c = result[2];
        Assert.False(c.Configured);
        Assert.True(c.Installed);
        Assert.Null(c.Description);
    }

    [Fact]
    public void Merge_LoadedButNotInTags_CountsAsInstalled()
    {
        var result = ModelService.Merge([], [], [new LoadedModel("x:1", 5, 5, DateTimeOffset.Now)]);

        var x = Assert.Single(result);
        Assert.True(x.Installed && x.Loaded);
    }
}
