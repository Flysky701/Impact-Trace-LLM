import { test, expect } from '@playwright/test'
import { readFileSync, mkdirSync } from 'node:fs'
import { resolve } from 'node:path'

// Explicit local opt-in: run against a started demo server with generated accounts.
test('developer and reviewer browse a real TinyDB snapshot', async ({ page }) => {
  const root = resolve('..')
  const credentials = Object.fromEntries(readFileSync(resolve(root, 'data/local/demo-credentials.txt'), 'utf8')
    .trim().split(/\r?\n/).map(line => line.split(': ')))
  const screenshots = resolve(root, 'reports/generated')
  mkdirSync(screenshots, { recursive: true })
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  await page.goto('/')
  await expect(page.getByRole('heading', { name: '进入工作空间' })).toBeVisible()
  await page.screenshot({ path: resolve(screenshots, 'login.png'), fullPage: true })
  await page.getByLabel('用户名').fill('developer')
  await page.getByLabel('密码', { exact: true }).fill(credentials.developer)
  await page.getByRole('button', { name: '登录工作空间' }).click()
  await expect(page.getByRole('heading', { name: '项目工作台', exact: false })).toBeVisible()
  // Reuse an existing demo project so rerunning this check does not create duplicates.
  const project = page.getByRole('button', { name: /TinyDB 演示/ })
  if (await project.count() === 0) {
    await page.getByRole('button', { name: '＋ 接入项目' }).click()
    await page.getByLabel('项目名称').fill('TinyDB 演示')
    await page.getByLabel('审核者').selectOption({ label: 'reviewer' })
    await page.getByLabel('仓库根目录').fill(resolve(root, 'data/local/tinydb'))
    await page.getByLabel('项目说明').fill('具有完整 Git 历史的 Python 开源样例')
    await page.getByRole('button', { name: '保存并读取仓库' }).click()
  } else { await project.click() }
  await expect(page.getByText('744 次提交')).toBeVisible()
  await page.screenshot({ path: resolve(screenshots, 'workspace.png'), fullPage: true })
  await page.getByRole('button', { name: /reject CachingMiddleware/ }).click()
  await page.getByRole('button', { name: 'tinydb/middlewares.py', exact: true }).click()
  await expect(page.locator('pre')).toContainText('class CachingMiddleware')
  await expect(page.locator('.source-title')).toContainText('18d73a15066a')
  await page.screenshot({ path: resolve(screenshots, 'source.png'), fullPage: true })
  await page.getByRole('button', { name: '退出', exact: true }).click()
  await page.getByLabel('用户名').fill('reviewer')
  await page.getByLabel('密码', { exact: true }).fill(credentials.reviewer)
  await page.getByRole('button', { name: '登录工作空间' }).click()
  await expect(page.getByRole('button', { name: /TinyDB 演示/ })).toBeVisible()
  await expect(page.getByRole('button', { name: '＋ 接入项目' })).toHaveCount(0)
  await page.getByRole('button', { name: /TinyDB 演示/ }).click()
  await expect(page.getByText('744 次提交')).toBeVisible()
  await page.setViewportSize({ width: 390, height: 844 })
  await page.screenshot({ path: resolve(screenshots, 'mobile.png'), fullPage: true })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  expect(errors).toEqual([])
})
