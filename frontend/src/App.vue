<template>
  <router-view />
  <ApiActivity />
</template>

<script setup>
import ApiActivity from './components/ApiActivity.vue'
</script>

<style>
:root {
  --ink: #111827;
  --ink-soft: #4b5563;
  --muted: #8b95a5;
  --paper: rgba(255,255,255,.86);
  --paper-solid: #ffffff;
  --paper-2: #f7f8fa;
  --field: rgba(255,255,255,.72);
  --line: rgba(17,24,39,.10);
  --line-strong: rgba(17,24,39,.18);
  --navy: #111827;
  --navy-2: #1f2937;
  --cyan: #2563eb;
  --mint: #16a34a;
  --amber: #b45309;
  --red: #dc2626;
  --sidebar: rgba(255,255,255,.74);
  --shadow-soft: 0 1px 2px rgba(17, 24, 39, .04), 0 18px 42px rgba(17, 24, 39, .08);
  --shadow-lift: 0 24px 60px rgba(17, 24, 39, .13);
  --shadow-pop: 0 10px 28px rgba(17, 24, 39, .10);
  --radius: 8px;
  --font-body: -apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", "Microsoft YaHei", sans-serif;
  --font-title: -apple-system, BlinkMacSystemFont, "SF Pro Display", "PingFang SC", "Microsoft YaHei", sans-serif;
  --font-mono: "SFMono-Regular", "Menlo", "Consolas", monospace;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
html { background: #f5f5f7; }
body {
  min-width: 320px;
  font-family: var(--font-body);
  background:
    radial-gradient(circle at 16% -10%, rgba(37,99,235,.12), transparent 30%),
    radial-gradient(circle at 92% 2%, rgba(17,24,39,.08), transparent 26%),
    linear-gradient(180deg, #fbfbfd 0%, #f5f5f7 44%, #f1f2f4 100%);
  color: var(--ink);
  text-rendering: optimizeLegibility;
  -webkit-font-smoothing: antialiased;
}
#app { min-height: 100vh; }
h1, h2, h3, h4 {
  font-family: var(--font-title);
  letter-spacing: 0;
  color: var(--ink);
  font-weight: 750;
}
::selection { background: rgba(45, 156, 189, .22); }
input, select, textarea, button { font: inherit; letter-spacing: 0; }
input, select, textarea {
  background: var(--field) !important;
  color: var(--ink) !important;
  border: 1px solid var(--line) !important;
  border-radius: 8px !important;
  backdrop-filter: blur(14px);
}
input:hover, select:hover, textarea:hover { border-color: var(--line-strong) !important; }
input:focus, select:focus, textarea:focus {
  outline: none;
  border-color: var(--cyan) !important;
  box-shadow: 0 0 0 4px rgba(37, 99, 235, .13) !important;
}
.btn-primary {
  background: linear-gradient(180deg, #242934, #111827) !important;
  color: #fff !important;
  border: 1px solid rgba(255,255,255,.12) !important;
  border-radius: 999px !important;
  box-shadow: inset 0 1px 0 rgba(255,255,255,.18), 0 12px 28px rgba(17,24,39,.18);
  font-weight: 700 !important;
}
.btn-secondary {
  background: rgba(255,255,255,.76) !important;
  color: var(--navy) !important;
  border: 1px solid var(--line) !important;
  border-radius: 999px !important;
  font-weight: 700 !important;
  backdrop-filter: blur(14px);
}
.btn-sm {
  border-radius: 999px !important;
  font-weight: 700 !important;
}
.section, .status-card, .thinking-list, .facts-table, .table-container, .knowledge-card,
.info-card, .project-card, .modal, .monitor-form, .monitors, .opportunity-table,
.sessions, .chat-panel {
  background: var(--paper) !important;
  border: 1px solid rgba(255,255,255,.78) !important;
  box-shadow: var(--shadow-soft) !important;
  backdrop-filter: blur(22px) saturate(1.18);
}
.table th, .table-header, .table-head {
  background: rgba(247,248,250,.88) !important;
  color: var(--ink-soft) !important;
  font-weight: 800 !important;
}
.status, .status-badge, .type-tag, .risk-tag, .status-tag, .audit-tag, .badge {
  border-radius: 999px !important;
  font-weight: 800 !important;
}
.empty, .empty-hint, .empty-state, .loading, .no-wf {
  color: var(--muted) !important;
}
button,
.action-card,
.project-card,
.node-item,
.nav-item,
.logo {
  transition: transform 0.16s cubic-bezier(.2,.8,.2,1), box-shadow 0.22s ease, filter 0.18s ease, background-color 0.18s ease, border-color 0.18s ease, color .18s ease;
}
button:not(:disabled):active,
.action-card:active,
.project-card:active,
.node-item:active,
.nav-item:active,
.logo:active {
  transform: translateY(1px) scale(0.99);
  filter: brightness(0.96);
}
button:focus-visible,
a:focus-visible,
input:focus-visible,
select:focus-visible,
textarea:focus-visible,
.node-item:focus-visible,
.project-card:focus-visible {
  outline: 3px solid rgba(37, 99, 235, 0.24);
  outline-offset: 2px;
}
button:disabled {
  cursor: wait;
}
button:not(:disabled):hover,
.action-card:hover,
.project-card:hover,
.node-item:hover {
  box-shadow: var(--shadow-lift);
}
</style>
