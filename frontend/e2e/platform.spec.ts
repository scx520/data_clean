import { expect, test } from '@playwright/test'

test('完整流程：预览、执行、导出、报告、模板和历史记录', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.goto('/')
  await expect(page.getByText('服务已连接')).toBeVisible()
  await page.locator('#dataset').selectOption({ label: '客户信息示例（模拟数据）.csv' })
  await expect(page.locator('.metric-value').first()).toContainText('52')
  await expect(page.locator('.data-table tbody tr')).toHaveCount(50)
  await page.screenshot({ path: 'artifacts/workbench.png', fullPage: true, animations: 'disabled' })
  await page.getByRole('button', { name: '下一页' }).click()
  await expect(page.locator('.data-table tbody tr')).toHaveCount(2)
  await page.getByRole('button', { name: '上一页' }).click()
  await page.getByRole('button', { name: '预览效果', exact: true }).click()
  await expect(page.getByText('预览结果 · 尚未保存')).toBeVisible()
  await expect(page.locator('.metric-value').first()).toContainText('48')
  await page.getByRole('button', { name: /^变更记录/ }).click()
  await expect(page.locator('.data-table tbody tr').first()).toContainText('去除首尾空格')
  await page.getByRole('button', { name: '原始数据', exact: true }).click()
  await expect(page.locator('.metric-value').first()).toContainText('52')
  await page.getByRole('button', { name: '执行清洗', exact: true }).click()
  await expect(page.getByText('已保存的清洗结果')).toBeVisible()
  await page.getByRole('button', { name: '导出结果' }).click()
  const downloadPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: '清洗结果 · Excel' }).click()
  const download = await downloadPromise
  expect(download.suggestedFilename()).toContain('.xlsx')
  await page.getByRole('button', { name: '查看质量报告' }).click()
  await expect(page.getByRole('heading', { name: '清洗成效，一目了然' })).toBeVisible()
  await expect(page.locator('.report-stat').first()).toContainText('48')
  await page.locator('.toast-message .icon-button').click()
  await page.screenshot({ path: 'artifacts/report.png', fullPage: true, animations: 'disabled' })
  await page.getByRole('button', { name: '清洗工作台', exact: true }).click()
  await page.getByRole('button', { name: '存为模板' }).click()
  await page.getByLabel('模板名称', { exact: true }).fill('客户信息基础整理')
  await page.getByRole('button', { name: '保存模板', exact: true }).click()
  await page.getByRole('button', { name: '规则模板', exact: true }).click()
  await expect(page.getByRole('heading', { name: '客户信息基础整理' })).toBeVisible()
  await page.getByRole('button', { name: '应用到工作台' }).click()
  await expect(page.getByRole('heading', { name: '清洗工作台' })).toBeVisible()
  await expect(page.getByText('已保存的清洗结果')).not.toBeVisible()
  await page.getByRole('button', { name: '任务记录', exact: true }).click()
  await page.getByRole('button', { name: '查看结果' }).first().click()
  await expect(page.getByText('已保存的清洗结果')).toBeVisible()
  await page.getByRole('button', { name: '去除首尾空格', exact: false }).first().click()
  await page.getByRole('switch', { name: '停用去除首尾空格' }).click()
  await expect(page.getByText('已保存的清洗结果')).not.toBeVisible()
  await expect(page.getByRole('button', { name: /^清洗预览/ })).toBeDisabled()
  expect(errors).toEqual([])
})

test('上传、字段配置、格式异常、搜索和持久化', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.goto('/')
  await page.getByRole('button', { name: '导入数据', exact: true }).first().click()
  await page
    .locator('input[type=file]')
    .setInputFiles({
      name: '测试台账.csv',
      mimeType: 'text/csv',
      buffer: Buffer.from(
        '\ufeff编号,姓名,邮箱\n001, 测试甲 ,bad-email\n002,测试乙,test@example.com\n',
      ),
    })
  await page.getByRole('button', { name: '导入并预览' }).click()
  await expect(page.locator('#dataset')).toContainText('测试台账.csv')
  await expect(page.locator('.data-table tbody tr')).toHaveCount(2)
  await expect(page.locator('.data-table tbody tr').first()).toContainText('001')
  await page.getByRole('button', { name: '添加清洗规则' }).click()
  await page.getByRole('button', { name: /标记异常数据.*检查手机号/ }).click()
  await page.locator('.rule-card.expanded .field-chip').filter({ hasText: '编号' }).click()
  await page.locator('.rule-card.expanded .field-chip').filter({ hasText: '邮箱' }).click()
  await page.locator('.rule-card.expanded select').selectOption('email')
  await page.getByRole('button', { name: '预览效果', exact: true }).click()
  await page.getByRole('button', { name: /^异常/ }).click()
  await expect(page.locator('.data-table tbody tr')).toHaveCount(1)
  await expect(page.locator('.data-table tbody tr')).toContainText('邮箱格式异常')
  await page.getByRole('button', { name: '执行清洗', exact: true }).click()
  await expect(page.getByText('已保存的清洗结果')).toBeVisible()
  await page.getByLabel('搜索数据', { exact: true }).fill('测试乙')
  await expect(page.locator('.data-table tbody tr')).toHaveCount(1)
  await page.reload()
  await page.getByRole('button', { name: '任务记录', exact: true }).click()
  await expect(page.locator('.record-table')).toContainText('测试台账')
  await page.getByRole('button', { name: '查看结果' }).first().click()
  await expect(page.locator('.data-table tbody tr')).toHaveCount(2)
  expect(errors).toEqual([])
})

test('手机布局没有横向页面溢出，菜单和指南可操作', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  await expect(page.getByText('服务已连接')).toBeVisible()
  await expect(page.locator('.data-table tbody tr').first()).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  )
  await page.screenshot({ path: 'artifacts/mobile.png', fullPage: true })
  await page.getByRole('button', { name: '数据集管理', exact: true }).click()
  await expect(page.getByRole('heading', { name: '数据集管理' })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  )
})
