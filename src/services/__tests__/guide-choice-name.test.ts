import { nameFor } from '@/services/guide-service';

/**
 * A curated answer carries a title; a derived one carries only its
 * tag. Both are headed by the same name, so the explainer's cards and
 * the picker's buttons agree and neither shows a raw tag.
 */
describe('nameFor', () => {
  it('keeps a curated title as written', () => {
    expect(nameFor({ tag: 'texture|towne', title: 'Wood' })).toBe('Wood');
  });

  it('names a derived answer after the last element of its tag', () => {
    expect(nameFor({ tag: 'texture|cave' })).toBe('Cave');
  });

  it('takes the underscores out', () => {
    expect(nameFor({ tag: 'texture|dungeon_stone' })).toBe('Dungeon stone');
    expect(nameFor({ tag: 'texture|cracked_ice' })).toBe('Cracked ice');
  });

  it('leaves a count out of the name, which belongs to the picker', () => {
    expect(nameFor({ tag: 'texture|sewer', count: 16 })).toBe('Sewer');
  });

  it('falls back to the whole tag when there is no last element', () => {
    expect(nameFor({ tag: 'texture' })).toBe('Texture');
  });
});
