import { expect, test } from '@playwright/test'

test('删除确认、回收站恢复和已删除数据集的历史结果', async ({ page, request }) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  const upload = await request.post('/api/datasets', {
    multipart: {
      file: {
        name: '删除回归样例.csv',
        mimeType: 'text/csv',
        buffer: Buffer.from('\ufeff编号,姓名\n001, 测试甲 \n002,测试乙\n'),
      },
    },
  })
  const datasetId = (await upload.json()).id
  const submit = await request.post(`/api/datasets/${datasetId}/tasks`, {
    data: { name: '删除后保留的历史任务', rules: [{ id: 'trim', type: 'trim' }] },
  })
  const taskId = (await submit.json()).id
  await expect
    .poll(async () => (await (await request.get(`/api/tasks/${taskId}`)).json()).status)
    .toBe('success')
  await page.goto('/')
  await page.getByRole('button', { name: '数据集管理', exact: true }).click()
  const card = page
    .locator('.dataset-card')
    .filter({ has: page.getByRole('heading', { name: '删除回归样例.csv', exact: true }) })
  await card.getByRole('button', { name: '删除数据集 删除回归样例.csv', exact: true }).click()
  await expect(page.getByRole('dialog')).toContainText('关联 1 条任务')
  await page.getByRole('button', { name: '取消', exact: true }).click()
  await expect(card).toBeVisible()
  await card.getByRole('button', { name: '删除数据集 删除回归样例.csv', exact: true }).click()
  await page.getByRole('button', { name: '确认删除', exact: true }).click()
  await expect(card).toHaveCount(0)
  await page.getByRole('button', { name: '清洗工作台', exact: true }).click()
  await expect(page.locator('#dataset')).not.toHaveValue(datasetId)
  await page.getByRole('button', { name: '任务记录', exact: true }).click()
  await page
    .locator('.record-table tbody tr')
    .filter({ hasText: '删除后保留的历史任务' })
    .getByRole('button', { name: '查看结果' })
    .click()
  await expect(page.locator('.dataset-archived-notice')).toContainText('已移入回收站')
  await expect(page.getByText('已保存的清洗结果')).toBeVisible()
  await expect(page.getByRole('button', { name: '执行清洗', exact: true })).toBeDisabled()
  await expect(page.locator('.data-table tbody tr')).toHaveCount(2)
  await page.getByRole('button', { name: '导出结果' }).click()
  const download = page.waitForEvent('download')
  await page.getByRole('button', { name: '清洗结果 · CSV' }).click()
  expect((await download).suggestedFilename()).toContain('.csv')
  await page.getByRole('button', { name: '数据集管理', exact: true }).click()
  await page.getByRole('tab', { name: /回收站/ }).click()
  await expect(card).toBeVisible()
  await card.getByRole('button', { name: '恢复', exact: true }).click()
  await expect(card).toHaveCount(0)
  await page.getByRole('tab', { name: /全部数据集/ }).click()
  await expect(card).toBeVisible()
  await card.getByRole('button', { name: '开始清洗' }).click()
  await expect(page.locator('.dataset-archived-notice')).toHaveCount(0)
  await expect(page.getByRole('button', { name: '预览效果', exact: true })).toBeEnabled()
  expect(errors).toEqual([])
})

test('删除最后一个数据集后显示空工作台，并可恢复', async ({ page, request }) => {
  // All test data belongs to Playwright's isolated temporary workspace.
  const datasets = await (await request.get('/api/datasets')).json()
  for (const dataset of datasets.slice(1))
    expect((await request.delete(`/api/datasets/${dataset.id}`)).status()).toBe(204)
  const last = datasets[0]
  await page.goto('/')
  await page.getByRole('button', { name: '数据集管理', exact: true }).click()
  await page.getByRole('button', { name: `删除数据集 ${last.name}`, exact: true }).click()
  await page.getByRole('button', { name: '确认删除', exact: true }).click()
  await expect(page.locator('.dataset-card')).toHaveCount(0)
  await page.getByRole('button', { name: '清洗工作台', exact: true }).click()
  await expect(page.getByText('从导入第一份数据开始')).toBeVisible()
  await expect(page.locator('.metric-value').first()).toContainText('0')
  await expect(page.getByRole('button', { name: '执行清洗', exact: true })).toBeDisabled()
  await page.getByRole('button', { name: '数据集管理', exact: true }).click()
  await page.getByRole('tab', { name: /回收站/ }).click()
  await page
    .locator('.dataset-card')
    .filter({ has: page.getByRole('heading', { name: last.name, exact: true }) })
    .getByRole('button', { name: '恢复', exact: true })
    .click()
  await page.getByRole('button', { name: '清洗工作台', exact: true }).click()
  await expect(page.locator('.data-table tbody tr').first()).toBeVisible()
})
