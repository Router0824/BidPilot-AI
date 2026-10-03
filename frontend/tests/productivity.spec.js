import { test, expect } from '@playwright/test'

test('workbench, protected editing, review persistence and Word download', async ({ page, request }, testInfo) => {
  const login = await request.post('/api/v1/auth/login', { data: { username: 'admin', password: 'admin123' } })
  expect(login.ok()).toBeTruthy()
  const auth = (await login.json()).data
  const headers = { Authorization: `Bearer ${auth.access_token}` }
  const created = await request.post('/api/v1/projects', { headers, data: { name: `交付验收-${testInfo.project.name}-${Date.now()}` } })
  const projectId = (await created.json()).data.id
  const section = await request.post(`/api/v1/projects/${projectId}/outline/sections`, { headers, data: { title: '技术方案', level: 1 } })
  const sectionId = (await section.json()).data.id
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  try {
    await page.addInitScript(({ token, user }) => {
      localStorage.setItem('token', token); localStorage.setItem('user', JSON.stringify(user))
    }, { token: auth.access_token, user: auth.user })
    await page.goto(`/project/${projectId}`)
    await expect(page.getByRole('heading', { name: '交付待办' })).toBeVisible()
    await expect(page.locator('.demo-entry')).not.toHaveAttribute('open', '')
    await page.getByRole('button', { name: '章节', exact: true }).click()
    await expect(page.locator('.tasks')).toContainText('完成章节：技术方案')
    await expect(page.locator('.tasks')).not.toContainText('上传招标文件')
    await page.screenshot({ path: testInfo.outputPath('workbench.png'), fullPage: true })
    await page.getByRole('link', { name: '完成章节：技术方案' }).click()
    const editor = page.getByRole('textbox', { name: '章节正文' })
    await expect(editor).toBeEnabled()
    const text = '项目技术方案\n\n人工编写内容，不允许生成覆盖。\n\n| 阶段 | 交付物 |\n| --- | --- |\n| 设计 | 设计文档 |'
    await editor.fill(text)
    await page.getByRole('button', { name: '保存草稿', exact: true }).click()
    await expect(page.getByRole('checkbox', { name: '保护人工内容' })).toBeChecked()
    await expect(page.getByRole('button', { name: '生成章节初稿' })).toBeDisabled()
    await page.reload()
    await expect(editor).toHaveValue(text)
    await expect(page.getByRole('checkbox', { name: '保护人工内容' })).toBeChecked()
    await page.screenshot({ path: testInfo.outputPath('editor.png'), fullPage: true })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBeTruthy()
    await editor.fill(text + '\n未保存的修改')
    page.once('dialog', dialog => dialog.dismiss())
    await page.getByRole('link', { name: '交付检查与 Word 导出' }).click()
    await expect(page).toHaveURL(new RegExp(`/outline\\?section=${sectionId}`))
    await editor.fill(text)
    await page.goto(`/project/${projectId}/reviews`)
    await page.getByRole('button', { name: '开始审查' }).click()
    await expect(page.locator('.finding-item')).toHaveCount(1)
    await page.reload()
    await expect(page.locator('.finding-item')).toHaveCount(1)
    await expect(page.getByRole('link', { name: '打开对应章节' })).toBeVisible()
    await page.goto(`/project/${projectId}`)
    await page.locator('summary').filter({ hasText: '交付与 Word 导出' }).click()
    await expect(page.getByRole('button', { name: '下载正式稿' })).toBeDisabled()
    const downloadPromise = page.waitForEvent('download')
    await page.getByRole('button', { name: '下载工作草稿' }).click()
    const download = await downloadPromise
    expect(download.suggestedFilename()).toBe('工作草稿.docx')
    expect(await download.failure()).toBeNull()
    await download.saveAs(testInfo.outputPath('working-draft.docx'))
    const sampleDownload = page.waitForEvent('download')
    await page.getByRole('button', { name: '下载模板范本' }).click()
    expect(await (await sampleDownload).failure()).toBeNull()
    const sample = await request.get(`/api/v1/projects/${projectId}/delivery/template/sample`, { headers })
    await page.getByLabel('企业 Word 模板').setInputFiles({ name: '企业模板.docx', mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', buffer: await sample.body() })
    await expect(page.getByText('正文插入指定位置', { exact: false })).toBeVisible()
    await page.getByLabel('投标单位', { exact: true }).fill('示范技术有限公司')
    const customizedDownload = page.waitForEvent('download')
    await page.getByRole('button', { name: '下载工作草稿' }).click()
    const customized = await customizedDownload
    expect(await customized.failure()).toBeNull()
    await customized.saveAs(testInfo.outputPath('customized-draft.docx'))
    await page.screenshot({ path: testInfo.outputPath('template-delivery.png'), fullPage: true })
    page.once('dialog', dialog => dialog.accept())
    await page.getByRole('button', { name: '恢复默认模板' }).click()
    await expect(page.getByText('使用默认模板', { exact: true })).toBeVisible()
    expect(errors).toEqual([])
  } finally {
    await request.delete(`/api/v1/projects/${projectId}`, { headers })
  }
})
