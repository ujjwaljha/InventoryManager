const PRESS = "is-pressed";
const TARGETS = "button, a.btn, .chip, .pick-option, .more-link, a.result-row, .sidebar a, .icon-btn";

function targetOf(event: Event): HTMLElement | null {
  const node = (event.target as HTMLElement | null)?.closest?.(TARGETS);
  if (!(node instanceof HTMLElement)) return null;
  if (node.closest("[disabled], [aria-disabled='true']")) return null;
  if ("disabled" in node && (node as HTMLButtonElement).disabled) return null;
  return node;
}

export function installClickFeel(): void {
  document.addEventListener(
    "pointerdown",
    (event) => {
      if (event.pointerType === "mouse" && event.button !== 0) return;
      const el = targetOf(event);
      if (!el) return;
      el.classList.add(PRESS);
      window.setTimeout(() => el.classList.remove(PRESS), 180);
    },
    true,
  );
}
