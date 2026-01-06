using System.Text.Json;

namespace CrosshairOverlay;

public sealed class OverlaySettings
{
    public bool enabled { get; set; } = true;
    public int size { get; set; } = 8;
    public string color { get; set; } = "white";
    public string style { get; set; } = "Dot";
    public double opacity { get; set; } = 1.0;
    public int outline { get; set; } = 0;

    public static OverlaySettings Load(string path)
    {
        try
        {
            if (!File.Exists(path)) return new OverlaySettings();
            var json = File.ReadAllText(path);
            if (string.IsNullOrWhiteSpace(json)) return new OverlaySettings();
            return JsonSerializer.Deserialize<OverlaySettings>(json) ?? new OverlaySettings();
        }
        catch
        {
            return new OverlaySettings();
        }
    }
}
