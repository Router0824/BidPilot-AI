<template>
  <router-view />
  <ApiActivity />
</template>

<script setup>
import ApiActivity from './components/ApiActivity.vue'
</script>

<style>
:root {
  --ink: #182033;
  --ink-soft: #566173;
  --muted: #8a94a6;
  --paper: #ffffff;
  --paper-2: #f8faf7;
  --field: #f6f8f5;
  --line: #dfe7df;
  --line-strong: #b8c7bf;
  --navy: #0e2b4f;
  --navy-2: #143c6c;
  --cyan: #2d9cbd;
  --mint: #38a169;
  --amber: #c77918;
  --red: #c24136;
  --sidebar: #111827;
  --shadow-soft: 0 1px 2px rgba(24, 32, 51, .04), 0 14px 34px rgba(24, 32, 51, .08);
  --shadow-lift: 0 18px 45px rgba(14, 43, 79, .16);
  --radius: 8px;
  --font-body: "Avenir Next", "Gill Sans", "PingFang SC", "Microsoft YaHei", sans-serif;
  --font-title: "DIN Alternate", "Avenir Next Condensed", "PingFang SC", "Microsoft YaHei", sans-serif;
  --font-mono: "SFMono-Regular", "Menlo", "Consolas", monospace;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
html { background: #edf2f1; }
body {
  min-width: 320px;
  font-family: var(--font-body);
  background:
    linear-gradient(120deg, rgba(45,156,189,.08), transparent 26%),
    linear-gradient(300deg, rgba(199,121,24,.08), transparent 24%),
    repeating-linear-gradient(0deg, rgba(14,43,79,.035) 0, rgba(14,43,79,.035) 1px, transparent 1px, transparent 42px),
    repeating-linear-gradient(90deg, rgba(14,43,79,.025) 0, rgba(14,43,79,.025) 1px, transparent 1px, transparent 42px),
    #edf2f1;
  color: var(--ink);
  text-rendering: optimizeLegibility;
  -webkit-font-smoothing: antialiased;
}
#app { min-height: 100vh; }
h1, h2, h3, h4 {
  font-family: var(--font-title);
  letter-spacing: 0;
  color: var(--ink);
}
::selection { background: rgba(45, 156, 189, .22); }
input, select, textarea, button { font: inherit; letter-spacing: 0; }
input, select, textarea {
  background: var(--field) !important;
  color: var(--ink) !important;
  border: 1px solid var(--line) !important;
}
input:hover, select:hover, textarea:hover { border-color: var(--line-strong) !important; }
input:focus, select:focus, textarea:focus {
  outline: none;
  border-color: var(--cyan) !important;
  box-shadow: 0 0 0 3px rgba(45, 156, 189, .14) !important;
}
.btn-primary {
  background: linear-gradient(180deg, var(--navy-2), var(--navy)) !important;
  border: 1px solid rgba(255,255,255,.08) !important;
  box-shadow: inset 0 1px 0 rgba(255,255,255,.16), 0 10px 24px rgba(14,43,79,.18);
  font-weight: 700 !important;
}
.btn-secondary {
  background: #f7f8f4 !important;
  color: var(--navy) !important;
  border: 1px solid var(--line) !important;
  font-weight: 700 !important;
}
.btn-sm {
  border-radius: 5px !important;
  font-weight: 700 !important;
}
.section, .status-card, .thinking-list, .facts-table, .table-container, .knowledge-card,
.info-card, .project-card, .modal, .monitor-form, .monitors, .opportunity-table,
.sessions, .chat-panel {
  background: rgba(255,255,255,.92) !important;
  border: 1px solid rgba(184,199,191,.72) !important;
  box-shadow: var(--shadow-soft) !important;
  backdrop-filter: blur(12px);
}
.table th, .table-header, .table-head {
  background: #f1f5f0 !important;
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
  transition: transform 0.12s ease, box-shadow 0.18s ease, filter 0.18s ease, background-color 0.18s ease, border-color 0.18s ease, color .18s ease;
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
  outline: 3px solid rgba(45, 156, 189, 0.28);
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
