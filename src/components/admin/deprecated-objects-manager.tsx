'use client'

import React, { useState, useEffect } from 'react';
import dynamic from 'next/dynamic';
import { useAdminContext } from '../../contexts/admin-context';
import { useToast } from '../../hooks/use-toast';
import Toast from '../ui/toast';

const ChangelogEditor = dynamic(() => import('./changelog-editor'), {
  ssr: false,
});

const AdminBlueprintPicker = dynamic(() => import('./admin-blueprint-picker'), {
  ssr: false,
});

interface DeprecatedBlueprint {
  id: string;
  blueprint_name: string;
  full_name: string;
  deprecated: boolean;
  successor_id: string | null;
  successor_info?: {
    name: string;
    full_name: string;
    changelog?: string;
  };
  created_at: string;
  updated_at: string;
}

const DeprecatedObjectsManager: React.FC = () => {
  const { state: adminState } = useAdminContext();
  const { toasts, showToast, removeToast } = useToast();
  const [deprecatedBlueprints, setDeprecatedBlueprints] = useState<DeprecatedBlueprint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedSuccessor, setSelectedSuccessor] = useState<string | null>(null);
  const [showChangelogEditor, setShowChangelogEditor] = useState(false);
  const [editingBlueprint, setEditingBlueprint] = useState<DeprecatedBlueprint | null>(null);
  const [showSuccessorPicker, setShowSuccessorPicker] = useState(false);
  const [attachingToBlueprint, setAttachingToBlueprint] = useState<DeprecatedBlueprint | null>(null);
  const [showDisconnectConfirm, setShowDisconnectConfirm] = useState<DeprecatedBlueprint | null>(null);

  useEffect(() => {
    loadDeprecatedBlueprints();
  }, []);

  const loadDeprecatedBlueprints = async () => {
    try {
      const response = await fetch('/api/blueprints/deprecated');
      if (!response.ok) {
        throw new Error('Failed to fetch deprecated blueprints');
      }
      const data = await response.json();
      setDeprecatedBlueprints(data);
    } catch (err) {
      setError('Failed to load deprecated blueprints');
      console.error('Deprecated blueprints loading error:', err);
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  const handleEditChangelog = (blueprint: DeprecatedBlueprint) => {
    if (blueprint.successor_id) {
      setEditingBlueprint(blueprint);
      setSelectedSuccessor(blueprint.successor_id);
      setShowChangelogEditor(true);
    }
  };

  const handleAttachSuccessor = (blueprint: DeprecatedBlueprint) => {
    setAttachingToBlueprint(blueprint);
    setShowSuccessorPicker(true);
  };

  const handleSelectSuccessor = async (successorId: string) => {
    if (!attachingToBlueprint) return;

    try {
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };

      if (adminState.csrfToken) {
        headers['X-CSRF-Token'] = adminState.csrfToken;
      }

      const response = await fetch(`/api/blueprints/${attachingToBlueprint.id}`, {
        method: 'PATCH',
        headers,
        credentials: 'include',
        body: JSON.stringify({
          successor_id: successorId,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to attach successor');
      }

      // Close picker and reload
      setShowSuccessorPicker(false);
      setAttachingToBlueprint(null);
      showToast('Successor attached successfully', 'success');
      loadDeprecatedBlueprints();
    } catch (err) {
      console.error('Error attaching successor:', err);
      showToast('Failed to attach successor', 'error');
    }
  };

  const handleDisconnectSuccessor = async (blueprint: DeprecatedBlueprint) => {
    try {
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };

      if (adminState.csrfToken) {
        headers['X-CSRF-Token'] = adminState.csrfToken;
      }

      const response = await fetch(`/api/blueprints/${blueprint.id}/disconnect-successor`, {
        method: 'POST',
        headers,
        credentials: 'include',
      });

      if (!response.ok) {
        throw new Error('Failed to disconnect successor');
      }

      showToast('Successor disconnected successfully', 'success');
      // Reload the list
      loadDeprecatedBlueprints();
    } catch (err) {
      console.error('Error disconnecting successor:', err);
      showToast('Failed to disconnect successor', 'error');
    }
  };

  return (
    <div className="deprecated-objects-manager">
      <div className="manager-header">
        <h3>Deprecated Objects</h3>
        <p>Manage deprecated blueprints and their successor relationships</p>
      </div>

      {error && (
        <div className="error-message">
          {error}
        </div>
      )}

      {loading && (
        <div className="loading-message">
          Loading deprecated blueprints...
        </div>
      )}

      {!loading && !error && (
        <div className="deprecated-content">
          {deprecatedBlueprints.length === 0 ? (
            <div className="no-deprecated">
              <p>No deprecated blueprints found.</p>
              <p>Blueprints are marked as deprecated when they are replaced by newer versions.</p>
            </div>
          ) : (
            <div className="deprecated-list">
              {deprecatedBlueprints.map((blueprint) => (
                <div key={blueprint.id} className="deprecated-item">
                  <div className="deprecated-info">
                    {blueprint.successor_info ? (
                      <h4>{blueprint.blueprint_name} → {blueprint.successor_info.name}</h4>
                    ) : (
                      <h4>{blueprint.blueprint_name}</h4>
                    )}
                    <p className="deprecated-full-name">{blueprint.full_name}</p>
                    <div className="deprecated-meta">
                      <span className="deprecated-date">
                        Deprecated: {formatDate(blueprint.updated_at)}
                      </span>
                    </div>
                    {blueprint.successor_info?.changelog && (
                      <div className="changelog-display">
                        <strong>Changelog:</strong>
                        <p>{blueprint.successor_info.changelog}</p>
                      </div>
                    )}
                  </div>
                  <div className="deprecated-actions">
                    {blueprint.successor_id ? (
                      <>
                        <button
                          className="create-changelog-btn"
                          onClick={() => handleEditChangelog(blueprint)}
                        >
                          {blueprint.successor_info?.changelog ? 'Edit Changelog' : 'Create Changelog'}
                        </button>
                        <button
                          className="disconnect-btn"
                          onClick={() => setShowDisconnectConfirm(blueprint)}
                          title="Disconnect successor"
                        >
                          Disconnect
                        </button>
                      </>
                    ) : (
                      <button
                        className="attach-successor-btn"
                        onClick={() => handleAttachSuccessor(blueprint)}
                      >
                        Attach Successor
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {showChangelogEditor && selectedSuccessor && (
        <div className="modal-overlay" onClick={() => setShowChangelogEditor(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '800px' }}>
            <div className="modal-header">
              <h3>
                {editingBlueprint?.successor_info?.changelog ? 'Edit' : 'Create'} Changelog for {editingBlueprint?.successor_info?.name || 'Successor'}
              </h3>
              <button className="modal-close" onClick={() => setShowChangelogEditor(false)}>
                ×
              </button>
            </div>
            <div className="modal-body" style={{ height: '500px' }}>
              <ChangelogEditor
                blueprintId={selectedSuccessor}
                blueprintName={editingBlueprint?.successor_info?.name || 'Blueprint'}
                onClose={() => {
                  setShowChangelogEditor(false);
                  loadDeprecatedBlueprints(); // Reload to show updated changelog
                }}
              />
            </div>
          </div>
        </div>
      )}

      {showSuccessorPicker && (
        <AdminBlueprintPicker
          isOpen={showSuccessorPicker}
          onSelect={(blueprint) => handleSelectSuccessor(blueprint.id)}
          onClose={() => {
            setShowSuccessorPicker(false);
            setAttachingToBlueprint(null);
          }}
        />
      )}

      {showDisconnectConfirm && (
        <div className="modal-overlay" onClick={() => setShowDisconnectConfirm(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '400px' }}>
            <div className="modal-header">
              <h3>Confirm Disconnect</h3>
              <button className="modal-close" onClick={() => setShowDisconnectConfirm(null)}>
                ×
              </button>
            </div>
            <div className="modal-body" style={{ padding: '20px' }}>
              <p>Are you sure you want to disconnect the successor relationship?</p>
              <p style={{ marginTop: '10px', fontSize: '14px', color: '#666' }}>
                This will remove the link between {showDisconnectConfirm.blueprint_name} and its successor.
              </p>
              <div style={{ marginTop: '20px', display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
                <button
                  onClick={() => setShowDisconnectConfirm(null)}
                  style={{
                    padding: '8px 16px',
                    background: '#6c757d',
                    color: 'white',
                    border: 'none',
                    borderRadius: '4px',
                    cursor: 'pointer',
                  }}
                >
                  Cancel
                </button>
                <button
                  onClick={() => {
                    handleDisconnectSuccessor(showDisconnectConfirm);
                    setShowDisconnectConfirm(null);
                  }}
                  style={{
                    padding: '8px 16px',
                    background: '#dc3545',
                    color: 'white',
                    border: 'none',
                    borderRadius: '4px',
                    cursor: 'pointer',
                  }}
                >
                  Disconnect
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {toasts.map(toast => (
        <Toast
          key={toast.id}
          message={toast.message}
          type={toast.type}
          onClose={() => removeToast(toast.id)}
        />
      ))}
    </div>
  );
};

export default DeprecatedObjectsManager;
