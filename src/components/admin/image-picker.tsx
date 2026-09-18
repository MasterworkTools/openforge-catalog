'use client'

import React, { useState, useEffect } from 'react';
import { useAdminContext } from '@/contexts/admin-context';

interface Image {
  id: string;
  image_name: string;
  image_url: string;
  image_type: 'thumbnail' | 'documentation';
  created_at: string;
  updated_at: string;
}

interface ImagePickerProps {
  onSelect: (image: Image) => void;
  onClose: () => void;
}

const ImagePicker: React.FC<ImagePickerProps> = ({ onSelect, onClose }) => {
  const { state: adminState } = useAdminContext();
  const [images, setImages] = useState<Image[]>([]);
  const [filter, setFilter] = useState('');
  const [uploading, setUploading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [imageName, setImageName] = useState('');

  useEffect(() => {
    loadImages();
  }, []);

  const loadImages = async () => {
    try {
      const response = await fetch('/api/images?image_type=documentation');
      if (!response.ok) {
        throw new Error('Failed to load images');
      }
      const data = await response.json();
      setImages(data || []);
    } catch (err) {
      setError('Failed to load images');
      console.error('Image loading error:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedFile(file);
      // Pre-fill the name field with the file name (without extension)
      const nameWithoutExt = file.name.replace(/\.[^/.]+$/, '');
      setImageName(nameWithoutExt);
      setError(null);
    }
  };

  const handleFileUpload = async () => {
    if (!selectedFile || !imageName.trim()) {
      setError('Please select a file and provide a name');
      return;
    }

    setUploading(true);
    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('metadata', JSON.stringify({
      image_name: imageName.trim(),
      image_type: 'documentation'
    }));

    try {
      const headers: Record<string, string> = {};

      // Add CSRF token if available
      if (adminState.csrfToken) {
        headers['X-CSRF-Token'] = adminState.csrfToken;
      }

      const response = await fetch('/api/images', {
        method: 'POST',
        headers: headers,
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        throw new Error(errorData?.error || `Upload failed with status ${response.status}`);
      }

      const image = await response.json();
      setImages(prev => [image, ...prev]);
      setError(null); // Clear any previous errors
      setSelectedFile(null); // Clear the selected file
      setImageName(''); // Clear the name input
      // Reset file input
      const fileInput = document.querySelector('.file-input') as HTMLInputElement;
      if (fileInput) fileInput.value = '';
    } catch (error) {
      console.error('Upload failed:', error);
      setError(error instanceof Error ? error.message : 'Failed to upload image');
    } finally {
      setUploading(false);
    }
  };

  const filteredImages = images.filter(img =>
    img.image_name.toLowerCase().includes(filter.toLowerCase())
  );

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content image-picker-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>Select Image</h3>
          <button className="modal-close" onClick={onClose}>
            ×
          </button>
        </div>

        <div className="modal-body">
          <div className="image-picker-header">
            <input
              type="text"
              placeholder="Search images..."
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              className="search-input"
            />
          </div>

          <div className="upload-section" style={{
            padding: '1rem',
            borderBottom: '1px solid #e0e0e0',
            backgroundColor: '#f5f5f5'
          }}>
            <h4 style={{ marginTop: 0, marginBottom: '0.5rem' }}>Upload New Image</h4>
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'flex-end' }}>
              <div style={{ flex: 1 }}>
                <input
                  type="file"
                  accept="image/*"
                  onChange={handleFileSelect}
                  disabled={uploading}
                  className="file-input"
                  style={{ marginBottom: '0.5rem' }}
                />
                {selectedFile && (
                  <input
                    type="text"
                    placeholder="Image name"
                    value={imageName}
                    onChange={(e) => setImageName(e.target.value)}
                    disabled={uploading}
                    style={{
                      width: '100%',
                      padding: '0.5rem',
                      border: '1px solid #ddd',
                      borderRadius: '4px'
                    }}
                  />
                )}
              </div>
              {selectedFile && (
                <button
                  onClick={handleFileUpload}
                  disabled={uploading || !imageName.trim()}
                  style={{
                    padding: '0.5rem 1rem',
                    backgroundColor: uploading || !imageName.trim() ? '#ccc' : '#4CAF50',
                    color: 'white',
                    border: 'none',
                    borderRadius: '4px',
                    cursor: uploading || !imageName.trim() ? 'not-allowed' : 'pointer'
                  }}
                >
                  {uploading ? 'Uploading...' : 'Upload'}
                </button>
              )}
            </div>
          </div>

          {error && (
            <div className="error-message">
              {error}
            </div>
          )}

          {loading && (
            <div className="loading-message">
              Loading images...
            </div>
          )}

          <div className="image-grid">
            {filteredImages.map(image => (
              <button
                key={image.id}
                className="image-item"
                onClick={() => onSelect(image)}
                type="button"
              >
                <img src={image.image_url} alt={image.image_name} />
                <span className="image-name">{image.image_name}</span>
              </button>
            ))}
          </div>

          {!loading && !error && filteredImages.length === 0 && (
            <div className="no-images">
              {filter ? 'No images found matching your search.' : 'No documentation images available.'}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ImagePicker;
