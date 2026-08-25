/**
 * Wallust Theme — desktop half.
 *
 * Shows the current wallpaper-derived palette and lets you regenerate /
 * apply it. Backend lives at /api/plugins/wallust-theme (plugin_api.py).
 * If the Python plugin is off, Apply falls back to `hermes wallust-theme apply`
 * via cli.exec.
 */

import {
  Badge,
  Button,
  Codicon,
  contrastRatio,
  GlyphSpinner,
  haptic,
  host,
  KEYBINDS_AREA,
  mixOklab,
  normalizeHex,
  PALETTE_AREA,
  readableOn,
  requestTheme,
  SegmentedControl,
  THEMES_AREA,
  Tip,
  usePluginI18n,
  useQuery,
  useQueryClient
} from '@hermes/plugin-sdk'
import { useState } from 'react'
import { jsx, jsxs } from 'react/jsx-runtime'

const ID = 'wallust-theme'
const STATUS_KEY = [ID, 'status']
const DEFAULT_SKIN = 'wallust'

// Cache key for the last known palette, so a relaunch can resolve (and restore)
// the skin before the gateway has answered /status. See restoreSkin below.
const CACHE_KEY = 'palette-cache'

let pluginCtx = null

function basename(path) {
  if (!path) return ''
  const parts = String(path).split(/[/\\]/)
  return parts[parts.length - 1] || path
}

function Swatch({ hex, label }) {
  return jsxs('div', {
    className: 'flex min-w-0 flex-col gap-1',
    children: [
      jsx('div', {
        className: 'h-8 w-full rounded-md border border-(--ui-stroke-secondary)',
        style: { background: hex || 'transparent' }
      }),
      label
        ? jsx('div', {
            className: 'truncate text-[0.625rem] text-(--ui-text-quaternary)',
            children: label
          })
        : null
    ]
  })
}

function PaletteRow({ colors16 }) {
  if (!Array.isArray(colors16) || !colors16.length) return null
  return jsx('div', {
    className: 'grid grid-cols-8 gap-1',
    children: colors16.map((hex, i) =>
      jsx(
        Tip,
        {
          label: `${i}: ${hex}`,
          children: jsx('div', {
            className: 'h-5 rounded-sm border border-(--ui-stroke-secondary)',
            style: { background: hex }
          })
        },
        `${i}-${hex}`
      )
    )
  })
}

function SemanticGrid({ colors }) {
  if (!colors || typeof colors !== 'object') return null
  const keys = [
    ['background', 'bg'],
    ['ui_text', 'text'],
    ['ui_accent', 'accent'],
    ['ui_border', 'border'],
    ['ui_ok', 'ok'],
    ['ui_warn', 'warn'],
    ['ui_error', 'err'],
    ['ui_thinking', 'think']
  ]
  return jsx('div', {
    className: 'grid grid-cols-4 gap-2',
    children: keys.map(([key, label]) => jsx(Swatch, { hex: colors[key], label }, key))
  })
}

// ── Skin → desktop theme ────────────────────────────────────────────────────
// The desktop registers backend skins only for the CURRENT connection, and
// `gateway.ready` seeds them WITHOUT applying (so a connect never stomps a
// manual pick). On a cold start that ordering loses: the boot paint reads the
// persisted name `wallust`, can't resolve it yet (nothing registered), and
// `normalizeSkin` silently falls back to the default. The activation event
// never comes either, because from the backend's point of view the skin never
// changed — it's the same `display.skin` it had before the restart.
//
// So the plugin contributes the theme itself. A `themes` contribution is part
// of the merged registry `resolveTheme` reads, and the plugin registers during
// app boot rather than on gateway connect, which is early enough for the name
// to resolve. `restoreSkin` then re-affirms the pick for the run where the
// fallback already happened.

const ACCENT_MIN_CONTRAST = 4.5

const pick = (colors, keys, backdrop) => {
  for (const key of keys) {
    const value = normalizeHex(colors[key], backdrop)

    if (value) {
      return value
    }
  }

  return null
}

// Nudge a color until it clears `min` contrast on `bg`, walking toward whichever
// end (white/black) is readable there. Mirrors the core converter's intent so
// small uppercase accent labels stay legible on a wallpaper-derived surface.
function ensureContrast(color, bg, min) {
  if (contrastRatio(color, bg) >= min) {
    return color
  }

  const target = readableOn(bg)
  let out = color

  for (let step = 1; step <= 20; step += 1) {
    out = mixOklab(color, target, step / 20)

    if (contrastRatio(out, bg) >= min) {
      return out
    }
  }

  return out
}

const titleCase = name => name.charAt(0).toUpperCase() + name.slice(1)

/**
 * Convert a resolved Hermes skin into a DesktopTheme, or null when it carries
 * no usable colors. Same token seeding as the core skin converter: derive every
 * glass/shadcn surface by mixing toward background/foreground.
 */
function skinToTheme(skin) {
  const name = String((skin && skin.name) || '').trim()
  const colors = skin && skin.colors

  if (!name || !colors || typeof colors !== 'object') {
    return null
  }

  const seededBg = pick(colors, ['background', 'status_bar_bg'], '#000000')
  const fgSeed = pick(colors, ['ui_text', 'banner_text', 'status_bar_text'], seededBg || '#000000')
  const background = seededBg || '#141414'
  const dark = contrastRatio(background, '#ffffff') > contrastRatio(background, '#000000')
  const foreground = fgSeed || (dark ? '#e6e6e6' : '#161616')

  const accentSeed = pick(colors, ['ui_accent', 'banner_accent', 'banner_title'], background) || foreground
  const sidebar = mixOklab(background, foreground, dark ? 0.02 : 0.012)
  const accent = ensureContrast(accentSeed, sidebar, ACCENT_MIN_CONTRAST)
  const border = pick(colors, ['ui_border', 'banner_border'], background) || mixOklab(background, foreground, 0.16)
  const mutedForeground = pick(colors, ['banner_dim', 'session_border'], background) || mixOklab(foreground, background, 0.45)
  const destructive = pick(colors, ['ui_error'], background) || '#e25563'

  const palette = {
    background,
    foreground,
    card: mixOklab(background, foreground, dark ? 0.04 : 0.025),
    cardForeground: foreground,
    muted: mixOklab(background, foreground, dark ? 0.06 : 0.04),
    mutedForeground,
    popover: mixOklab(background, foreground, dark ? 0.08 : 0.05),
    popoverForeground: foreground,
    primary: accent,
    primaryForeground: readableOn(accent),
    secondary: mixOklab(accent, background, dark ? 0.72 : 0.86),
    secondaryForeground: foreground,
    accent: mixOklab(accent, background, dark ? 0.82 : 0.88),
    accentForeground: foreground,
    border,
    input: pick(colors, ['completion_menu_bg'], background) || mixOklab(background, foreground, dark ? 0.1 : 0.06),
    ring: accent,
    midground: accent,
    midgroundForeground: readableOn(accent),
    composerRing: accent,
    destructive,
    destructiveForeground: readableOn(destructive),
    sidebarBackground: sidebar,
    sidebarBorder: border,
    userBubble: mixOklab(background, accent, dark ? 0.18 : 0.12),
    userBubbleBorder: border
  }

  return {
    name,
    label: titleCase(name),
    description: 'Wallust palette',
    // A skin is single-mode: same palette in both slots so the light/dark
    // toggle doesn't invert a wallpaper-derived palette.
    colors: palette,
    darkColors: palette
  }
}

// The live theme contribution + its disposer, so a fresh palette replaces the
// previous registration instead of stacking.
let themeDispose = null

/** Register `skin` as a desktop theme and cache it for the next cold start. */
function publishTheme(skin) {
  const theme = skinToTheme(skin)

  if (!theme || !pluginCtx) {
    return null
  }

  if (themeDispose) {
    themeDispose()
    themeDispose = null
  }

  themeDispose = pluginCtx.register({ id: `theme-${theme.name}`, area: THEMES_AREA, data: theme })
  pluginCtx.storage.set(CACHE_KEY, skin)

  return theme
}

/**
 * Re-affirm the skin as the painted theme.
 *
 * Only acts when the desktop's own persisted pick IS this skin — the whole
 * point is restoring the user's choice after the boot paint dropped it, never
 * overriding a deliberate switch to another theme. `requestTheme` returns false
 * for a name that doesn't resolve, which is why registration comes first.
 */
function restoreSkin(name) {
  let persisted = null

  try {
    persisted = window.localStorage.getItem('hermes-desktop-theme-v2')
  } catch {
    // Restricted storage: skip the restore rather than guess at intent.
    return false
  }

  return persisted === name ? requestTheme(name) : false
}

async function applyViaRest(style) {
  return pluginCtx.rest('/apply', {
    method: 'POST',
    body: { style, activate: true },
    timeoutMs: 90000
  })
}

async function applyViaCli(style) {
  const argv = ['wallust-theme', 'apply', '--json']
  if (style && style !== 'auto') argv.push('--style', style)
  const res = await host.request('cli.exec', { argv, timeout: 90 })
  if (res?.blocked) {
    throw new Error(res.hint || 'cli.exec blocked')
  }
  if (typeof res?.code === 'number' && res.code !== 0) {
    throw new Error(res.output || `exit ${res.code}`)
  }
  const text = String(res?.output || '').trim()
  try {
    return JSON.parse(text)
  } catch {
    return { ok: true, raw: text }
  }
}

function WallustPane() {
  const t = usePluginI18n(ID)
  const queryClient = useQueryClient()
  const [style, setStyle] = useState('auto')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const statusQuery = useQuery({
    queryKey: STATUS_KEY,
    queryFn: async () => {
      try {
        return await pluginCtx.rest('/status', { timeoutMs: 8000 })
      } catch {
        const res = await host.request('cli.exec', {
          argv: ['wallust-theme', 'status', '--json'],
          timeout: 20
        })
        const text = String(res?.output || '').trim()
        return JSON.parse(text)
      }
    },
    refetchInterval: 8000
  })

  const data = statusQuery.data || {}
  const wallpaper = data.wallpaper || data.last_wallpaper
  const colors = data.colors
  const colors16 = data.colors16

  const onApply = async () => {
    if (busy) return
    setBusy(true)
    setError('')
    haptic('tap')
    try {
      let result
      try {
        result = await applyViaRest(style)
      } catch {
        result = await applyViaCli(style)
      }
      if (result && result.ok === false) {
        throw new Error(result.error || t('applyFailed'))
      }
      // Re-publish so the freshly extracted palette is what a future cold start
      // restores. The backend also emits skin.changed for the live repaint.
      if (result && result.colors) {
        publishTheme({ colors: result.colors, name: String(result.skin || DEFAULT_SKIN) })
      }
      host.notify({ kind: 'success', message: t('applied') })
      await queryClient.invalidateQueries({ queryKey: STATUS_KEY })
    } catch (err) {
      const message = err?.message || String(err)
      setError(message)
      host.notify({ kind: 'error', message: t('applyFailed') })
    } finally {
      setBusy(false)
    }
  }

  return jsxs('div', {
    className: 'flex h-full min-h-0 flex-col gap-3 p-3 text-sm',
    children: [
      jsxs('div', {
        className: 'flex items-center justify-between gap-2',
        children: [
          jsxs('div', {
            className: 'flex min-w-0 items-center gap-2',
            children: [
              jsx(Codicon, { name: 'symbol-color', className: 'text-(--ui-text-tertiary)' }),
              jsx('div', { className: 'font-medium', children: t('paneTitle') })
            ]
          }),
          data.watching
            ? jsx(Badge, { variant: 'muted', children: t('watching') })
            : null
        ]
      }),
      jsxs('div', {
        className: 'min-w-0 text-(--ui-text-tertiary)',
        children: [
          jsx('div', {
            className: 'truncate',
            title: wallpaper || '',
            children: wallpaper ? basename(wallpaper) : t('noWallpaper')
          }),
          data.generated_at
            ? jsx('div', {
                className: 'text-[0.6875rem] text-(--ui-text-quaternary)',
                children: data.generated_at
              })
            : null
        ]
      }),
      jsx(SegmentedControl, {
        value: style,
        onChange: setStyle,
        options: [
          { id: 'auto', label: t('styleAuto') },
          { id: 'dark', label: t('styleDark') },
          { id: 'light', label: t('styleLight') }
        ]
      }),
      jsx(SemanticGrid, { colors }),
      jsx(PaletteRow, { colors16 }),
      error
        ? jsx('div', {
            className: 'text-[0.75rem] text-(--ui-text-tertiary)',
            children: error
          })
        : null,
      jsx(Button, {
        size: 'sm',
        disabled: busy,
        onClick: onApply,
        children: busy
          ? jsxs('span', {
              className: 'inline-flex items-center gap-1.5',
              children: [jsx(GlyphSpinner, { className: 'size-3' }), t('applying')]
            })
          : t('apply')
      })
    ]
  })
}

export default {
  id: ID,
  name: 'Wallust Theme',
  description: 'Match Hermes colors to the wallpaper via wallust',
  defaultEnabled: true,
  register(ctx) {
    pluginCtx = ctx
    ctx.i18n.register({
      en: {
        paneTitle: 'Wallust',
        apply: 'Apply from wallpaper',
        applying: 'Extracting…',
        applied: 'Hermes restyled from wallpaper',
        applyFailed: 'Wallust apply failed',
        watching: 'live',
        noWallpaper: 'No wallpaper detected',
        styleAuto: 'Auto',
        styleDark: 'Dark',
        styleLight: 'Light'
      },
      zh: {
        paneTitle: 'Wallust',
        apply: '从壁纸套用',
        applying: '抽色中…',
        applied: '已按壁纸重绘 Hermes',
        applyFailed: 'Wallust 套用失败',
        watching: '跟随',
        noWallpaper: '未检测到壁纸',
        styleAuto: '跟随',
        styleDark: '深色',
        styleLight: '浅色'
      }
    })

    // Restore the skin on boot. Two rungs, because the cache is fast but the
    // backend is authoritative:
    //
    //   1. The cached palette from the last run registers synchronously, so the
    //      name resolves and the theme repaints without waiting on the network.
    //   2. /status re-publishes from the skin file on disk, catching a palette
    //      that changed while the app was closed (wallpaper hook, another
    //      surface). Same-name re-registration just replaces the definition.
    //
    // Both go through `restoreSkin`, which no-ops unless the desktop's own
    // persisted pick is this skin — a user on another theme is left alone.
    const cached = ctx.storage.get(CACHE_KEY, null)

    if (cached) {
      const theme = publishTheme(cached)

      if (theme) {
        restoreSkin(theme.name)
      }
    }

    void (async () => {
      try {
        const status = await pluginCtx.rest('/status', { timeoutMs: 8000 })
        const name = String((status && status.skin) || DEFAULT_SKIN)
        const colors = status && status.colors

        if (colors) {
          const theme = publishTheme({ colors, name })

          if (theme) {
            restoreSkin(theme.name)
          }
        }
      } catch {
        // Backend down / plugin API off: the cached rung already ran, and the
        // pane's own status query retries on its interval.
      }
    })()

    ctx.register({
      id: 'pane',
      area: 'panes',
      title: 'wallust',
      data: { placement: 'right', width: '260px' },
      render: () => jsx(WallustPane, {})
    })

    ctx.register({
      id: 'apply-cmd',
      area: PALETTE_AREA,
      data: {
        id: 'wallust-theme.apply',
        label: 'Apply wallust theme from wallpaper',
        keywords: ['wallust', 'wallpaper', 'theme', 'skin', 'palette'],
        run: async () => {
          try {
            let result
            try {
              result = await applyViaRest('auto')
            } catch {
              result = await applyViaCli('auto')
            }
            if (result && result.ok === false) throw new Error(result.error)
            host.notify({ kind: 'success', message: 'Hermes restyled from wallpaper' })
          } catch (err) {
            host.notify({ kind: 'error', message: err?.message || 'Wallust apply failed' })
          }
        }
      }
    })

    ctx.register({
      id: 'apply-key',
      area: KEYBINDS_AREA,
      data: {
        id: 'wallust-theme.apply',
        label: 'Apply wallust theme from wallpaper',
        category: 'Wallust Theme',
        defaults: ['mod+shift+w'],
        run: async () => {
          try {
            await applyViaRest('auto')
            host.notify({ kind: 'success', message: 'Hermes restyled from wallpaper' })
          } catch {
            try {
              await applyViaCli('auto')
              host.notify({ kind: 'success', message: 'Hermes restyled from wallpaper' })
            } catch (err) {
              host.notify({ kind: 'error', message: err?.message || 'Wallust apply failed' })
            }
          }
        }
      }
    })
  }
}
