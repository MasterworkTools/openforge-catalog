'use client'

import React, { useState, useEffect, useRef, useCallback } from 'react';
import dynamic from 'next/dynamic';
import ImagePicker from './image-picker';
import { Blueprint } from '@/types';
import { useAdminContext } from '@/contexts/admin-context';

// Dynamic import to avoid SSR issues with markdown editor
const MDEditor = dynamic(
  () => import('@uiw/react-md-editor'),
  { ssr: false }
);

type DocumentationTarget =
  | { type: 'blueprint'; blueprint: Blueprint }
  | { type: 'tag'; tag: string[] };

interface MarkdownEditorProps {
  target: DocumentationTarget;
}

interface DocumentationData {
  id?: string;
  document: string;
  document_type: 'changelog' | 'instructions';
  is_live: boolean;
}

interface ApiDocumentationItem {
  id: string;
  document: string;
  document_type: 'changelog' | 'instructions';
  is_live: boolean;
  created_at: string;
  updated_at: string;
}

const MarkdownEditor: React.FC<MarkdownEditorProps> = ({ target }) => {
  const [content, setContent] = useState('');
  // Always use 'instructions' for regular documentation editor
  const documentType = 'instructions' as const;
  const [isLive, setIsLive] = useState(true);
  const [showImagePicker, setShowImagePicker] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [existingDoc, setExistingDoc] = useState<DocumentationData | null>(null);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const editorRef = useRef<any>(null);

  // Get CSRF token from admin context
  const { state: adminState } = useAdminContext();

  // Convert Obsidian image syntax to standard markdown/HTML
  const processObsidianImages = (markdown: string): string => {
    // Pattern to match Obsidian image syntax: ![alt|width](url) or ![alt|widthxheight](url)
    const obsidianImageRegex = /!\[([^\]|]*)\|(\d+)(?:x(\d+))?\]\(([^)]+)\)/g;

    return markdown.replace(obsidianImageRegex, (_match, alt, width, height, url) => {
      // For MDEditor preview, we'll use HTML img tags
      if (height) {
        return `<img src="${url}" alt="${alt}" width="${width}" height="${height}" />`;
      } else {
        return `<img src="${url}" alt="${alt}" width="${width}" />`;
      }
    });
  };

  // Load existing documentation
  useEffect(() => {
    let isCancelled = false;

    // Helper function to load and select the correct instructions document
    const loadInstructionsDocument = async (endpoint: string, targetName: string): Promise<ApiDocumentationItem | null> => {
      const response = await fetch(endpoint, {
        credentials: 'include', // Include cookies for authentication
      });
      if (!response.ok) {
        console.error('Failed to load documentation:', {
          status: response.status,
          statusText: response.statusText,
          endpoint
        });
        return null;
      }

      const docs = await response.json();
      console.log('Loaded documentation:', { endpoint, docs });
      const instructionsDocs = docs.documentation?.filter((doc: ApiDocumentationItem) => doc.document_type === 'instructions') || [];

      if (instructionsDocs.length > 1) {
        console.warn(`Multiple instructions documents found for ${targetName}. This should not happen.`);
        // Prioritize live document, then most recently updated
        const liveDoc = instructionsDocs.find((doc: ApiDocumentationItem) => doc.is_live);
        if (liveDoc) {
          return liveDoc;
        } else {
          // Sort by updated_at descending and take the most recent
          const sortedDocs = instructionsDocs.sort((a: ApiDocumentationItem, b: ApiDocumentationItem) =>
            new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
          );
          return sortedDocs[0];
        }
      } else if (instructionsDocs.length === 1) {
        return instructionsDocs[0];
      }

      return null;
    };

    const loadExistingDocumentation = async () => {
      try {
        let docToSet: DocumentationData | null = null;

        if (target.type === 'blueprint') {
          docToSet = await loadInstructionsDocument(
            `/api/blueprints/${target.blueprint.id}/documentation`,
            `blueprint ${target.blueprint.id}`
          );
        } else {
          const tagPath = target.tag.join('/');
          docToSet = await loadInstructionsDocument(
            `/api/tags/${tagPath}/documentation`,
            `tag ${tagPath}`
          );
        }

        if (!isCancelled && docToSet) {
          setExistingDoc(docToSet);
          setContent(docToSet.document);
          // Document type is always 'instructions' for regular documentation
          setIsLive(docToSet.is_live);
        }
      } catch (err) {
        if (!isCancelled) {
          console.error('Failed to load existing documentation:', err);
        }
      }
    };

    loadExistingDocumentation();

    return () => {
      isCancelled = true;
    };
  }, [target]);

  const saveDocument = useCallback(async (makeLive: boolean = false) => {
    if (!content.trim()) return;

    setSaving(true);
    setSaveStatus('saving');
    setError(null);

    try {
      const saveData = {
        document: content,
        document_type: documentType,
        is_live: makeLive,
      };

      // Determine base URL and method based on target type and whether document exists
      let baseUrl;
      if (target.type === 'blueprint') {
        baseUrl = `/api/blueprints/${target.blueprint.id}/documentation`;
      } else {
        const tagPath = target.tag.join('/');
        baseUrl = `/api/tags/${tagPath}/documentation`;
      }

      const url = existingDoc?.id ? `${baseUrl}/${existingDoc.id}` : baseUrl;
      const method = existingDoc?.id ? 'PATCH' : 'POST';

      console.log('Saving documentation:', {
        url,
        method,
        saveData,
        existingDoc,
        target
      });

      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };

      // Add CSRF token if available
      if (adminState.csrfToken) {
        headers['X-CSRF-Token'] = adminState.csrfToken;
      }

      const response = await fetch(url, {
        method,
        headers,
        credentials: 'include', // Include cookies for authentication
        body: JSON.stringify(saveData),
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error('Save failed:', {
          status: response.status,
          statusText: response.statusText,
          url,
          method,
          body: errorText
        });
        throw new Error(`Failed to save documentation: ${response.status} ${response.statusText} - ${errorText}`);
      }

      const responseData = await response.json();
      console.log('Save response:', responseData);

      // The API might return { documentation: {...} } or just the document
      const savedDoc = responseData.documentation || responseData;
      setExistingDoc(savedDoc);
      setSaveStatus('saved');

      // Update the displayed message based on what was saved
      if (makeLive) {
        setIsLive(true);
        setSuccessMessage('Published successfully!');
      } else {
        setSuccessMessage('Draft saved successfully!');
      }

      // Clear saved status after 3 seconds
      setTimeout(() => {
        setSaveStatus('idle');
        setSuccessMessage(null);
      }, 3000);
    } catch (err) {
      console.error('Save error:', err);
      const errorMessage = err instanceof Error ? err.message : 'Failed to save documentation';
      setError(errorMessage);
      setSaveStatus('error');

      // Clear error status after 5 seconds
      setTimeout(() => {
        setSaveStatus('idle');
      }, 5000);
    } finally {
      setSaving(false);
    }
  }, [content, documentType, target, existingDoc, adminState.csrfToken]);


  // TODO: Implement drag and drop image upload
  // The MDEditor expects onDrop to be a DragEventHandler<HTMLDivElement>
  // but our handleImageUpload function signature doesn't match
  // For now, users can use the image picker button instead

  const insertImage = (imageUrl: string, imageName: string) => {
    // Use Obsidian's image resize syntax with a default width of 400px
    const imageMarkdown = `![${imageName}|400](${imageUrl})`;

    // Since MDEditor doesn't expose a ref API, we'll insert at cursor position
    // by updating the content state
    setContent(prevContent => {
      // Simple approach: append to the end if we can't determine cursor position
      return prevContent + '\n\n' + imageMarkdown;
    });
  };

  const getTargetDisplay = () => {
    if (target.type === 'blueprint') {
      return target.blueprint.blueprint_name;
    } else {
      return target.tag.join(': ');
    }
  };

  return (
    <div className="markdown-editor">
      <div className="editor-header">
        <div className="target-info">
          <h4>Editing: {getTargetDisplay()}</h4>
        </div>

        <div className="editor-controls">
          <label className="live-toggle">
            <input
              type="checkbox"
              checked={isLive}
              onChange={(e) => setIsLive(e.target.checked)}
            />
            Live
          </label>

          <button
            onClick={() => saveDocument(false)}
            disabled={saving || !content.trim()}
            className="save-draft-button"
            style={{
              marginRight: '0.5rem',
              padding: '0.5rem 1rem',
              backgroundColor: '#6b7280',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: saving || !content.trim() ? 'not-allowed' : 'pointer',
              opacity: saving || !content.trim() ? 0.6 : 1,
              fontSize: '14px',
              fontWeight: '500',
              transition: 'background-color 0.2s'
            }}
            onMouseEnter={(e) => {
              if (!saving && content.trim()) {
                e.currentTarget.style.backgroundColor = '#4b5563';
              }
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = '#6b7280';
            }}
          >
            {saving ? 'Saving...' : 'Save Draft'}
          </button>
          <button
            onClick={() => saveDocument(true)}
            disabled={saving || !content.trim()}
            className="publish-button"
            style={{
              padding: '0.5rem 1rem',
              backgroundColor: '#10b981',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: saving || !content.trim() ? 'not-allowed' : 'pointer',
              opacity: saving || !content.trim() ? 0.6 : 1,
              fontSize: '14px',
              fontWeight: '500',
              transition: 'background-color 0.2s'
            }}
            onMouseEnter={(e) => {
              if (!saving && content.trim()) {
                e.currentTarget.style.backgroundColor = '#059669';
              }
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = '#10b981';
            }}
          >
            {saving ? 'Publishing...' : 'Publish'}
          </button>
        </div>

        <div className="save-status">
          {saveStatus === 'saving' && <span className="saving">Saving...</span>}
          {saveStatus === 'saved' && successMessage && <span className="saved">{successMessage}</span>}
          {saveStatus === 'error' && <span className="error">{error || 'Unknown error'}</span>}
        </div>
      </div>

      {error && (
        <div className="error-message">
          {error}
        </div>
      )}

      <div className="editor-container">
        <MDEditor
          ref={editorRef}
          value={content}
          onChange={(value) => {
            setContent(value || '');
            if (error || successMessage) {
              setError(null);
              setSuccessMessage(null);
              setSaveStatus('idle');
            }
          }}
          preview="live"
          height={500}
          // onDrop={handleImageUpload} // TODO: Fix type mismatch - MDEditor expects DragEventHandler
          textareaProps={{
            placeholder: "Enter documentation content...",
          }}
          commands={[
            {
              name: 'image-picker',
              keyCommand: 'image-picker',
              buttonProps: { 'aria-label': 'Insert image from library' },
              icon: <span>📷</span>,
              execute: () => setShowImagePicker(true),
            }
          ]}
          previewOptions={{
            // Process the markdown to handle Obsidian image syntax
            components: {
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              code({ inline, className, children, ...props }: any) {
                // Default code rendering
                const match = /language-(\w+)/.exec(className || '');
                return !inline && match ? (
                  <pre className={className}>
                    <code className={className} {...props}>
                      {children}
                    </code>
                  </pre>
                ) : (
                  <code className={className} {...props}>
                    {children}
                  </code>
                );
              },
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              img: ({ src, alt, className, ...props }: any) => {
                // Check if this is Obsidian syntax that wasn't processed
                const altMatch = alt?.match(/^(.+)\|(\d+)$/);
                if (altMatch) {
                  const [, realAlt, width] = altMatch;
                  // Remove max-w-full class and use inline style
                  const filteredClassName = className?.replace(/\bmax-w-full\b/g, '').trim();
                  return (
                    <>
                      <img
                        src={src}
                        alt={realAlt}
                        className={filteredClassName}
                        style={{ width: `${width}px`, height: 'auto' }}
                        {...props}
                      />
                    </>
                  );
                }
                return <img src={src} alt={alt} className={className} {...props} />;
              }
            },
            // Use urlTransform instead of deprecated transformImageUri/transformLinkUri
            urlTransform: (url: string) => url,
          }}
          // @ts-expect-error - renderPreview might not be in the type definitions
          renderPreview={(source: string) => {
            // Process Obsidian syntax before rendering
            const processed = processObsidianImages(source);
            // @ts-expect-error - MDEditor.Markdown might not be in the type definitions
            return <MDEditor.Markdown source={processed} />;
          }}
        />
      </div>

      {showImagePicker && (
        <ImagePicker
          onSelect={(image) => {
            insertImage(image.image_url, image.image_name);
            setShowImagePicker(false);
          }}
          onClose={() => setShowImagePicker(false)}
        />
      )}
    </div>
  );
};

export default MarkdownEditor;
