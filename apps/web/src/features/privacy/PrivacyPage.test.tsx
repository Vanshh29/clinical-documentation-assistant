import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mockApi, renderRoute } from '@/test/utils';
import { PrivacyPage } from './PrivacyPage';

afterEach(() => vi.unstubAllGlobals());

describe('PrivacyPage', () => {
  it('requires typing DELETE before erasing and reports the result', async () => {
    const { calls } = mockApi({ 'DELETE /me/data': { notes_deleted: 3 } });
    renderRoute(<PrivacyPage />);
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /Delete my data/ }));
    const dialog = await screen.findByRole('dialog', { name: 'Delete all your data?' });
    const confirm = within(dialog).getByRole('button', { name: 'Delete everything' });
    expect(confirm).toBeDisabled();
    await user.type(within(dialog).getByLabelText('Confirmation'), 'delete');
    expect(confirm).toBeDisabled(); // case-sensitive
    await user.clear(within(dialog).getByLabelText('Confirmation'));
    await user.type(within(dialog).getByLabelText('Confirmation'), 'DELETE');
    await user.click(confirm);
    await waitFor(() => expect(calls.some((c) => c.key === 'DELETE /me/data')).toBe(true));
    expect(await screen.findByText('Deleted 3 note(s) and their summaries.')).toBeInTheDocument();
  });
});
