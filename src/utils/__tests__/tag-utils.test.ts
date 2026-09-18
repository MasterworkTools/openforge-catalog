import { tagToArray, arrayToTag, convertTagDict, getOtherBlueprintTags } from '../tag-utils';
import { Blueprint } from '@/types';

describe('tagToArray', () => {
  it('splits a pipe-delimited string', () => {
    expect(tagToArray('foo|bar')).toEqual(['foo', 'bar']);
  });
  it('returns the array unchanged', () => {
    expect(tagToArray(['foo', 'bar'])).toEqual(['foo', 'bar']);
  });
});

describe('arrayToTag', () => {
  it('joins an array into a pipe-delimited string', () => {
    expect(arrayToTag(['foo', 'bar'])).toBe('foo|bar');
  });
  it('handles a single-element array', () => {
    expect(arrayToTag(['foo'])).toBe('foo');
  });
  it('handles an empty array', () => {
    expect(arrayToTag([])).toBe('');
  });
});

describe('convertTagDict', () => {
  it('converts tag array to pipe-delimited string in dict', () => {
    expect(convertTagDict({ tag: ['foo', 'bar'] })).toEqual({ tag: 'foo|bar' });
  });
  it('handles empty tag array', () => {
    expect(convertTagDict({ tag: [] })).toEqual({ tag: '' });
  });
});

describe('getOtherBlueprintTags', () => {
  const mockBlueprint1: Blueprint = {
    id: '1',
    blueprint_name: 'Test Blueprint 1',
    blueprint_type: 'test',
    tags: ['shape|round', 'size|large', 'texture|smooth'],
    file_name: 'test1.stl',
    file_size: 1000,
    file_md5: 'abc123',
    file_modified_at: '2023-01-01T00:00:00Z',
    full_name: 'Test Blueprint 1',
    created_at: '2023-01-01T00:00:00Z',
    updated_at: '2023-01-01T00:00:00Z',
    signed_url: 'http://example.com/test1.stl',
    storage_address: 'test1.stl',
    images: []
  };

  const mockBlueprint2: Blueprint = {
    id: '2',
    blueprint_name: 'Test Blueprint 2',
    blueprint_type: 'test',
    tags: ['shape|square', 'size|small'],
    file_name: 'test2.stl',
    file_size: 1000,
    file_md5: 'def456',
    file_modified_at: '2023-01-01T00:00:00Z',
    full_name: 'Test Blueprint 2',
    created_at: '2023-01-01T00:00:00Z',
    updated_at: '2023-01-01T00:00:00Z',
    signed_url: 'http://example.com/test2.stl',
    storage_address: 'test2.stl',
    images: []
  };

  const mockParentBlueprint: Blueprint = {
    id: 'parent',
    blueprint_name: 'Parent Blueprint',
    blueprint_type: 'test',
    tags: ['parent|tag1', 'parent|tag2'],
    file_name: 'parent.stl',
    file_size: 1000,
    file_md5: 'parent123',
    file_modified_at: '2023-01-01T00:00:00Z',
    full_name: 'Parent Blueprint',
    created_at: '2023-01-01T00:00:00Z',
    updated_at: '2023-01-01T00:00:00Z',
    signed_url: 'http://example.com/parent.stl',
    storage_address: 'parent.stl',
    images: []
  };

  it('returns tags from other selected parts only', () => {
    const configSelections = {
      'part1': mockBlueprint1,
      'part2': mockBlueprint2
    };

    const result = getOtherBlueprintTags(configSelections, 'part1');

    expect(result).toEqual({
      parentTags: [],
      siblingSelections: [
        { partName: 'part2', tags: ['shape|square', 'size|small'] }
      ]
    });
  });

  it('excludes tags from the current part', () => {
    const configSelections = {
      'part1': mockBlueprint1,
      'part2': mockBlueprint2
    };

    const result = getOtherBlueprintTags(configSelections, 'part2');

    expect(result).toEqual({
      parentTags: [],
      siblingSelections: [
        { partName: 'part1', tags: ['shape|round', 'size|large', 'texture|smooth'] }
      ]
    });
  });

  it('includes tags from parent blueprint when provided', () => {
    const configSelections = {
      'part1': mockBlueprint1
    };

    const result = getOtherBlueprintTags(configSelections, 'part1', mockParentBlueprint);

    expect(result).toEqual({
      parentTags: ['parent|tag1', 'parent|tag2'],
      siblingSelections: []
    });
  });

  it('combines tags from other parts and parent blueprint', () => {
    const configSelections = {
      'part1': mockBlueprint1,
      'part2': mockBlueprint2
    };

    const result = getOtherBlueprintTags(configSelections, 'part1', mockParentBlueprint);

    expect(result).toEqual({
      parentTags: ['parent|tag1', 'parent|tag2'],
      siblingSelections: [
        { partName: 'part2', tags: ['shape|square', 'size|small'] }
      ]
    });
  });

  it('returns empty set when no other parts or parent', () => {
    const configSelections = {};

    const result = getOtherBlueprintTags(configSelections, 'part1');

    expect(result).toEqual({
      parentTags: [],
      siblingSelections: []
    });
  });
});
