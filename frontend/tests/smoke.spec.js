import { expect, test } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const docs = fileURLToPath(new URL('../../backend/tests/fixtures/documents/', import.meta.url))
const realDocs = fileURLToPath(new URL('../../demo_documents/', import.meta.url))

async function runXRay(page) {
  await page.getByTestId('run-xray').click()
  await expect(page).toHaveURL(/\/report\//, { timeout: 60_000 })
  await expect(page.getByTestId('scorecard')).toBeVisible()
}

test('home page offers upload and paste only', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByTestId('dropzone')).toBeVisible()
  await expect(page.getByText('Try a sample')).toHaveCount(0)
})

test('uploaded offer letter: detect, analyze, explore the report', async ({ page }) => {
  await page.goto('/')
  await page.getByTestId('file-input').setInputFiles(`${docs}india_offer_letter.txt`)

  await expect(page).toHaveURL(/\/analyze\//)
  await expect(page.getByTestId('doc-filename')).toHaveText('india_offer_letter.txt')
  await expect(page.getByTestId('doctype-select')).toHaveValue('offer_letter')
  await runXRay(page)

  await expect(page.getByTestId('report-title')).toHaveText('india_offer_letter.txt')
  await expect(page.getByTestId('report-summary')).toContainText('India')
  await expect(page.getByTestId('document-viewer').locator('mark.hl').first()).toBeVisible()
  await expect(page.getByTestId('heat-strip')).toBeVisible()
  expect(await page.getByTestId('finding-card').count()).toBeGreaterThan(5)
  await expect(page.getByTestId('findings-rail')).toContainText('Employer retains original certificates')

  await page.getByRole('tab', { name: /Market/ }).click()
  expect(await page.getByTestId('market-item').count()).toBeGreaterThan(0)

  await page.getByTestId('open-chat').click()
  await page.getByTestId('chat-input').fill('Is there a non-compete?')
  await page.getByTestId('chat-input').press('Enter')
  await expect(page.getByRole('dialog')).toContainText(/C\d+/)
  await page.getByRole('button', { name: 'Close' }).click()

  await expect(page.getByText('Redlines & email')).toHaveCount(0)
  await expect(page.getByText('Why this score?')).toHaveCount(0)
  await expect(page.getByRole('contentinfo')).toContainText('not legal advice')

  await page.getByRole('link', { name: 'History' }).first().click()
  await expect(page.getByText('india_offer_letter.txt')).toBeVisible()
})

test('uploaded contract read from the vendor side', async ({ page }) => {
  await page.goto('/')
  await page.getByTestId('file-input').setInputFiles(`${docs}saas_msa.txt`)

  await expect(page).toHaveURL(/\/analyze\//)
  await expect(page.getByTestId('doctype-select')).toHaveValue('msa_saas')
  await page.getByTestId('perspective-vendor').click()
  await runXRay(page)
  await expect(page.getByTestId('scorecard')).toContainText('Vendor')
})

test('pasted NDA is detected and compared', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Paste text' }).click()
  await page.getByTestId('paste-textarea').fill(readFileSync(`${docs}legal_nda_contract.txt`, 'utf8'))
  await page.getByRole('button', { name: 'Analyze text' }).click()

  await expect(page).toHaveURL(/\/analyze\//)
  await expect(page.getByTestId('doctype-select')).toHaveValue('nda')
  await runXRay(page)
  await expect(page.getByTestId('findings-rail')).toContainText('No carve-out for disclosures required by law')

  await page.goto('/history')
  await page.getByLabel(/Select legal_nda_contract|Select pasted-text/).check()
  await page.getByLabel(/Select india_offer_letter/).check()
  await page.getByRole('button', { name: /Compare selected/ }).click()
  await expect(page.getByTestId('compare-result')).toBeVisible()
})

test('two real offer-letter PDFs are analyzed and compared', async ({ page }) => {
  for (const [file, company] of [['bark_cfo_offer_letter_2026.pdf', 'Barkbox'], ['fortrea_interim_ceo_offer_letter_2025.pdf', 'Fortrea']]) {
    await page.goto('/')
    await page.getByTestId('file-input').setInputFiles(`${realDocs}offer_letters/${file}`)
    await expect(page).toHaveURL(/\/analyze\//)
    await expect(page.getByTestId('doctype-select')).toHaveValue('offer_letter')
    await expect(page.getByText(company).first()).toBeVisible()
    await runXRay(page)
    await expect(page.getByTestId('document-viewer').locator('mark.hl').first()).toBeVisible()
  }

  await page.goto('/history')
  await page.getByLabel(/Select bark_cfo_offer_letter/).check()
  await page.getByLabel(/Select fortrea_interim_ceo/).check()
  await page.getByRole('button', { name: /Compare selected/ }).click()
  await expect(page.getByTestId('compare-result')).toBeVisible()
})
