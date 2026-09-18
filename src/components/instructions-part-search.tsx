'use client'

import React from 'react';
import { useTagContext } from '@/contexts/tag-context';
import TagRow from './ui/tag-row';

export function InstructionsPartSearch() {
  const addTag = useTagContext((state) => state.addTag);
  const removeTag = useTagContext((state) => state.removeTag);
  const selectedTags = useTagContext((state) => state.selectedTags);
  const tagDescriptions = useTagContext((state) => state.tagDescriptions);

  const addExampleTag = (tag: string) => {
    const section = tag.split('|')[0];
    const sectionTags = selectedTags.filter((t: string) => t.startsWith(section + '|'));
    sectionTags.forEach((t: string) => removeTag(t));
    addTag(tag);
  };

  // Helper to render h2 + description + tag row
  const Section = ({ title, tags, tooltipAbove }: { title: string, tags?: string[], tooltipAbove?: boolean }) => (
    <>
      <h2 className="text-2xl font-bold mt-8 mb-4">{title}</h2>
      {tagDescriptions[title.toLowerCase()] && (
        <p className="mb-6">{tagDescriptions[title.toLowerCase()]}</p>
      )}
      {tags && tags.length > 0 && (
        <>
          <p className="mb-4"><strong>Example Tags:</strong></p>
          <div className="mb-8">
            <TagRow tags={tags} onTagClick={addExampleTag} tooltipAbove={tooltipAbove} />
          </div>
        </>
      )}
    </>
  );

  return (
    <div className="part-search-instructions p-6 max-w-3xl">
      <h1 className="text-3xl font-bold mb-6">Instructions (Part Search)</h1>
      <p className="mb-6">
        The main interface for this is designed for you to select tags that help you refine your search.
        You can select tags in the tree on the left. The tags are broken into some broad categories.
        If you want to instead build full tiles, and select all the parts needed to make that tile, click on the Blueprints tab
        above.
      </p>

      {Section({ title: 'Build', tags: [
        'build|separate wall',
        'build|wall on tile',
        'build|s2w',
        'build|s-system',
        'build|thick wall',
      ] })}
      {Section({ title: 'Component', tags: [
        'component|arrow_slit',
        'component|door|arched',
        'component|drain',
        'component|portcullis',
        'component|wall',
        'component|window',
      ] })}
      {Section({ title: 'Connection', tags: [
        'connection|dragonlock',
        'connection|openlock',
        'connection|openforge',
        'connection|magnetic|flex',
        'connection|side',
        'connection|pegs',
        'connection|openlock|topless',
      ] })}
      {Section({ title: 'Decoration', tags: [
        'decoration|air',
        'decoration|earth',
        'decoration|fire',
        'decoration|water',
        'decoration|demon',
        'decoration|celtic_knot',
      ] })}
      {Section({ title: 'Interface' })}
      {Section({ title: 'Part' })}
      {Section({ title: 'Scatter' })}
      {Section({ title: 'Shape' })}
      {Section({ title: 'Size' })}
      {Section({ title: 'Texture', tags: [
        'texture|dungeon_stone',
        'texture|cut-stone',
        'texture|towne',
        'texture|sewer',
        'texture|cave',
      ], tooltipAbove: true })}
    </div>
  );
}

export default InstructionsPartSearch;
