export function scrollDemoFocus(selector = '.demo-focus') {
  window.setTimeout(() => {
    const target = document.querySelector(selector)
    if (!target) return
    target.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, 260)
}
