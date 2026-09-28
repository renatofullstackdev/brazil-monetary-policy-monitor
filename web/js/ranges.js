export function setRangeControlState(container, attribute, value) {
  if (!container) return;
  container.querySelectorAll(`button[${attribute}]`).forEach((button) => {
    button.setAttribute("aria-pressed", String(button.getAttribute(attribute) === value));
  });
}
