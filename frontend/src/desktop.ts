const FLAG = "im_desktop";

function platformClass(): string {
  const ua = navigator.userAgent;
  const plat = navigator.platform || "";
  if (/Mac|iPhone|iPad/.test(ua) || plat.startsWith("Mac")) return "desktop-mac";
  if (/Win/.test(ua) || plat.startsWith("Win")) return "desktop-win";
  return "desktop-linux";
}

export function isDesktopApp(): boolean {
  return document.documentElement.classList.contains("desktop-app");
}

export function markDesktopApp(): void {
  const fromQuery = new URLSearchParams(window.location.search).get("desktop") === "1";
  const fromBridge = "pywebview" in window;
  if (fromQuery) sessionStorage.setItem(FLAG, "1");
  const fromFlag = sessionStorage.getItem(FLAG) === "1";
  if (!(fromQuery || fromBridge || fromFlag)) return;
  document.documentElement.classList.add("desktop-app", platformClass());
}

markDesktopApp();
window.addEventListener("pywebviewready", markDesktopApp);
