import { expect, test } from '@playwright/test'

test.setTimeout(120_000)

test('数值聚类生成标签、分组概况、历史报告和完整导出', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.goto('/')
  await page.getByRole('button', { name: '导入数据', exact: true }).first().click()
  await page
    .locator('input[type=file]')
    .setInputFiles({
      name: '聚类样例.csv',
      mimeType: 'text/csv',
      buffer: Buffer.from(
        '\ufeff编号,金额\n001,10\n002,11\n003,12\n004,1000\n005,1001\n006,1002\n007,未知\n',
      ),
    })
  await page.getByRole('button', { name: '导入并预览' }).click()
  await expect(page.locator('.data-table tbody tr')).toHaveCount(7)
  await page.getByRole('button', { name: '添加清洗规则' }).click()
  await page.getByRole('button', { name: /聚类分析.*按数值/ }).click()
  const config = page.locator('.rule-card.expanded')
  await config.getByRole('button', { name: '编号', exact: true }).click()
  await config.getByRole('button', { name: '金额', exact: true }).click()
  await config.getByLabel('聚类方式', { exact: true }).selectOption('numeric')
  await config.getByLabel('分组数量', { exact: true }).selectOption('2')
  await config.getByLabel('新增分组字段名', { exact: true }).fill('消费分组')
  await page.getByRole('button', { name: '预览效果', exact: true }).click()
  await expect(page.locator('.cluster-report')).toContainText('参与 6 行')
  await expect(page.locator('.cluster-report')).toContainText('未参与 1 行')
  await expect(page.locator('.cluster-group')).toHaveCount(2)
  await expect(page.locator('.data-table thead')).toContainText('消费分组')
  await expect(page.locator('.data-table tbody tr').last()).toContainText('未参与')
  await page.screenshot({
    path: 'artifacts/clustering.png',
    fullPage: true,
    animations: 'disabled',
  })
  await page.getByRole('button', { name: '原始数据', exact: true }).click()
  await expect(page.locator('.data-table thead')).not.toContainText('消费分组')
  await page.getByRole('button', { name: '执行清洗', exact: true }).click()
  await expect(page.getByText('已保存的清洗结果')).toBeVisible()
  await expect(page.locator('.data-table thead')).toContainText('消费分组')
  await page.getByRole('button', { name: '导出结果' }).click()
  const download = page.waitForEvent('download')
  await page.getByRole('button', { name: '清洗结果 · CSV' }).click()
  expect((await download).suggestedFilename()).toContain('.csv')
  await page.getByRole('button', { name: '查看质量报告' }).click()
  await expect(page.locator('.cluster-report')).toContainText('消费分组')
  await expect(page.locator('.cluster-group')).toHaveCount(2)
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.reload()
  await page.getByRole('button', { name: '任务记录', exact: true }).click()
  await page
    .locator('.record-table tbody tr')
    .filter({ hasText: '聚类样例' })
    .getByRole('button', { name: '查看结果' })
    .click()
  await expect(page.locator('.cluster-report')).toContainText('数值聚类')
  await expect(page.locator('.data-table thead')).toContainText('消费分组')
  expect(errors).toEqual([])
})

test('中文文本聚类展示文字特征和示例', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: '导入数据', exact: true }).first().click()
  await page
    .locator('input[type=file]')
    .setInputFiles({
      name: '文本分组样例.csv',
      mimeType: 'text/csv',
      buffer: Buffer.from(
        '\ufeff企业名称\n移动通信营业厅\n移动通信营业厅\n移动通信营业厅\n水果蔬菜超市\n水果蔬菜超市\n水果蔬菜超市\n',
      ),
    })
  await page.getByRole('button', { name: '导入并预览' }).click()
  await expect(page.locator('.data-table tbody tr')).toHaveCount(6)
  // Preserve repeated records so the clustering example includes every input row.
  await page.getByRole('switch', { name: '停用去除重复记录' }).click()
  await page.getByRole('button', { name: '添加清洗规则' }).click()
  await page.getByRole('button', { name: /聚类分析.*按数值/ }).click()
  await page
    .locator('.rule-card.expanded')
    .getByLabel('分组数量', { exact: true })
    .selectOption('2')
  await page.getByRole('button', { name: '预览效果', exact: true }).click()
  await expect(page.locator('.cluster-report')).toContainText('中文文本聚类')
  await expect(page.locator('.cluster-group')).toHaveCount(2)
  await expect(page.locator('.cluster-example')).toHaveCount(4)
  await expect(page.locator('.metric-value').first()).toContainText('6')
})
