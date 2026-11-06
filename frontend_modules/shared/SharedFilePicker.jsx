import React, { useMemo, useState } from 'react';

import './SharedFilePicker.css';

const extension = (name) => `.${String(name || '').split('.').pop().toLowerCase()}`;
const fileSize = (bytes) => bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;

export function SharedFilePicker({ title = 'Files already uploaded', description = 'Choose files kept in this browser session.', accept = '.csv,.xlsx,.xls', files = [], maxFiles = 4, disabled = false, onUse, onRemove }) {
  const [selected, setSelected] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const allowed = useMemo(() => accept.split(',').map((item) => item.trim().toLowerCase()), [accept]);
  const available = files.filter(({ file }) => allowed.includes(extension(file.name)));

  function toggle(fileId) {
    setError('');
    if (selected.includes(fileId)) setSelected((current) => current.filter((id) => id !== fileId));
    else if (selected.length >= maxFiles) setError(`Choose up to ${maxFiles} files at a time.`);
    else setSelected((current) => [...current, fileId]);
  }

  async function useSelected() {
    const picked = available.filter(({ id }) => selected.includes(id));
    if (!picked.length || busy || disabled) return;
    setBusy(true);
    setError('');
    try { await onUse(picked); setSelected([]); }
    catch (caught) { setError(caught.message || 'Could not use the selected files.'); }
    finally { setBusy(false); }
  }

  return (
    <section className="shared-file-picker" aria-label={title}>
      <div className="shared-file-picker-heading">
        <div><div className="shared-file-picker-kicker">THIS SESSION</div><h3>{title}</h3><p>{description}</p></div>
      </div>
      {error && <p className="shared-file-error" role="alert">{error}</p>}
      {available.length ? (
        <div className="shared-file-list">
          {available.map(({ id, file }) => (
            <label className="shared-file-row" key={id}>
              <input type="checkbox" checked={selected.includes(id)} onChange={() => toggle(id)} disabled={disabled || busy} />
              <span className="shared-file-row-name"><strong>{file.name}</strong><small>{fileSize(file.size)}</small></span>
              {onRemove && <button className="shared-file-remove" type="button" title={`Remove ${file.name} from this session`} aria-label={`Remove ${file.name} from this session`} disabled={disabled || busy} onClick={(event) => { event.preventDefault(); event.stopPropagation(); onRemove(id); setSelected((current) => current.filter((item) => item !== id)); }}>Remove</button>}
            </label>
          ))}
        </div>
      ) : <p className="shared-file-empty">No compatible files in this session yet. Upload a file here or on the other page.</p>}
      <div className="shared-file-picker-actions"><span>{selected.length ? `${selected.length} of ${maxFiles} selected` : 'Select one or more files'}</span><button className="shared-file-use" type="button" onClick={useSelected} disabled={disabled || busy || !selected.length}>{busy ? 'Loading files…' : 'Use selected files'}</button></div>
    </section>
  );
}
