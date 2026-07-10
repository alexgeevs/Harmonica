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
