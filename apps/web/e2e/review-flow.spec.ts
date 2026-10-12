import { expect, test, type Page } from '@playwright/test';

const PASSWORD = 'demo-password-123';

async function signIn(page: Page, email: string) {
  await page.goto('/login');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password').fill(PASSWORD);
  await page.getByRole('button', { name: 'Sign in' }).click();
}

test('clinician submits a note, reviews the summary, edits and approves it', async ({ page }) => {
  await signIn(page, 'clinician1@demo.example');
  await expect(page.getByRole('heading', { name: 'Notes' })).toBeVisible();

  await page.getByRole('link', { name: 'New note' }).first().click();
  await page.getByRole('button', { name: /English example/ }).click();
  await page.getByRole('button', { name: /Submit for summary/ }).click();

  // The worker picks the note up through Kafka; the page polls until it is ready.
  await expect(page.getByText('Needs review')).toBeVisible({ timeout: 30_000 });
  const note = page.getByRole('region', { name: 'Note text' });
  await expect(note).toContainText('Jordan Example'); // real value is restored for display

  // Source highlighting follows the selected field.
  await page.getByRole('button', { name: 'Show source for Plan' }).click();
  await expect(note.locator('mark').first()).toContainText('Plan: rest, fluids');

  // Edit, then approve (which saves first).
  const plan = page.getByRole('region', { name: 'Plan' }).getByRole('textbox');
  await plan.fill('Plan: rest, fluids and paracetamol 500 mg as needed. Review if no improvement.');
  await page.getByRole('button', { name: 'Approve', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Approve this summary?' });
  await expect(dialog).toContainText('1 field(s) changed');
  await dialog.getByRole('button', { name: 'Approve summary' }).click();

  await expect(page.getByText('Approved — this summary is final')).toBeVisible();
  await expect(page.getByText(/1 field\(s\) edited/)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Approve', exact: true })).toHaveCount(0);

  await page.getByRole('link', { name: 'All notes' }).click();
  await expect(page.getByRole('link', { name: /Cough and sore throat/ }).first()).toContainText('Approved');
});

test('administrator sees metrics and the audit trail but no note content', async ({ page }) => {
  await signIn(page, 'admin@demo.example');
  await expect(page.getByRole('heading', { name: 'Metrics & audit' })).toBeVisible();
  await expect(page.getByText('Approval rate')).toBeVisible();
  await page.getByRole('tab', { name: 'Audit log' }).click();
  await expect(page.getByRole('table')).toContainText('summary.approved');
  await expect(page.locator('body')).not.toContainText('Jordan Example');
  await page.goto('/notes/new');
  await expect(page).toHaveURL(/\/admin$/); // admins cannot open clinician pages
});

test('a signed-out visitor is sent to sign in', async ({ page }) => {
  await page.goto('/');
  await expect(page).toHaveURL(/\/login$/);
});
