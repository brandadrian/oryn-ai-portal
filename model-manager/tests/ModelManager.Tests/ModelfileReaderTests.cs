using ModelManager.Core.Services;

namespace ModelManager.Tests;

public class ModelfileReaderTests
{
    [Fact]
    public void Parse_ReadsNameAndPurpose()
    {
        string[] lines =
        [
            "# ============================================================",
            "# qwen3.8:27b-q4-128k",
            "# ============================================================",
            "#",
            "# WOFÜR",
            "#   Standard-Qwen 3.8 27B ohne Anpassungen.",
            "#   Allgemeiner Chat.",
            "#",
            "# EIGENSCHAFTEN",
            "#   Basis: Qwen 3.8 27B",
            "",
            "FROM qwen3.8:27b",
        ];

        var model = ModelfileReader.Parse(lines, "qwen3.8-27b-q4-128k.Modelfile");

        Assert.NotNull(model);
        Assert.Equal("qwen3.8:27b-q4-128k", model.Name);
        Assert.Equal("Standard-Qwen 3.8 27B ohne Anpassungen. Allgemeiner Chat.", model.Description);
        Assert.Equal("qwen3.8-27b-q4-128k.Modelfile", model.File);
    }

    [Fact]
    public void Parse_WithoutPurpose_HasEmptyDescription()
    {
        var model = ModelfileReader.Parse(["# my:model", "FROM base"], "x.Modelfile");

        Assert.NotNull(model);
        Assert.Equal("my:model", model.Name);
        Assert.Equal("", model.Description);
    }

    [Fact]
    public void Parse_WithoutHeader_ReturnsNull()
    {
        Assert.Null(ModelfileReader.Parse(["FROM base", "PARAMETER num_ctx 4096"], "x.Modelfile"));
    }

    [Fact]
    public void ReadDirectory_ReadsRepositoryModels()
    {
        var dir = Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "..", "..", "models");
        if (!Directory.Exists(dir)) return;

        var models = ModelfileReader.ReadDirectory(dir);

        Assert.NotEmpty(models);
        Assert.All(models, m => Assert.Contains(':', m.Name));
    }
}
