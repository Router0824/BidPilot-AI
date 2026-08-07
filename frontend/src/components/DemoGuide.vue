<template>
  <aside class="demo-guide">
    <div class="guide-copy">
      <span>90 秒 Demo</span>
      <strong>{{ title }}</strong>
      <p>{{ body }}</p>
    </div>
    <div class="guide-actions">
      <router-link
        v-if="nextTo"
        :to="nextTo"
        class="guide-btn primary"
      >
        {{ nextLabel || '下一步' }}
      </router-link>
      <router-link
        v-if="exitTo"
        :to="exitTo"
        class="guide-btn"
      >
        退出引导
      </router-link>
    </div>
  </aside>
</template>

<script setup>
defineProps({
  title: { type: String, required: true },
  body: { type: String, required: true },
  nextTo: { type: [String, Object], default: '' },
  nextLabel: { type: String, default: '' },
  exitTo: { type: [String, Object], default: '' },
})
</script>

<style scoped>
.demo-guide {
  position: sticky;
  top: 14px;
  z-index: 8;
  display: flex;
  justify-content: space-between;
  gap: 18px;
  align-items: center;
  margin-bottom: 16px;
  padding: 14px 16px;
  border: 1px solid rgba(17,24,39,.12);
  border-radius: 22px;
  background: rgba(255,255,255,.9);
  box-shadow: 0 18px 42px rgba(15,23,42,.12);
  backdrop-filter: blur(22px);
}
.guide-copy span {
  display: block;
  margin-bottom: 4px;
  color: #64748b;
  font-size: 11px;
  font-weight: 900;
  text-transform: uppercase;
}
.guide-copy strong {
  display: block;
  color: #111827;
  font-size: 16px;
}
.guide-copy p {
  margin: 4px 0 0;
  color: #64748b;
  font-size: 13px;
  line-height: 1.5;
}
.guide-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}
.guide-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 36px;
  padding: 0 14px;
  border: 1px solid #dbe3ee;
  border-radius: 999px;
  background: white;
  color: #111827;
  font-size: 13px;
  font-weight: 800;
  text-decoration: none;
  white-space: nowrap;
}
.guide-btn.primary {
  border-color: #111827;
  background: #111827;
  color: white;
}
@media (max-width: 760px) {
  .demo-guide {
    position: static;
    flex-direction: column;
    align-items: flex-start;
  }
  .guide-actions {
    justify-content: flex-start;
  }
}
</style>
