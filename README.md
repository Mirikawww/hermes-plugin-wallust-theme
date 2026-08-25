# Wallust Theme

Hermes plugin that extracts a palette from an image with
[wallust](https://codeberg.org/explosion-mental/wallust) (k-means / salience /
ANSI) and applies it as a Hermes **skin** — CLI, TUI, and desktop together.

```bash
hermes plugins install Mirikawww/hermes-plugin-wallust-theme --enable
```

Then pick **Wallust** in Appearance, or run:

```bash
hermes wallust-theme apply
```

One-click (desktop): [Install in Hermes](hermes://plugin/install?repo=Mirikawww/hermes-plugin-wallust-theme&enable=1)

## Requirements

- [Hermes Agent](https://hermes-agent.nousresearch.com/)
- [`wallust`](https://codeberg.org/explosion-mental/wallust) on `PATH` (or `~/.local/bin/wallust`)
- An image — defaults to the current GNOME wallpaper (`org.gnome.desktop.background`)

## What it does

1. Runs `wallust` against the wallpaper (or any image you pass).
2. Maps color0–15 onto Hermes tokens (`background`, `ui_accent`, status colors, syntax, borders).
3. Writes `$HERMES_HOME/skins/wallust.yaml` and `hermes config set display.skin wallust`.
   The gateway watcher repaints every surface within ~1s.

Hermes only paints the **active** skin. Stay on `wallust` if you want wallpaper
changes to keep restyling the UI. Revert with `hermes config set display.skin default`.

The desktop half also **restores the skin on relaunch**. The desktop paints its
theme before the gateway connects, and a backend skin is only registered per
connection — so a wallpaper-derived skin isn't resolvable at that moment and the
app silently falls back to its default theme, even with `display.skin: wallust`
set. The plugin contributes the palette as a real desktop theme at load time and
re-affirms it, but only when the desktop's own persisted pick is this skin, so
switching to another theme is still respected.

## Surfaces

| Surface | How |
|---|---|
| Desktop pane | Settings → Plugins → Wallust Theme |
| ⌘K | “Apply wallust theme from wallpaper” (`Mod+Shift+W`) |
| Slash | `/wallust-theme apply` · `/wallust-theme status` |
| CLI | `hermes wallust-theme apply` · `hermes wallust-theme status` |
| Agent tools | `wallust_theme_apply` · `wallust_theme_status` |

## Follow wallpaper changes (Linux / GNOME)

If you already run wallust when the wallpaper changes, add this template + hook
so Hermes restyles with kitty (or whatever else you template).

Copy `templates/hermes-palette.json` into `~/.config/wallust/templates/` and in
`~/.config/wallust/wallust.toml`:

```toml
[templates]
hermes_palette = { template = 'hermes-palette.json', target = '~/.hermes/plugin-data/wallust-theme/palette.json' }

[hooks]
hermes_skin = "python3 ~/.hermes/plugins/wallust-theme/scripts/from-palette.py"
```

Without that hook, run `hermes wallust-theme apply` (or the desktop pane / ⌘K)
whenever you want a new palette.

Optional in-process watcher (only if you do **not** already have a wallpaper
systemd unit):

```yaml
plugins:
  entries:
    wallust-theme:
      settings:
        auto_watch: true
```

## Settings (`plugins.entries.wallust-theme.settings`)

- `auto_watch` (bool, default false) — poll GNOME wallpaper from inside Hermes
- `style` (`auto` / `dark` / `light`)
- `skin_name` (default `wallust`)

## Layout

```
plugin.yaml              # manifest
__init__.py              # tools, slash, CLI
colors.py                # wallust 16 → Hermes tokens
engine.py                # run wallust, write skin, activate
desktop/plugin.js        # desktop pane + palette command
dashboard/plugin_api.py  # /api/plugins/wallust-theme
scripts/from-palette.py  # wallust hook consumer
templates/hermes-palette.json
```
