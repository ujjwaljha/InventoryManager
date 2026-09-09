export type ThemePref = "system" | "light" | "dark";

const KEY = "im_theme";

export function readThemePref(): ThemePref {
  try {
    const stored = localStorage.getItem(KEY);
    if (stored === "light" || stored === "dark" || stored === "system") return stored;
  } catch {
    /* ignore */
  }
  return "system";
}

function osDark(): boolean {
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;
}

export function resolvedDark(pref: ThemePref = readThemePref()): boolean {
  if (pref === "dark") return true;
  if (pref === "light") return false;
  return osDark();
}

export function applyTheme(pref: ThemePref = readThemePref()): void {
  const dark = resolvedDark(pref);
  const root = document.documentElement;
  root.classList.toggle("theme-dark", dark);
  root.style.colorScheme = dark ? "dark" : "light";
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute("content", dark ? "#14110e" : "#1e4d3a");
}

export function writeThemePref(pref: ThemePref): void {
  try {
    localStorage.setItem(KEY, pref);
  } catch {
    /* ignore */
  }
  applyTheme(pref);
}

export function installTheme(): void {
  applyTheme();
  const mq = window.matchMedia?.("(prefers-color-scheme: dark)");
  mq?.addEventListener?.("change", () => {
    if (readThemePref() === "system") applyTheme("system");
  });
}
