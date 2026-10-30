import { expect, test } from '@playwright/test'

test('字段搜索和批量选择保留隐藏选项，聚类限制20字段', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: '导入数据', exact: true }).first().click()
  const fields = [
    '客户编号',
    '客户姓名',
    '客户经理',
    '金额',
    ...Array.from({ length: 21 }, (_, i) => `扩展字段${i + 1}`),
  ]
  const values = fields.map((_, i) => String(i))
  await page
    .locator('input[type=file]')
    .setInputFiles({
      name: '多字段选择.csv',
      mimeType: 'text/csv',
      buffer: Buffer.from(`\ufeff${fields.join(',')}\n${values.join(',')}\n`),
    })
  await page.getByRole('button', { name: '导入并预览' }).click()
  await expect(page.locator('.data-table tbody tr')).toHaveCount(1)
  const selector = page.locator('.rule-card.expanded .field-selector')
  await expect(selector.locator('.field-selection-summary')).toContainText('当前使用全部 25 个字段')
  await selector.getByRole('button', { name: '全选', exact: true }).click()
  await expect(selector.locator('.field-chip.chosen')).toHaveCount(25)
  await selector.getByLabel('搜索字段', { exact: true }).fill('客户')
  await expect(selector.locator('.field-chip')).toHaveCount(3)
  await selector.getByRole('button', { name: '清空匹配项', exact: true }).click()
  await expect(selector.locator('.field-selection-summary')).toContainText('已选 22 个字段')
  await selector.getByRole('button', { name: '反选匹配项', exact: true }).click()
  await expect(selector.locator('.field-selection-summary')).toContainText('已选 25 个字段')
  await selector.getByRole('button', { name: '清空匹配项', exact: true }).click()
  await selector.getByRole('button', { name: '全选匹配项', exact: true }).click()
  await expect(selector.locator('.field-selection-summary')).toContainText('已选 25 个字段')
  await selector.getByLabel('搜索字段', { exact: true }).fill('不存在')
  await expect(selector.getByText('没有匹配字段，试试其他关键词。')).toBeVisible()
  await selector.getByRole('button', { name: '清除字段搜索' }).click()
  await selector.getByRole('button', { name: '反选', exact: true }).click()
  await expect(selector.locator('.field-chip.chosen')).toHaveCount(0)
  await expect(selector.locator('.field-selection-summary')).toContainText('当前使用全部 25 个字段')
  await selector.getByRole('button', { name: '客户经理', exact: true }).click()
  await page.getByRole('button', { name: '预览效果', exact: true }).click()
  await expect(page.getByText('预览结果 · 尚未保存')).toBeVisible()
  await page.locator('.execution-details summary').click()
  await expect(page.locator('.execution-rule').filter({ hasText: '去除首尾空格' })).toContainText(
    '处理字段：客户经理',
  )
  await selector.getByRole('button', { name: '全选', exact: true }).click()
  await expect(page.getByRole('button', { name: /^清洗预览/ })).toBeDisabled()
  await selector.getByRole('button', { name: '清空选择', exact: true }).click()
  await page.getByRole('button', { name: '添加清洗规则' }).click()
  await page.getByRole('button', { name: /聚类分析.*按数值/ }).click()
  const cluster = page.locator('.rule-card.expanded .field-selector')
  await cluster.getByRole('button', { name: '全选', exact: true }).click()
  await expect(cluster.getByRole('alert')).toContainText('最多选择 20 个字段')
  await expect(cluster.locator('.field-chip.chosen')).toHaveCount(1)
  await cluster.getByRole('button', { name: '清空选择', exact: true }).click()
  await expect(cluster.locator('.field-selection-summary')).toContainText('请至少选择一个')
  await cluster.getByLabel('搜索字段', { exact: true }).fill('客户')
  await cluster.getByRole('button', { name: '全选匹配项', exact: true }).click()
  await expect(cluster.locator('.field-chip.chosen')).toHaveCount(3)
  await expect(cluster.getByRole('alert')).toHaveCount(0)
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await cluster.scrollIntoViewIfNeeded()
  await page.screenshot({
    path: 'artifacts/field-selection-mobile.png',
    fullPage: true,
    animations: 'disabled',
  })
})
