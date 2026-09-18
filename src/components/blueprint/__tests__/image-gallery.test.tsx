import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import ImageGallery from '../image-gallery';
import { createMockBlueprint } from '@/test-utils';
import type { Image, ThumbnailVariants } from '@/types';

// Mock fetch globally
global.fetch = jest.fn();

describe('ImageGallery', () => {
  const mockBlueprint = createMockBlueprint({
    id: 'test-blueprint-id',
    images: [
      { id: '1', image_url: 'image1.jpg', image_name: 'Image 1', created_at: '2023-01-01', updated_at: '2023-01-01' },
      { id: '2', image_url: 'image2.jpg', image_name: 'Image 2', created_at: '2023-01-01', updated_at: '2023-01-01' },
      { id: '3', image_url: 'image3.jpg', image_name: 'Image 3', created_at: '2023-01-01', updated_at: '2023-01-01' }
    ]
  });

  beforeEach(() => {
    jest.clearAllMocks();
    (global.fetch as jest.Mock).mockReset();
  });

  it('renders all images in the gallery for legacy thumbnails', async () => {
    const legacyResponse: ThumbnailVariants = {
      type: 'single',
      thumbnail_url: 'legacy-thumb.jpg'
    };

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => legacyResponse,
    });

    render(<ImageGallery blueprint={mockBlueprint} />);

    await waitFor(() => {
      const images = screen.getAllByRole('img');
      expect(images).toHaveLength(3);
      expect(images[0]).toHaveAttribute('src', 'image1.jpg');
      expect(images[1]).toHaveAttribute('src', 'image2.jpg');
      expect(images[2]).toHaveAttribute('src', 'image3.jpg');
    });
  });

  it('renders images with correct alt text for legacy thumbnails', async () => {
    const legacyResponse: ThumbnailVariants = {
      type: 'single',
      thumbnail_url: 'legacy-thumb.jpg'
    };

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => legacyResponse,
    });

    render(<ImageGallery blueprint={mockBlueprint} />);

    await waitFor(() => {
      expect(screen.getByAltText('Image 1')).toBeInTheDocument();
      expect(screen.getByAltText('Image 2')).toBeInTheDocument();
      expect(screen.getByAltText('Image 3')).toBeInTheDocument();
    });
  });

  it('renders images in individual div containers for legacy thumbnails', async () => {
    const legacyResponse: ThumbnailVariants = {
      type: 'single',
      thumbnail_url: 'legacy-thumb.jpg'
    };

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => legacyResponse,
    });

    render(<ImageGallery blueprint={mockBlueprint} />);

    await waitFor(() => {
      const imageContainers = screen.getAllByRole('img').map(img => img.parentElement);
      expect(imageContainers).toHaveLength(3);
      imageContainers.forEach(container => {
        expect(container).toBeInTheDocument();
      });
    });
  });

  it('returns null when blueprint has no images after API error', async () => {
    const blueprintWithoutImages = createMockBlueprint({ id: 'test-id', images: [] });

    (global.fetch as jest.Mock).mockRejectedValueOnce(new Error('API error'));

    const { container } = render(<ImageGallery blueprint={blueprintWithoutImages} />);

    await waitFor(() => {
      expect(container.firstChild).toBeNull();
    });
  });

  it('returns null when blueprint images is undefined after API error', async () => {
    const blueprintWithoutImages = createMockBlueprint({ id: 'test-id', images: undefined as unknown as Image[] });

    (global.fetch as jest.Mock).mockRejectedValueOnce(new Error('API error'));

    const { container } = render(<ImageGallery blueprint={blueprintWithoutImages} />);

    await waitFor(() => {
      expect(container.firstChild).toBeNull();
    });
  });

  it('handles single image for legacy thumbnails', async () => {
    const singleImageBlueprint = createMockBlueprint({
      id: 'single-image-id',
      images: [{ id: '1', image_url: 'single.jpg', image_name: 'Single Image', created_at: '2023-01-01', updated_at: '2023-01-01' }]
    });

    const legacyResponse: ThumbnailVariants = {
      type: 'single',
      thumbnail_url: 'legacy-thumb.jpg'
    };

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => legacyResponse,
    });

    render(<ImageGallery blueprint={singleImageBlueprint} />);

    await waitFor(() => {
      const image = screen.getByRole('img');
      expect(image).toBeInTheDocument();
      expect(image).toHaveAttribute('src', 'single.jpg');
      expect(image).toHaveAttribute('alt', 'Single Image');
    });
  });

  it('renders images in a container div for legacy thumbnails', async () => {
    const legacyResponse: ThumbnailVariants = {
      type: 'single',
      thumbnail_url: 'legacy-thumb.jpg'
    };

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => legacyResponse,
    });

    render(<ImageGallery blueprint={mockBlueprint} />);

    await waitFor(() => {
      const container = screen.getByTestId('image-gallery-container');
      expect(container).toBeInTheDocument();
    });
  });

  it('shows loading state initially', () => {
    (global.fetch as jest.Mock).mockImplementation(() => new Promise(() => {})); // Never resolves

    render(<ImageGallery blueprint={mockBlueprint} />);

    expect(screen.getByText('Loading...')).toBeInTheDocument();
  });

  it('renders SpriteViewer when API returns sprite data', async () => {
    const spriteResponse: ThumbnailVariants = {
      type: 'sprite',
      sprite_url: 'https://example.com/sprite.png',
      grid_rows: 2,
      grid_cols: 5,
      tile_size: 512,
      angles: [
        { index: 0, name: 'front', camera_pos: [0, -4, 2] },
        { index: 1, name: 'front-right', camera_pos: [3, -3, 2] },
        { index: 2, name: 'right', camera_pos: [4, 0, 2] },
        { index: 3, name: 'back-right', camera_pos: [3, 3, 2] },
        { index: 4, name: 'back', camera_pos: [0, 4, 2] },
        { index: 5, name: 'back-left', camera_pos: [-3, 3, 2] },
        { index: 6, name: 'left', camera_pos: [-4, 0, 2] },
        { index: 7, name: 'front-left', camera_pos: [-3, -3, 2] },
        { index: 8, name: 'top', camera_pos: [0, -2, 5] },
        { index: 9, name: 'bottom', camera_pos: [0, -2, -3] },
      ],
      default_angle: 0,
    };

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => spriteResponse,
    });

    render(<ImageGallery blueprint={mockBlueprint} />);

    await waitFor(() => {
      expect(screen.getByTestId('sprite-viewer-container')).toBeInTheDocument();
    });
  });

  it('falls back to legacy gallery when API fails', async () => {
    (global.fetch as jest.Mock).mockRejectedValueOnce(new Error('API error'));

    render(<ImageGallery blueprint={mockBlueprint} />);

    await waitFor(() => {
      const images = screen.getAllByRole('img');
      expect(images).toHaveLength(3);
    });
  });
});
