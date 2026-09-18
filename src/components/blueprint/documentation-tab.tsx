'use client'

import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { BlueprintDocumentation, TagDocumentation } from '@/types';

// Custom component to handle image rendering
const ImageRenderer = ({ src, alt }: { src: string; alt: string }) => {
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    const fetchImage = async () => {
      try {
        // If it's already a full URL, use it directly
        if (src.startsWith('http')) {
          setImageUrl(src);
          setLoading(false);
          return;
        }

        // For relative paths, we need to fetch the image object
        // This assumes the image name is the filename without extension
        const imageName = src.replace(/\.[^/.]+$/, ''); // Remove file extension

        const response = await fetch(`/api/images?image_name=${encodeURIComponent(imageName)}`);
        if (response.ok) {
          const images = await response.json();
          if (images.length > 0) {
            // If multiple images have the same name, use the most recently created one
            // (they're already ordered by created_at DESC from the backend)
            setImageUrl(images[0].image_url);
          } else {
            setError(true);
          }
        } else {
          setError(true);
        }
             } catch (err) {
         console.error('Error fetching image:', src, err);
         setError(true);
       } finally {
        setLoading(false);
      }
    };

    fetchImage();
  }, [src]);

  if (loading) {
    return <span className="text-gray-500">Loading image...</span>;
  }

  if (error || !imageUrl) {
    return <span className="text-red-500">Image not found: {src}</span>;
  }

  // Check if alt contains Obsidian-style width syntax
  const altMatch = alt?.match(/^(.+)\|(\d+)$/);
  if (altMatch) {
    const [, realAlt, width] = altMatch;
    return <img src={imageUrl} alt={realAlt} style={{ width: `${width}px`, height: 'auto' }} />;
  }

  return <img src={imageUrl} alt={alt} className="max-w-full h-auto" />;
};

interface DocumentationTabProps {
  blueprintDocumentation: BlueprintDocumentation[];
  tagDocumentation: Record<string, TagDocumentation[]>;
}

const DocumentationTab: React.FC<DocumentationTabProps> = ({
  blueprintDocumentation,
  tagDocumentation
}) => {
  // Filter to only show instructions (not changelogs)
  const instructionDocs = blueprintDocumentation.filter(
    doc => doc.document_type === 'instructions'
  );

  // Format tag for display (replace | with ": ")
  const formatTagForDisplay = (tag: string[] | string): string => {
    if (Array.isArray(tag)) {
      return tag.join(': ');
    }
    // If tag is a string, split by | and then join with :
    return tag.split('|').join(': ');
  };

  // Format date for hover display
  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  return (
    <div className="documentation-tab">
      {/* Blueprint Documentation Section */}
      {instructionDocs.length > 0 && (
        <div className="mb-8">
          <h2
            className="text-xl font-semibold mb-4 text-gray-800"
            title={`Last updated: ${formatDate(instructionDocs[0].updated_at)}`}
          >
            Documentation
          </h2>
          <div className="prose prose-sm max-w-none">
            {instructionDocs.map((doc) => (
                                      <div key={doc.id} className="mb-6">
                          <ReactMarkdown
                            components={{
                              img: ({ src, alt }) => <ImageRenderer src={String(src || '')} alt={String(alt || '')} />
                            }}
                          >
                            {doc.document}
                          </ReactMarkdown>
                        </div>
            ))}
          </div>
        </div>
      )}

      {/* Tag Documentation Sections */}
      {Object.entries(tagDocumentation).map(([tagKey, docs], index) => {
        if (docs.length === 0) return null;

        return (
          <div key={tagKey} className="mb-8">
            {index > 0 && <hr className="my-6 border-gray-200" />}
            <h3
              className="text-lg font-semibold mb-4 text-gray-700"
              title={`Last updated: ${formatDate(docs[0].updated_at)}`}
            >
              {formatTagForDisplay(docs[0].tag)}
            </h3>
            <div className="prose prose-sm max-w-none">
                                        {docs.map((doc) => (
                            <div key={doc.id} className="mb-4">
                              <ReactMarkdown
                                components={{
                                  img: ({ src, alt }) => <ImageRenderer src={String(src || '')} alt={String(alt || '')} />
                                }}
                              >
                                {doc.document}
                              </ReactMarkdown>
                            </div>
                          ))}
            </div>
          </div>
        );
      })}

      {/* No documentation message */}
      {instructionDocs.length === 0 && Object.keys(tagDocumentation).length === 0 && (
        <div className="text-center py-8 text-gray-500">
          <p>No documentation available for this blueprint.</p>
        </div>
      )}
    </div>
  );
};

export default DocumentationTab;
