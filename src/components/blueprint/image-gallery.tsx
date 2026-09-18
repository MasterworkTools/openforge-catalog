'use client'

import React, { useState, useEffect } from 'react';
import { Blueprint, ThumbnailVariants } from '@/types';
import SpriteViewer from './sprite-viewer';

interface BlueprintImageGalleryProps {
  blueprint: Blueprint;
}

const BlueprintImageGallery: React.FC<BlueprintImageGalleryProps> = ({ blueprint }) => {
  const [thumbnailData, setThumbnailData] = useState<ThumbnailVariants | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!blueprint?.id) {
      setIsLoading(false);
      return;
    }

    let cancelled = false;

    const fetchThumbnailData = async () => {
      try {
        const res = await fetch(`/api/blueprints/${blueprint.id}/thumbnail-variants`);
        if (!res.ok) throw new Error('Failed to fetch thumbnail variants');
        const data: ThumbnailVariants = await res.json();

        if (!cancelled) {
          setThumbnailData(data);
          setIsLoading(false);
        }
      } catch (error) {
        console.error('Error fetching thumbnail variants:', error);
        if (!cancelled) {
          setThumbnailData(null);
          setIsLoading(false);
        }
      }
    };

    fetchThumbnailData();

    return () => {
      cancelled = true;
    };
  }, [blueprint?.id]);

  if (isLoading) {
    return <div className="text-center text-gray-500">Loading...</div>;
  }

  // If sprite, show SpriteViewer
  if (thumbnailData?.type === 'sprite') {
    return <SpriteViewer key={blueprint.id} blueprint={blueprint} thumbnailData={thumbnailData} />;
  }

  // Legacy fallback
  if (!blueprint.images || blueprint.images.length === 0) {
    return null;
  }

  return (
    <div data-testid="image-gallery-container">
      {blueprint.images.map((image) => (
        <div key={image.id}>
          <img src={image.image_url} alt={image.image_name} />
        </div>
      ))}
    </div>
  );
};

export default BlueprintImageGallery;
