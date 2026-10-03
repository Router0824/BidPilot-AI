import { test, expect } from '@playwright/test'

test('connection test uses the current form without saving credentials', async ({ page, request }) => {
  const login = await request.post('/api/v1/auth/login', { data: { username: 'admin', password: 'admin123' } })
  const { access_token } = (await login.json()).data
  await page.addInitScript(token => localStorage.setItem('token', token), access_token)
  let tested, saved = false
  await page.route('**/api/v1/system/llm-config', route => {
    if (route.request().method() === 'PUT') saved = true
    return route.fulfill({ json: { data: { provider: 'mock', api_key_configured: false } } })
  })
  await page.route('**/api/v1/system/llm-config/test', route => {
    tested = route.request().postDataJSON()
    return route.fulfill({ json: { data: { ok: true, mode: 'real', message: '当前配置验证通过' } } })
  })
  await page.goto('/settings')
  await page.locator('.provider-card').filter({ hasText: 'DeepSeek' }).click()
  await expect(page.getByLabel('默认模型', { exact: true })).toHaveValue('deepseek-flash')
  await expect(page.getByLabel('快速模型', { exact: true })).toHaveValue('deepseek-flash')
  await expect(page.getByLabel('高质量模型', { exact: true })).toHaveValue('deepseek-v4-pro')
  await page.locator('.provider-card').filter({ hasText: 'Custom' }).click()
  await page.getByLabel('API Key', { exact: true }).fill('fake-test-key')
  await page.getByLabel('Base URL', { exact: true }).fill('https://example.test/v1')
  await page.getByLabel('默认模型', { exact: true }).fill('test-model')
  await page.getByRole('button', { name: '测试连接', exact: true }).click()
  await expect(page.locator('.message')).toHaveText('当前配置验证通过')
  expect(tested.api_key).toBe('fake-test-key')
  expect(tested.model).toBe('test-model')
  expect(saved).toBe(false)
  await expect(page.locator('.mode-pill')).toContainText('当前运行：Mock')
})
