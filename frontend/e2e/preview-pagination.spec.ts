import { expect, test } from '@playwright/test'

test('大表预览保持完整总数，客户经理去重显示实际字段和全部变更', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.goto('/')
  await page.getByRole('button', { name: '导入数据', exact: true }).first().click()
  const records = Array.from(
    { length: 9556 },
    (_, i) => `${String(i).padStart(5, '0')},经理${String(i % 581).padStart(3, '0')}`,
  )
  await page
    .locator('input[type=file]')
    .setInputFiles({
      name: '大表去重回归.csv',
      mimeType: 'text/csv',
      buffer: Buffer.from(`\ufeff记录编号,客户经理\n${records.join('\n')}`),
    })
  await page.getByRole('button', { name: '导入并预览' }).click()
  await expect(page.locator('.metric-value').first()).toContainText('9,556')

  // Unique record IDs mean whole-row deduplication should make zero changes.
  await page.getByRole('button', { name: '预览效果', exact: true }).click()
  await expect(page.locator('.zero-change-hint')).toBeVisible()
  await expect(page.locator('.table-footer')).toContainText('9,556')
  await expect(page.locator('.page-total')).toContainText('192')
  for (let i = 0; i < 4; i++) {
    const response = page.waitForResponse(
      (r) => r.url().includes('/api/previews/') && r.request().method() === 'GET',
    )
    await page.getByRole('button', { name: '下一页' }).click()
    await response
  }
  await expect(page.locator('.data-table tbody tr').first()).toContainText('00200')
  await page.getByLabel('搜索数据', { exact: true }).fill('09555')
  await expect(page.locator('.data-table tbody tr')).toHaveCount(1)
  await expect(page.locator('.data-table tbody tr')).toContainText('09555')

  // Selecting just the manager field must remove repeated managers across the full dataset.
  await page.getByRole('button', { name: /去除重复记录.*已启用/ }).click()
  await page
    .locator('.rule-card.expanded')
    .getByRole('button', { name: '客户经理', exact: true })
    .click()
  await expect(page.locator('.rule-card.expanded .field-chip.chosen')).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  await page.getByRole('button', { name: '预览效果', exact: true }).click()
  await expect(page.locator('.metric-value').first()).toContainText('581')
  await expect(page.locator('.table-footer')).toContainText('581')
  await expect(page.locator('.result-summary-counts')).toContainText('移除 8,975 行')
  await page.locator('.execution-details summary').click()
  await expect(page.locator('.execution-rule').filter({ hasText: '去除重复记录' })).toContainText(
    '处理字段：客户经理',
  )
  await page.getByRole('button', { name: /^变更记录/ }).click()
  await expect(page.locator('.table-footer')).toContainText('8,975')
  await page.getByLabel('搜索数据', { exact: true }).fill('9556')
  await expect(page.locator('.data-table tbody tr')).toHaveCount(1)
  await expect(page.locator('.data-table tbody tr')).toContainText('9556')
  await page.getByRole('button', { name: '原始数据', exact: true }).click()
  await expect(page.locator('.metric-value').first()).toContainText('9,556')
  expect(errors).toEqual([])
})
