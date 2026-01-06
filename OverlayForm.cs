using System;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Runtime.InteropServices;
using System.Windows.Forms;

namespace CrosshairOverlay;

public sealed class OverlayForm : Form
{
    private readonly string _settingsPath;
    private OverlaySettings _s = new();
    private readonly FileSystemWatcher _watcher;
    private readonly System.Windows.Forms.Timer _pollTimer;

    public OverlayForm()
    {
        // Always resolve settings relative to the EXE folder, not the shell's working directory.
        _settingsPath = Path.Combine(AppContext.BaseDirectory, "overlay_settings.json");

        FormBorderStyle = FormBorderStyle.None;
        ShowInTaskbar = false;
        TopMost = true;
        StartPosition = FormStartPosition.Manual;

        // Colorkey transparency (simple + stable). Use a very uncommon key color.
        BackColor = Color.Magenta;
        TransparencyKey = Color.Magenta;

        // Avoid the "purple fringe" by drawing with NO anti-aliasing.
        // (Anti-aliased edges would blend with the colorkey color.)
        SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.UserPaint, true);

        // Small always-centered window; big enough for max slider.
        ClientSize = new Size(160, 160);
        Recenter();

        // Click-through + no-activate.
        ApplyExtendedStyles();

        // Load initial settings.
        _s = OverlaySettings.Load(_settingsPath);
        ApplyEnabled();

        // Watcher for instant updates.
        _watcher = new FileSystemWatcher(AppContext.BaseDirectory, "overlay_settings.json");
        _watcher.NotifyFilter = NotifyFilters.LastWrite | NotifyFilters.CreationTime | NotifyFilters.Size | NotifyFilters.FileName;
        _watcher.Changed += (_, __) => BeginInvoke(new Action(ReloadSettingsSafe));
        _watcher.Created += (_, __) => BeginInvoke(new Action(ReloadSettingsSafe));
        _watcher.Renamed += (_, __) => BeginInvoke(new Action(ReloadSettingsSafe));
        _watcher.EnableRaisingEvents = true;

        // Small poll (backup for filesystems that miss events).
        _pollTimer = new System.Windows.Forms.Timer();
        _pollTimer.Interval = 250;
        _pollTimer.Tick += (_, __) => ReloadSettingsSafe();
        _pollTimer.Start();
    }

    protected override bool ShowWithoutActivation => true;

    private void ReloadSettingsSafe()
    {
        // File writes can race; retry lightly.
        for (int i = 0; i < 3; i++)
        {
            try
            {
                var ns = OverlaySettings.Load(_settingsPath);
                _s = ns;
                ApplyEnabled();
                Recenter();
                Invalidate();
                return;
            }
            catch
            {
                System.Threading.Thread.Sleep(20);
            }
        }
    }

    private void ApplyEnabled()
    {
        if (_s.enabled)
        {
            if (!Visible) Show();
            Opacity = Math.Max(0.1, Math.Min(1.0, _s.opacity));
        }
        else
        {
            Hide();
        }
    }

    private void Recenter()
    {
        var screen = Screen.PrimaryScreen?.Bounds ?? new Rectangle(0, 0, 1920, 1080);
        var x = screen.Left + (screen.Width / 2) - (Width / 2);
        var y = screen.Top + (screen.Height / 2) - (Height / 2);
        Location = new Point(x, y);
    }

    protected override void OnShown(EventArgs e)
    {
        base.OnShown(e);
        Recenter();
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        // Clear with colorkey so everything else is transparent.
        e.Graphics.Clear(Color.Magenta);

        if (!_s.enabled) return;

        // No AA to avoid colorkey fringe.
        e.Graphics.SmoothingMode = SmoothingMode.None;
        e.Graphics.PixelOffsetMode = PixelOffsetMode.Half;

        var c = new Point(ClientSize.Width / 2, ClientSize.Height / 2);

        int arm = Math.Clamp(_s.size, 2, 70);
        int thickness = Math.Max(2, arm / 5);
        int outline = Math.Clamp(_s.outline, 0, 10);

        using var penMain = new Pen(ParseColor(_s.color), thickness) { StartCap = LineCap.Square, EndCap = LineCap.Square };
        using var penOutline = new Pen(Color.Black, thickness + outline) { StartCap = LineCap.Square, EndCap = LineCap.Square };

        void DrawLine(Pen p, int x1, int y1, int x2, int y2) => e.Graphics.DrawLine(p, x1, y1, x2, y2);

        if (string.Equals(_s.style, "Dot", StringComparison.OrdinalIgnoreCase))
        {
            int r = thickness; // dot radius tied to thickness
            if (outline > 0)
            {
                using var b = new SolidBrush(Color.Black);
                e.Graphics.FillEllipse(b, c.X - r - outline, c.Y - r - outline, (r + outline) * 2, (r + outline) * 2);
            }
            using var b2 = new SolidBrush(ParseColor(_s.color));
            e.Graphics.FillEllipse(b2, c.X - r, c.Y - r, r * 2, r * 2);
            return;
        }

        if (string.Equals(_s.style, "Plus", StringComparison.OrdinalIgnoreCase))
        {
            if (outline > 0)
            {
                DrawLine(penOutline, c.X, c.Y - arm, c.X, c.Y + arm);
                DrawLine(penOutline, c.X - arm, c.Y, c.X + arm, c.Y);
            }
            DrawLine(penMain, c.X, c.Y - arm, c.X, c.Y + arm);
            DrawLine(penMain, c.X - arm, c.Y, c.X + arm, c.Y);
            return;
        }

        // Cross
        if (outline > 0)
        {
            DrawLine(penOutline, c.X - arm, c.Y - arm, c.X + arm, c.Y + arm);
            DrawLine(penOutline, c.X - arm, c.Y + arm, c.X + arm, c.Y - arm);
        }
        DrawLine(penMain, c.X - arm, c.Y - arm, c.X + arm, c.Y + arm);
        DrawLine(penMain, c.X - arm, c.Y + arm, c.X + arm, c.Y - arm);
    }

    private static Color ParseColor(string? name)
    {
        return (name ?? "").ToLowerInvariant() switch
        {
            "red" => Color.Red,
            "green" => Color.Lime,
            "blue" => Color.DodgerBlue,
            _ => Color.White
        };
    }

    private void ApplyExtendedStyles()
    {
        // Make the window click-through and avoid focus stealing.
        const int GWL_EXSTYLE = -20;
        const int WS_EX_LAYERED = 0x00080000;
        const int WS_EX_TRANSPARENT = 0x00000020;
        const int WS_EX_TOOLWINDOW = 0x00000080;
        const int WS_EX_NOACTIVATE = 0x08000000;

        var ex = GetWindowLong(Handle, GWL_EXSTYLE);
        ex |= WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE;
        SetWindowLong(Handle, GWL_EXSTYLE, ex);
    }

    protected override CreateParams CreateParams
    {
        get
        {
            var cp = base.CreateParams;
            // Avoid activation
            cp.ExStyle |= 0x08000000; // WS_EX_NOACTIVATE
            return cp;
        }
    }

    [DllImport("user32.dll")]
    private static extern int GetWindowLong(IntPtr hWnd, int nIndex);

    [DllImport("user32.dll")]
    private static extern int SetWindowLong(IntPtr hWnd, int nIndex, int dwNewLong);
}
