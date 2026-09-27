import React from 'react';
import { render, screen } from '@testing-library/react';
import { GuideSprite } from '../guide-sprite';
import type { GuideBlueprint, SpriteAngle } from '@/services/guide-service';

/**
 * A sheet is either a still at a named angle or, when that angle was
 * never generated, a fallback that has to say so. These cover the
 * saying-so, because the picture itself is a background-position and
 * the label is the only thing a reader gets.
 */
function sheet(angles: SpriteAngle[]): GuideBlueprint {
  return {
    id: 'bp1',
    blueprint_name: 'rough stone wall',
    file_md5: 'a'.repeat(32),
    storage_address: null,
    images: [
      {
        id: 'img1',
        image_name: 'sheet.png',
        image_url: '/sheet.png',
        image_type: 'thumbnail',
        sprite_metadata: {
          grid_rows: 2,
          grid_cols: 5,
          tile_size: 240,
          angles,
          default_angle: 0,
        },
      },
    ],
  };
}

const FRONT: SpriteAngle = { index: 0, name: 'front' };
const LEFT: SpriteAngle = { index: 6, name: 'left' };

describe('GuideSprite', () => {
  let warn: jest.SpyInstance;

  beforeEach(() => {
    warn = jest.spyOn(console, 'warn').mockImplementation(() => {});
  });

  afterEach(() => warn.mockRestore());

  it('labels the angle it was asked for when the sheet has it', () => {
    render(<GuideSprite blueprint={sheet([FRONT, LEFT])} view="left" />);
    expect(
      screen.getByLabelText('rough stone wall, seen from the left')
    ).toBeInTheDocument();
    expect(warn).not.toHaveBeenCalled();
  });

  it('says out loud which angle is missing rather than only in the label', () => {
    // A sheet generated before the left view existed. The picture
    // falls back to the default frame, so without the warning the only
    // sign is an aria-label nobody is reading.
    render(<GuideSprite blueprint={sheet([FRONT])} view="left" />);
    expect(
      screen.getByLabelText('rough stone wall, seen from the front')
    ).toBeInTheDocument();
    expect(warn).toHaveBeenCalledWith(
      'sprite for %s has no %s angle',
      'rough stone wall',
      'left'
    );
  });

  it('stays quiet for a plain thumbnail, which has no angles to miss', () => {
    render(
      <GuideSprite
        blueprint={{
          id: 'bp2',
          blueprint_name: 'a picture',
          file_md5: null,
          storage_address: null,
          images: [
            {
              id: 'img2',
              image_name: 'thumb.png',
              image_url: '/thumb.png',
              image_type: 'thumbnail',
            },
          ],
        }}
        view="left"
      />
    );
    expect(screen.getByAltText('a picture')).toBeInTheDocument();
    expect(warn).not.toHaveBeenCalled();
  });
});
