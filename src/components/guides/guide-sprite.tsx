'use client';

import React from 'react';
import { GuideBlueprint, thumbnailOf } from '@/services/guide-service';

/**
 * One frame of a blueprint's sprite sheet, at a fixed angle.
 *
 * The sprite viewer on a blueprint's own page is interactive — drag to
 * rotate, arrow keys, an unwrapped cube. That is the right thing when
 * you are looking at one piece. Here there are up to four pieces side
 * by side and the question is whether they go together, which only
 * works if they are all drawn from the same direction. So this is a
 * still, and the angle is chosen by name rather than by index: the
 * index of "front" is not the same in every sheet.
 */

const VIEW = 'front';

export function GuideSprite({
  blueprint,
  size = 240,
}: {
  blueprint: GuideBlueprint | null;
  size?: number;
}) {
  const image = thumbnailOf(blueprint);
  const sprite = image?.sprite_metadata;

  if (!image) {
    return (
      <div
        className="flex items-center justify-center rounded bg-gray-100 text-xs text-gray-500"
        style={{ width: size, height: size }}
      >
        no picture
      </div>
    );
  }

  // A thumbnail that is not a sprite sheet is just a picture.
  if (!sprite) {
    return (
      <img
        src={image.image_url}
        alt={blueprint?.blueprint_name ?? ''}
        className="object-contain rounded"
        style={{ width: size, height: size }}
      />
    );
  }

  const index =
    sprite.angles?.find((angle) => angle.name === VIEW)?.index ??
    sprite.default_angle ??
    0;
  const row = Math.floor(index / sprite.grid_cols);
  const col = index % sprite.grid_cols;

  return (
    <div
      role="img"
      aria-label={`${blueprint?.blueprint_name ?? 'part'}, seen from the ${VIEW}`}
      className="rounded"
      style={{
        width: size,
        height: size,
        backgroundImage: `url(${image.image_url})`,
        // The sheet is drawn at `size` per tile rather than its native
        // tile_size, so the whole sheet scales with it.
        backgroundSize: `${sprite.grid_cols * size}px ${sprite.grid_rows * size}px`,
        backgroundPosition: `-${col * size}px -${row * size}px`,
        backgroundRepeat: 'no-repeat',
      }}
    />
  );
}
