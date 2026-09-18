import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import SpriteViewer from '../sprite-viewer';
import { createMockBlueprint } from '@/test-utils';
import type { SpriteThumbnailData, SpriteAngle } from '@/types';

describe('SpriteViewer', () => {
  const mockAngles: SpriteAngle[] = [
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
  ];

  const mockThumbnailData: SpriteThumbnailData = {
    type: 'sprite',
    sprite_url: 'https://example.com/sprite.png',
    grid_rows: 2,
    grid_cols: 5,
    tile_size: 512,
    angles: mockAngles,
    default_angle: 0,
  };

  const mockBlueprint = createMockBlueprint({
    id: 'test-blueprint-id',
    blueprint_name: 'Test Model',
  });

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Rendering', () => {
    it('renders the sprite viewer container', () => {
      render(<SpriteViewer blueprint={mockBlueprint} thumbnailData={mockThumbnailData} />);
      expect(screen.getByTestId('sprite-viewer-container')).toBeInTheDocument();
    });

    it('renders sprite with correct default background position', () => {
      render(<SpriteViewer blueprint={mockBlueprint} thumbnailData={mockThumbnailData} />);

      const spriteElement = screen.getByLabelText(/Test Model.*front/);
      const style = spriteElement.style;

      expect(style.backgroundImage).toBe('url("https://example.com/sprite.png")');
      expect(style.backgroundPosition).toBe('0px 0px'); // Angle 0: row 0, col 0
      expect(style.width).toBe('512px');
      expect(style.height).toBe('512px');
    });

    it('renders sprite with custom default angle', () => {
      const customData = { ...mockThumbnailData, default_angle: 5 };
      render(<SpriteViewer blueprint={mockBlueprint} thumbnailData={customData} />);

      const spriteElement = screen.getByLabelText(/Test Model.*back-left/);
      // Angle 5: row 1, col 0 -> position: -(0 * 512)px -(1 * 512)px = 0px -512px
      expect(spriteElement.style.backgroundPosition).toBe('0px -512px');
    });

    it('renders unwrapped cube layout with all 10 angles', () => {
      render(<SpriteViewer blueprint={mockBlueprint} thumbnailData={mockThumbnailData} />);

      // Check for all angle buttons in the cube layout
      expect(screen.getByText('TOP')).toBeInTheDocument();
      expect(screen.getByText('F')).toBeInTheDocument();
      expect(screen.getByText('FL')).toBeInTheDocument();
      expect(screen.getByText('FR')).toBeInTheDocument();
      expect(screen.getByText('L')).toBeInTheDocument();
      expect(screen.getByText('R')).toBeInTheDocument();
      expect(screen.getByText('B')).toBeInTheDocument();
      expect(screen.getByText('BL')).toBeInTheDocument();
      expect(screen.getByText('BR')).toBeInTheDocument();
      expect(screen.getByText('BOT')).toBeInTheDocument();
    });

    it('renders keyboard hint', () => {
      render(<SpriteViewer blueprint={mockBlueprint} thumbnailData={mockThumbnailData} />);

      expect(screen.getByText('Use arrow keys or drag to rotate view')).toBeInTheDocument();
    });

    it('highlights current angle dot', () => {
      render(<SpriteViewer blueprint={mockBlueprint} thumbnailData={mockThumbnailData} />);

      const frontDot = screen.getByTitle('front');
      expect(frontDot).toHaveClass('bg-blue-600');
    });
  });

  describe('UI Controls', () => {
    it('changes angle when clicking a dot', () => {
      render(<SpriteViewer blueprint={mockBlueprint} thumbnailData={mockThumbnailData} />);

      const rightDot = screen.getByTitle('right'); // Angle 2
      fireEvent.click(rightDot);

      const spriteElement = screen.getByLabelText(/Test Model.*right/);
      // Angle 2: row 0, col 2 -> position: -(2 * 512)px -(0 * 512)px = -1024px 0px
      expect(spriteElement.style.backgroundPosition).toBe('-1024px 0px');
    });

    it('changes angle when clicking TOP button', () => {
      render(<SpriteViewer blueprint={mockBlueprint} thumbnailData={mockThumbnailData} />);

      const topButton = screen.getByText('TOP');
      fireEvent.click(topButton);

      const spriteElement = screen.getByLabelText(/Test Model.*top/);
      // Angle 8: row 1, col 3 -> position: -(3 * 512)px -(1 * 512)px = -1536px -512px
      expect(spriteElement.style.backgroundPosition).toBe('-1536px -512px');
    });

    it('changes angle when clicking BOT button', () => {
      render(<SpriteViewer blueprint={mockBlueprint} thumbnailData={mockThumbnailData} />);

      const bottomButton = screen.getByText('BOT');
      fireEvent.click(bottomButton);

      const spriteElement = screen.getByLabelText(/Test Model.*bottom/);
      // Angle 9: row 1, col 4 -> position: -(4 * 512)px -(1 * 512)px = -2048px -512px
      expect(spriteElement.style.backgroundPosition).toBe('-2048px -512px');
    });

    it('highlights TOP button when active', () => {
      render(<SpriteViewer blueprint={mockBlueprint} thumbnailData={mockThumbnailData} />);

      const topButton = screen.getByText('TOP');
      fireEvent.click(topButton);

      expect(topButton).toHaveClass('bg-blue-600');
      expect(topButton).toHaveClass('text-white');
    });

    it('updates button highlighting when angle changes', () => {
      render(<SpriteViewer blueprint={mockBlueprint} thumbnailData={mockThumbnailData} />);

      const backButton = screen.getByText('B'); // Back angle
      fireEvent.click(backButton);

      expect(backButton).toHaveClass('bg-blue-600');
      expect(screen.getByText('F')).not.toHaveClass('bg-blue-600');
    });
  });

  describe('Keyboard Navigation', () => {
    it('changes to next angle on right arrow key', () => {
      render(<SpriteViewer blueprint={mockBlueprint} thumbnailData={mockThumbnailData} />);

      const spriteElement = screen.getByLabelText(/Test Model/);
      spriteElement.focus();

      fireEvent.keyDown(spriteElement, { key: 'ArrowRight' });

      const updatedElement = screen.getByLabelText(/Test Model.*front-right/);
      // Angle 1: row 0, col 1 -> position: -(1 * 512)px -(0 * 512)px = -512px 0px
      expect(updatedElement.style.backgroundPosition).toBe('-512px 0px');
    });

    it('changes to previous angle on left arrow key', () => {
      render(<SpriteViewer blueprint={mockBlueprint} thumbnailData={mockThumbnailData} />);

      const spriteElement = screen.getByLabelText(/Test Model/);
      spriteElement.focus();

      fireEvent.keyDown(spriteElement, { key: 'ArrowLeft' });

      const updatedElement = screen.getByLabelText(/Test Model.*front-left/);
      // Angle 7: row 1, col 2 -> position: -(2 * 512)px -(1 * 512)px = -1024px -512px
      expect(updatedElement.style.backgroundPosition).toBe('-1024px -512px');
    });

    it('wraps to angle 0 when pressing right at angle 7', () => {
      const customData = { ...mockThumbnailData, default_angle: 7 };
      render(<SpriteViewer blueprint={mockBlueprint} thumbnailData={customData} />);

      const spriteElement = screen.getByLabelText(/Test Model/);
      spriteElement.focus();

      fireEvent.keyDown(spriteElement, { key: 'ArrowRight' });

      const updatedElement = screen.getByLabelText(/Test Model.*front/);
      expect(updatedElement.style.backgroundPosition).toBe('0px 0px');
    });

    it('wraps to angle 7 when pressing left at angle 0', () => {
      render(<SpriteViewer blueprint={mockBlueprint} thumbnailData={mockThumbnailData} />);

      const spriteElement = screen.getByLabelText(/Test Model/);
      spriteElement.focus();

      fireEvent.keyDown(spriteElement, { key: 'ArrowLeft' });

      const updatedElement = screen.getByLabelText(/Test Model.*front-left/);
      expect(updatedElement.style.backgroundPosition).toBe('-1024px -512px');
    });

    it('changes to top view on up arrow key', () => {
      render(<SpriteViewer blueprint={mockBlueprint} thumbnailData={mockThumbnailData} />);

      const spriteElement = screen.getByLabelText(/Test Model/);
      spriteElement.focus();

      fireEvent.keyDown(spriteElement, { key: 'ArrowUp' });

      const updatedElement = screen.getByLabelText(/Test Model.*top/);
      expect(updatedElement.style.backgroundPosition).toBe('-1536px -512px');
    });

    it('changes to bottom view on down arrow key', () => {
      render(<SpriteViewer blueprint={mockBlueprint} thumbnailData={mockThumbnailData} />);

      const spriteElement = screen.getByLabelText(/Test Model/);
      spriteElement.focus();

      fireEvent.keyDown(spriteElement, { key: 'ArrowDown' });

      const updatedElement = screen.getByLabelText(/Test Model.*bottom/);
      expect(updatedElement.style.backgroundPosition).toBe('-2048px -512px');
    });

    it('returns to front (angle 0) when pressing right from vertical angle', () => {
      render(<SpriteViewer blueprint={mockBlueprint} thumbnailData={mockThumbnailData} />);

      const spriteElement = screen.getByLabelText(/Test Model/);
      spriteElement.focus();

      // Go to top view
      fireEvent.keyDown(spriteElement, { key: 'ArrowUp' });

      // Press right should go to front (angle 0)
      fireEvent.keyDown(screen.getByLabelText(/Test Model/), { key: 'ArrowRight' });

      const updatedElement = screen.getByLabelText(/Test Model.*front/);
      expect(updatedElement.style.backgroundPosition).toBe('0px 0px');
    });
  });

  describe('Mouse Drag Interaction', () => {
    it('changes angle when dragging right', () => {
      render(<SpriteViewer blueprint={mockBlueprint} thumbnailData={mockThumbnailData} />);

      const spriteElement = screen.getByLabelText(/Test Model/);

      // Start drag
      fireEvent.mouseDown(spriteElement, { clientX: 100 });

      // Drag right by 30 pixels (threshold for 1 angle change)
      fireEvent(window, new MouseEvent('mousemove', { clientX: 130, bubbles: true }));

      const updatedElement = screen.getByLabelText(/Test Model.*front-right/);
      expect(updatedElement.style.backgroundPosition).toBe('-512px 0px');

      // End drag
      fireEvent(window, new MouseEvent('mouseup', { bubbles: true }));
    });

    it('changes angle when dragging left', () => {
      render(<SpriteViewer blueprint={mockBlueprint} thumbnailData={mockThumbnailData} />);

      const spriteElement = screen.getByLabelText(/Test Model/);

      fireEvent.mouseDown(spriteElement, { clientX: 100 });

      // Drag left by 30 pixels
      fireEvent(window, new MouseEvent('mousemove', { clientX: 70, bubbles: true }));

      const updatedElement = screen.getByLabelText(/Test Model.*front-left/);
      expect(updatedElement.style.backgroundPosition).toBe('-1024px -512px');

      fireEvent(window, new MouseEvent('mouseup', { bubbles: true }));
    });

    it('wraps around when dragging right past angle 7', () => {
      const customData = { ...mockThumbnailData, default_angle: 7 };
      render(<SpriteViewer blueprint={mockBlueprint} thumbnailData={customData} />);

      const spriteElement = screen.getByLabelText(/Test Model/);

      fireEvent.mouseDown(spriteElement, { clientX: 100 });

      // Drag right by 30 pixels (one angle change from 7 -> 0)
      fireEvent(window, new MouseEvent('mousemove', { clientX: 130, bubbles: true }));

      const updatedElement = screen.getByLabelText(/Test Model.*front/);
      expect(updatedElement.style.backgroundPosition).toBe('0px 0px');

      fireEvent(window, new MouseEvent('mouseup', { bubbles: true }));
    });

    it('requires threshold distance to change angle', () => {
      render(<SpriteViewer blueprint={mockBlueprint} thumbnailData={mockThumbnailData} />);

      const spriteElement = screen.getByLabelText(/Test Model/);

      fireEvent.mouseDown(spriteElement, { clientX: 100 });

      // Drag right by only 20 pixels (less than 30px threshold)
      fireEvent(window, new MouseEvent('mousemove', { clientX: 120, bubbles: true }));

      // Should still be at front (angle 0)
      const unchangedElement = screen.getByLabelText(/Test Model.*front/);
      expect(unchangedElement.style.backgroundPosition).toBe('0px 0px');

      fireEvent(window, new MouseEvent('mouseup', { bubbles: true }));
    });

    it('cleans up event listeners after drag ends', () => {
      const removeEventListenerSpy = jest.spyOn(window, 'removeEventListener');

      render(<SpriteViewer blueprint={mockBlueprint} thumbnailData={mockThumbnailData} />);

      const spriteElement = screen.getByLabelText(/Test Model/);

      fireEvent.mouseDown(spriteElement, { clientX: 100 });
      fireEvent(window, new MouseEvent('mouseup', { bubbles: true }));

      expect(removeEventListenerSpy).toHaveBeenCalledWith('mousemove', expect.any(Function));
      expect(removeEventListenerSpy).toHaveBeenCalledWith('mouseup', expect.any(Function));

      removeEventListenerSpy.mockRestore();
    });

    it('does not initiate drag on right-click', () => {
      render(<SpriteViewer blueprint={mockBlueprint} thumbnailData={mockThumbnailData} />);

      const spriteElement = screen.getByLabelText(/Test Model/);

      // Right-click (button 2)
      fireEvent.mouseDown(spriteElement, { button: 2, clientX: 100 });

      // Try to drag
      fireEvent(window, new MouseEvent('mousemove', { clientX: 130, bubbles: true }));

      // Should still be at front (angle 0) - no drag happened
      const unchangedElement = screen.getByLabelText(/Test Model.*front/);
      expect(unchangedElement.style.backgroundPosition).toBe('0px 0px');

      fireEvent(window, new MouseEvent('mouseup', { bubbles: true }));
    });

    it('changes to top view when dragging vertically upward', () => {
      render(<SpriteViewer blueprint={mockBlueprint} thumbnailData={mockThumbnailData} />);

      const spriteElement = screen.getByLabelText(/Test Model/);

      fireEvent.mouseDown(spriteElement, { clientX: 100, clientY: 100 });

      // Drag up by more than threshold (30px)
      fireEvent(window, new MouseEvent('mousemove', { clientX: 100, clientY: 60, bubbles: true }));

      const updatedElement = screen.getByLabelText(/Test Model.*top/);
      // Angle 8: row 1, col 3 -> position: -(3 * 512)px -(1 * 512)px = -1536px -512px
      expect(updatedElement.style.backgroundPosition).toBe('-1536px -512px');

      fireEvent(window, new MouseEvent('mouseup', { bubbles: true }));
    });

    it('changes to bottom view when dragging vertically downward', () => {
      render(<SpriteViewer blueprint={mockBlueprint} thumbnailData={mockThumbnailData} />);

      const spriteElement = screen.getByLabelText(/Test Model/);

      fireEvent.mouseDown(spriteElement, { clientX: 100, clientY: 100 });

      // Drag down by more than threshold (30px)
      fireEvent(window, new MouseEvent('mousemove', { clientX: 100, clientY: 140, bubbles: true }));

      const updatedElement = screen.getByLabelText(/Test Model.*bottom/);
      // Angle 9: row 1, col 4 -> position: -(4 * 512)px -(1 * 512)px = -2048px -512px
      expect(updatedElement.style.backgroundPosition).toBe('-2048px -512px');

      fireEvent(window, new MouseEvent('mouseup', { bubbles: true }));
    });

    it('returns to front view when dragging horizontally from top view', () => {
      const customData = { ...mockThumbnailData, default_angle: 8 }; // Start at top
      render(<SpriteViewer blueprint={mockBlueprint} thumbnailData={customData} />);

      const spriteElement = screen.getByLabelText(/Test Model/);

      fireEvent.mouseDown(spriteElement, { clientX: 100, clientY: 100 });

      // Drag right by more than threshold
      fireEvent(window, new MouseEvent('mousemove', { clientX: 140, clientY: 100, bubbles: true }));

      // Should go to front (angle 0) when dragging horizontally from vertical view
      const updatedElement = screen.getByLabelText(/Test Model.*front/);
      expect(updatedElement.style.backgroundPosition).toBe('0px 0px');

      fireEvent(window, new MouseEvent('mouseup', { bubbles: true }));
    });

    it('returns to front view when dragging horizontally from bottom view', () => {
      const customData = { ...mockThumbnailData, default_angle: 9 }; // Start at bottom
      render(<SpriteViewer blueprint={mockBlueprint} thumbnailData={customData} />);

      const spriteElement = screen.getByLabelText(/Test Model/);

      fireEvent.mouseDown(spriteElement, { clientX: 100, clientY: 100 });

      // Drag left by more than threshold
      fireEvent(window, new MouseEvent('mousemove', { clientX: 60, clientY: 100, bubbles: true }));

      // Should go to front (angle 0) when dragging horizontally from vertical view
      const updatedElement = screen.getByLabelText(/Test Model.*front/);
      expect(updatedElement.style.backgroundPosition).toBe('0px 0px');

      fireEvent(window, new MouseEvent('mouseup', { bubbles: true }));
    });

    it('interprets diagonal drag as vertical when Y delta is dominant', () => {
      render(<SpriteViewer blueprint={mockBlueprint} thumbnailData={mockThumbnailData} />);

      const spriteElement = screen.getByLabelText(/Test Model/);

      fireEvent.mouseDown(spriteElement, { clientX: 100, clientY: 100 });

      // Diagonal drag: 20px right, 40px up (vertical is dominant)
      fireEvent(window, new MouseEvent('mousemove', { clientX: 120, clientY: 60, bubbles: true }));

      // Should go to top view (vertical wins)
      const updatedElement = screen.getByLabelText(/Test Model.*top/);
      expect(updatedElement.style.backgroundPosition).toBe('-1536px -512px');

      fireEvent(window, new MouseEvent('mouseup', { bubbles: true }));
    });

    it('interprets diagonal drag as horizontal when X delta is dominant', () => {
      render(<SpriteViewer blueprint={mockBlueprint} thumbnailData={mockThumbnailData} />);

      const spriteElement = screen.getByLabelText(/Test Model/);

      fireEvent.mouseDown(spriteElement, { clientX: 100, clientY: 100 });

      // Diagonal drag: 40px right, 20px down (horizontal is dominant)
      fireEvent(window, new MouseEvent('mousemove', { clientX: 140, clientY: 120, bubbles: true }));

      // Should rotate horizontally to front-right (horizontal wins)
      const updatedElement = screen.getByLabelText(/Test Model.*front-right/);
      expect(updatedElement.style.backgroundPosition).toBe('-512px 0px');

      fireEvent(window, new MouseEvent('mouseup', { bubbles: true }));
    });
  });

  describe('Accessibility', () => {
    it('has tabindex for keyboard focus', () => {
      render(<SpriteViewer blueprint={mockBlueprint} thumbnailData={mockThumbnailData} />);

      const container = screen.getByTestId('sprite-viewer-container');
      expect(container).toHaveAttribute('tabIndex', '0');
    });

    it('has descriptive aria-label with current angle', () => {
      render(<SpriteViewer blueprint={mockBlueprint} thumbnailData={mockThumbnailData} />);

      const spriteElement = screen.getByLabelText(/Test Model.*front/);
      expect(spriteElement).toHaveAttribute('aria-label');
    });

    it('updates aria-label when angle changes', () => {
      render(<SpriteViewer blueprint={mockBlueprint} thumbnailData={mockThumbnailData} />);

      const rightDot = screen.getByTitle('right');
      fireEvent.click(rightDot);

      expect(screen.getByLabelText(/Test Model.*right/)).toBeInTheDocument();
    });

    it('has title attributes on angle buttons', () => {
      render(<SpriteViewer blueprint={mockBlueprint} thumbnailData={mockThumbnailData} />);

      expect(screen.getByTitle('front')).toBeInTheDocument();
      expect(screen.getByTitle('right')).toBeInTheDocument();
      expect(screen.getByTitle('back')).toBeInTheDocument();
      expect(screen.getByTitle('left')).toBeInTheDocument();
      expect(screen.getByTitle('top')).toBeInTheDocument();
      expect(screen.getByTitle('bottom')).toBeInTheDocument();
    });
  });
});
