'use client'

import React, { useState, useEffect } from 'react';
import dynamic from 'next/dynamic';
import { useAdminContext } from '@/contexts/admin-context';

// Dynamic import to avoid SSR issues with markdown editor
const MDEditor = dynamic(
  () => import('@uiw/react-md-editor'),
  { ssr: false }
);

interface ChangelogEditorProps {
  blueprintId: string;
  blueprintName: string;
  onClose?: () => void;
}

interface ChangelogData {
  id?: string;
  document: string;
  document_type: 'changelog';
  is_live: boolean;
}

const ChangelogEditor: React.FC<ChangelogEditorProps> = ({ blueprintId, onClose }) => {
  const { state: adminState } = useAdminContext();
  const [content, setContent] = useState('');
  const [isLive, setIsLive] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  const [error, setError] = useState<string | null>(null);
  const [existingDoc, setExistingDoc] = useState<ChangelogData | null>(null);

  useEffect(() => {
    let isCancelled = false;

    const loadExistingChangelog = async () => {
      try {
        const response = await fetch(`/api/blueprints/${blueprintId}/documentation`);
        if (isCancelled) return;

        if (!response.ok) {
          if (response.status === 404) {
            // No existing documentation, that's fine
            return;
          }
          throw new Error('Failed to load documentation');
        }

        const data = await response.json();
        if (isCancelled) return;

        const docs = data.documentation || [];
        // Find the live changelog
        const changelog = docs.find((doc: ChangelogData) =>
          doc.document_type === 'changelog' && doc.is_live
        );

        if (changelog) {
          setExistingDoc(changelog);
          setContent(changelog.document);
          setIsLive(changelog.is_live);
        }
      } catch (err) {
        if (!isCancelled) {
          console.error('Error loading changelog:', err);
          setError('Failed to load existing changelog');
        }
      }
    };

    loadExistingChangelog();

    return () => {
      isCancelled = true;
    };
  }, [blueprintId]);

  const handleSave = async () => {
    setSaving(true);
    setSaveStatus('saving');
    setError(null);

    try {
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };

      if (adminState.csrfToken) {
        headers['X-CSRF-Token'] = adminState.csrfToken;
      }

      const url = existingDoc
        ? `/api/blueprints/${blueprintId}/documentation/${existingDoc.id}`
        : `/api/blueprints/${blueprintId}/documentation`;

      const method = existingDoc ? 'PATCH' : 'POST';

      const response = await fetch(url, {
        method,
        headers,
        credentials: 'include',
        body: JSON.stringify({
          document: content,
          document_type: 'changelog',
          is_live: isLive,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
        throw new Error(errorData.error || 'Failed to save changelog');
      }

      const savedData = await response.json();
      setExistingDoc(savedData);
      setSaveStatus('saved');

      // Clear success status after 2 seconds
      setTimeout(() => {
        setSaveStatus('idle');
      }, 2000);
    } catch (err) {
      console.error('Save error:', err);
      setError(err instanceof Error ? err.message : 'Failed to save changelog');
      setSaveStatus('error');
    } finally {
      setSaving(false);
    }
  };

  const handlePublish = async () => {
    await handleSave();
    if (onClose) {
      onClose();
    }
  };

  return (
    <div className="changelog-editor">
      <div className="editor-controls" style={{ marginBottom: '10px', display: 'flex', gap: '10px', alignItems: 'center' }}>
        <button
          onClick={handleSave}
          disabled={saving}
          className="save-button"
          style={{
            padding: '8px 16px',
            background: '#6c757d',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
          }}
        >
          {saving ? 'Saving...' : 'Save Draft'}
        </button>

        <button
          onClick={handlePublish}
          disabled={saving}
          className="publish-button"
          style={{
            padding: '8px 16px',
            background: '#28a745',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
          }}
        >
          {saving ? 'Publishing...' : 'Publish'}
        </button>

        <label className="live-toggle" style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <input
            type="checkbox"
            checked={isLive}
            onChange={(e) => setIsLive(e.target.checked)}
          />
          Live
        </label>

        {saveStatus === 'saved' && (
          <span style={{ color: '#28a745', fontSize: '14px' }}>✓ Saved</span>
        )}

        {error && (
          <span style={{ color: '#dc3545', fontSize: '14px' }}>{error}</span>
        )}
      </div>

      <div className="editor-container" style={{ height: 'calc(100% - 50px)' }}>
        <MDEditor
          value={content}
          onChange={(val) => setContent(val || '')}
          preview="edit"
          height={400}
        />
      </div>
    </div>
  );
};

export default ChangelogEditor;
