// Client-side appearance: three colour slots (main surface, sidebar, player bar) plus dark
// mode, applied as CSS variables on <html> and remembered per device in localStorage.
//
// The palettes are deliberately limited so every combination stays readable: surface options
// are all light enough for the dark ink, bar options are all dark enough for the light text
// the bars use. Dark mode swaps the surface variables wholesale (see :root[data-dark] in
// styles.css), which is why the surface swatches are disabled while it is on.

export type ThemeSelection = {
  surface: string;
  sidebar: string;
  playerbar: string;
  dark: boolean;
};

export type SurfaceOption = {
  key: string;
  name: string;
  bg: string;
  panelSoft: string;
  line: string;
  lineSoft: string;
};

export type BarOption = {
  key: string;
  name: string;
  base: string;
  raised: string;
};

export const SURFACE_OPTIONS: SurfaceOption[] = [
  { key: "mint", name: "Mint", bg: "#eef3f1", panelSoft: "#eef4f1", line: "#d8e2dd", lineSoft: "#e4ebe7" },
  { key: "paper", name: "Paper", bg: "#f7f6f3", panelSoft: "#f2f1ec", line: "#e0ded5", lineSoft: "#eae8e1" },
  { key: "sand", name: "Sand", bg: "#f4efe6", panelSoft: "#f1ece1", line: "#e2dbc9", lineSoft: "#ebe4d6" },
  { key: "sky", name: "Sky", bg: "#edf1f5", panelSoft: "#edf2f6", line: "#d8e0e8", lineSoft: "#e3e9ef" },
  { key: "blossom", name: "Blossom", bg: "#f5eef0", panelSoft: "#f3edee", line: "#e5d8dc", lineSoft: "#ece1e4" }
];

export const BAR_OPTIONS: BarOption[] = [
  { key: "deep-green", name: "Deep green", base: "#20302f", raised: "#283c3a" },
  { key: "ink-green", name: "Ink green", base: "#1a2827", raised: "#223432" },
  { key: "charcoal", name: "Charcoal", base: "#24282a", raised: "#2e3437" },
  { key: "midnight", name: "Midnight", base: "#1e2836", raised: "#273548" },
  { key: "plum", name: "Plum", base: "#2d2435", raised: "#3a2f45" },
  { key: "espresso", name: "Espresso", base: "#2a231d", raised: "#362e26" }
];

export const DEFAULT_THEME: ThemeSelection = {
  surface: "mint",
  sidebar: "deep-green",
  playerbar: "ink-green",
  dark: false
};

// Named appearance presets: each is a full ThemeSelection built only from the existing surface
// and bar options above, so no new colours are introduced. Picking one applies all four fields
// at once, exactly like choosing the swatches by hand. The first preset is the default look, so
// a fresh install starts on "Classic". At least one preset is dark.
export type ThemePreset = {
  key: string;
  name: string;
  selection: ThemeSelection;
};

export const THEME_PRESETS: ThemePreset[] = [
  { key: "classic", name: "Classic", selection: { surface: "mint", sidebar: "deep-green", playerbar: "ink-green", dark: false } },
  { key: "charcoal", name: "Charcoal", selection: { surface: "paper", sidebar: "charcoal", playerbar: "charcoal", dark: false } },
  { key: "espresso", name: "Espresso", selection: { surface: "sand", sidebar: "espresso", playerbar: "espresso", dark: false } },
  { key: "midnight", name: "Midnight", selection: { surface: "sky", sidebar: "midnight", playerbar: "midnight", dark: false } },
  { key: "plum", name: "Plum", selection: { surface: "blossom", sidebar: "plum", playerbar: "plum", dark: false } },
  { key: "night", name: "Night", selection: { surface: "mint", sidebar: "deep-green", playerbar: "ink-green", dark: true } }
];

/** Returns the preset whose full selection matches the current theme exactly, if any. */
export function matchThemePreset(theme: ThemeSelection): string | null {
  for (const preset of THEME_PRESETS) {
    const s = preset.selection;
    if (
      s.surface === theme.surface &&
      s.sidebar === theme.sidebar &&
      s.playerbar === theme.playerbar &&
      s.dark === theme.dark
    ) {
      return preset.key;
    }
  }
  return null;
}

// Background colour a preset chip shows for its surface dot. Dark presets preview the dark
// background (see :root[data-dark] in styles.css) rather than their stored light surface, which
// dark mode overrides anyway.
const DARK_PREVIEW_BG = "#141c1b";

export function themePresetPreview(preset: ThemePreset): { surface: string; sidebar: string; playerbar: string } {
  const surface = SURFACE_OPTIONS.find((o) => o.key === preset.selection.surface) ?? SURFACE_OPTIONS[0];
  const sidebar = BAR_OPTIONS.find((o) => o.key === preset.selection.sidebar) ?? BAR_OPTIONS[0];
  const playerbar = BAR_OPTIONS.find((o) => o.key === preset.selection.playerbar) ?? BAR_OPTIONS[1];
  return {
    surface: preset.selection.dark ? DARK_PREVIEW_BG : surface.bg,
    sidebar: sidebar.base,
    playerbar: playerbar.base
  };
}

const STORAGE_KEY = "harmonica.theme";

// Surface-side variables the light swatches (or the dark block in styles.css) control. Cleared
// from the inline style before each apply so dark mode falls through to :root[data-dark].
const SURFACE_VARS = ["--bg", "--panel-soft", "--line", "--line-soft"];

export function loadTheme(): ThemeSelection {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<ThemeSelection>;
      return {
        surface: SURFACE_OPTIONS.some((o) => o.key === parsed.surface)
          ? (parsed.surface as string)
          : DEFAULT_THEME.surface,
        sidebar: BAR_OPTIONS.some((o) => o.key === parsed.sidebar)
          ? (parsed.sidebar as string)
          : DEFAULT_THEME.sidebar,
        playerbar: BAR_OPTIONS.some((o) => o.key === parsed.playerbar)
          ? (parsed.playerbar as string)
          : DEFAULT_THEME.playerbar,
        dark: Boolean(parsed.dark)
      };
    }
  } catch {
    /* localStorage unavailable or corrupted; use the default look. */
  }
  return DEFAULT_THEME;
}

export function saveTheme(theme: ThemeSelection): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(theme));
  } catch {
    /* private mode; the theme just won't persist. */
  }
}

export function applyTheme(theme: ThemeSelection): void {
  const root = document.documentElement;
  const style = root.style;
  const surface = SURFACE_OPTIONS.find((o) => o.key === theme.surface) ?? SURFACE_OPTIONS[0];
  const sidebar = BAR_OPTIONS.find((o) => o.key === theme.sidebar) ?? BAR_OPTIONS[0];
  const playerbar = BAR_OPTIONS.find((o) => o.key === theme.playerbar) ?? BAR_OPTIONS[1];

  for (const name of SURFACE_VARS) {
    style.removeProperty(name);
  }
  if (theme.dark) {
    root.setAttribute("data-dark", "");
  } else {
    root.removeAttribute("data-dark");
    style.setProperty("--bg", surface.bg);
    style.setProperty("--panel-soft", surface.panelSoft);
    style.setProperty("--line", surface.line);
    style.setProperty("--line-soft", surface.lineSoft);
  }
  style.setProperty("--sidebar", sidebar.base);
  style.setProperty("--sidebar-2", sidebar.raised);
  style.setProperty("--playerbar", playerbar.base);
  style.setProperty("--playerbar-2", playerbar.raised);
}
