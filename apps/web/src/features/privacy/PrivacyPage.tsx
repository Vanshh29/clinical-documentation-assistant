import { Trash2 } from 'lucide-react';
import { useState } from 'react';
import { Dialog } from '@/components/Dialog';
import { PageHeader } from '@/components/feedback';
import { useToast } from '@/components/Toast';
import { useEraseMyData } from '@/lib/queries';

export function PrivacyPage() {
  const [open, setOpen] = useState(false);
  const [confirm, setConfirm] = useState('');
  const erase = useEraseMyData();
  const toast = useToast();

  const run = async () => {
    try {
      const res = await erase.mutateAsync();
      setOpen(false);
      setConfirm('');
      toast(`Deleted ${res.notes_deleted} note(s) and their summaries.`);
    } catch (e) {
      toast(e instanceof Error ? e.message : 'Deletion failed.', 'error');
    }
  };

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader title="Privacy" subtitle="How your notes are handled and how to remove them." />
      <section className="card mb-6 space-y-3 p-5">
        <h2 className="text-lg font-bold">How notes are handled</h2>
        <ul className="list-disc space-y-2 pl-5 text-muted">
          <li>
            Names, dates of birth, phone numbers, insurance and bank numbers are replaced with placeholders before a
            language model reads the note.
          </li>
          <li>
            The mapping back to real values is encrypted and stored separately. Real values appear only on screens you
            open while signed in.
          </li>
          <li>
            Only you can see your notes. Administrators see aggregate metrics and an audit log of identifiers, never
            note text.
          </li>
          <li>Every summary needs your approval before it is final, and every action is recorded in the audit log.</li>
        </ul>
      </section>
      <section className="card border-danger/40 p-5">
        <h2 className="text-lg font-bold">Delete my data</h2>
        <p className="mt-1 text-muted">
          Permanently deletes all of your notes, generated summaries and redaction mappings. A record that a deletion
          happened (without any note content) stays in the audit log.
        </p>
        <button type="button" className="btn btn-danger mt-4" onClick={() => setOpen(true)}>
          <Trash2 className="h-4 w-4" aria-hidden="true" /> Delete my data
        </button>
      </section>

      <Dialog open={open} onClose={() => setOpen(false)} title="Delete all your data?">
        <p className="text-sm text-muted">This cannot be undone. Type DELETE to confirm.</p>
        <label htmlFor="confirm-delete" className="label mt-3">
          Confirmation
        </label>
        <input
          id="confirm-delete"
          className="input"
          value={confirm}
          autoComplete="off"
          onChange={(e) => setConfirm(e.target.value)}
        />
        <div className="mt-5 flex justify-end gap-2">
          <button type="button" className="btn btn-ghost" onClick={() => setOpen(false)}>
            Cancel
          </button>
          <button
            type="button"
            className="btn btn-danger"
            disabled={confirm !== 'DELETE' || erase.isPending}
            onClick={() => void run()}
          >
            {erase.isPending ? 'Deleting…' : 'Delete everything'}
          </button>
        </div>
      </Dialog>
    </div>
  );
}
