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
          // Deliberately not 240: the sheet is drawn at `SIZE` per
          // tile, not at its native `tile_size`, and with the two equal
          // the assertion below could not tell which one was used.
          tile_size: 120,
          angles,
          default_angle: 0,
        },
      },
    ],
  };
}

const FRONT: SpriteAngle = { index: 0, name: 'front' };
// Index 7, not 6: 6 of a 5-wide sheet is row 1 *and* column 1, so a
// transposed backgroundPosition would have looked correct.
const LEFT: SpriteAngle = { index: 7, name: 'left' };

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

  it('draws the frame at that angle, on the right row of the sheet', () => {
    // The label is not the picture. `LEFT` is index 6 of a 5-wide
    // sheet, so it is the second row — and every sheet in the catalog
    // is two rows, which means `row = 0` or `col = index` would draw
    // the wrong half of the ring while the label went on being right.
    render(<GuideSprite blueprint={sheet([FRONT, LEFT])} view="left" />);
    const drawn = screen.getByLabelText('rough stone wall, seen from the left');
    // index 7, grid_cols 5 -> row 1, col 2, at SIZE = 240 per tile.
    // Row and column differ, so swapping them fails.
    expect(drawn).toHaveStyle({ backgroundPosition: '-480px -240px' });
    // And the whole sheet is scaled to SIZE per tile, not to the
    // sheet's own tile_size (120 here), or the offsets land between
    // frames.
    expect(drawn).toHaveStyle({ backgroundSize: '1200px 480px' });
  });

  it('names the frame it actually drew when it cannot name the angle', () => {
    // The sheet has a frame at the default index but no entry naming
    // it, so there is no side to report. Saying `view` here would tell
    // a reader "left" over a picture of something else, which is the
    // one thing the label must not do.
    const bp = sheet([{ index: 3, name: 'back' }]);
    bp.images![0].sprite_metadata!.default_angle = 9;
    render(<GuideSprite blueprint={bp} view="left" />);
    expect(
      screen.getByLabelText('rough stone wall, seen from the default angle')
    ).toBeInTheDocument();
  });

  it('says it once per sheet and angle, not once per render', () => {
    // Why the warning is in an effect rather than the render body. A
    // re-render with the same sheet and angle is the same gap, already
    // reported; in the render body each one said it again.
    const bp = sheet([FRONT]);
    const { rerender } = render(<GuideSprite blueprint={bp} view="left" />);
    rerender(<GuideSprite blueprint={bp} view="left" />);
    rerender(<GuideSprite blueprint={bp} view="left" />);
    expect(warn).toHaveBeenCalledTimes(1);

    // A different missing angle on the same sheet is a different gap.
    rerender(<GuideSprite blueprint={bp} view="back" />);
    expect(warn).toHaveBeenCalledTimes(2);
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
