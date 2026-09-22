'use client';

import React, { useState } from 'react';
import { GuidePart } from '@/services/guide-service';
import { ConfigTags } from '@/types';
import { downloadFiles, downloadUrl } from '@/utils/blueprint-utils';
import PartSelectionModal from '../part-selection-modal';
import { GuideSprite } from './guide-sprite';

interface GuidePartsProps {
  parts: GuidePart[];
}

/**
 * The answer: the pieces to print, stacked the way they stack.
 *
 * A base sits under the piece it carries, so it is drawn under it —
 * `under` says which. Everything is drawn from the same angle, because
 * the question a parts list has to answer at a glance is whether these
 * pieces go together, and you cannot see that if each one is turned a
 * different way.
 *
 * Every piece shows its tags. A guide recommending the wrong thing is
 * far easier to diagnose from the tags than from the filename, and
 * while the guides are being written that is most of what this page is
 * for.
 */
export function GuideParts({ parts }: GuidePartsProps) {
  const [inspecting, setInspecting] = useState<GuidePart | null>(null);
  const urls = parts.flatMap((part) =>
    part.blueprint ? [downloadUrl(part.blueprint.id)] : []
  );
  if (parts.length === 0) return null;

  return (
    <section className="guide-parts mb-8">
      <h2 className="text-xl font-bold mb-3">What to print</h2>
      <div className="flex flex-wrap gap-6 items-start">
        {stacks(parts).map((stack) => (
          <div key={stack[0].role} className="flex flex-col gap-1">
            {stack.map((part) => (
              <Part key={part.role} part={part} onInspect={setInspecting} />
            ))}
          </div>
        ))}
      </div>
      {urls.length > 0 && (
        <button
          type="button"
          className="mt-4 border border-gray-300 rounded px-3 py-2"
          onClick={() => downloadFiles(urls)}
        >
          Download {urls.length === 1 ? 'the file' : `all ${urls.length} files`}
        </button>
      )}
      <PartSelectionModal
        isOpen={inspecting !== null}
        onClose={() => setInspecting(null)}
        partName={inspecting ? `${inspecting.title} (${inspecting.role})` : ''}
        configValues={inspecting ? asConfigTags(inspecting.query) : null}
      />
    </section>
  );
}

/**
 * A resolved role's predicate, in the shape the part-selection modal
 * seeds its tag search from.
 *
 * Every term the search can act on — four of the five — so the modal
 * opens on exactly the set the guide resolved against rather than a
 * wider one. `accept` is the exception and the body says why. The tag
 * tree can only add and remove exact tags, so the sweep stays as the
 * guide left it while you explore around it — which is the right way
 * round for finding a restriction that is missing.
 */
function asConfigTags(query: GuidePart['query']): ConfigTags {
  const tags = (names?: string[]) => (names ?? []).map((tag) => ({ tag }));
  // `accept` is deliberately not passed. The tag search has no subtree
  // predicate — `processConfigValues` reads require, deny,
  // deny_children and allow, and drops anything else — so sending it
  // would seed the modal with a set *wider* than the one that narrowed
  // the part, which is the opposite of what this is for. No guide uses
  // `accept` yet; the day one does, the search needs the predicate
  // before this line changes.
  return {
    require: tags(query.require),
    deny: tags(query.deny),
    deny_children: tags(query.deny_children),
    allow: tags(query.allow),
  };
}

/**
 * Parts grouped into the piles they physically make.
 *
 * A part with `under: floor` belongs beneath the floor, so it joins
 * that pile rather than starting its own. Order within a pile is
 * top-down, which is the order they are drawn in. A part whose `under`
 * names a role not in this list stands on its own rather than
 * disappearing.
 */
function stacks(parts: GuidePart[]): GuidePart[][] {
  const byRole = new Map(parts.map((part) => [part.role, part]));
  const piles = new Map<string, GuidePart[]>();

  for (const part of parts) {
    const top = part.under && byRole.has(part.under) ? part.under : part.role;
    if (!piles.has(top)) piles.set(top, [byRole.get(top)!]);
    if (top !== part.role) piles.get(top)!.push(part);
  }
  return [...piles.values()];
}

function Part({
  part,
  onInspect,
}: {
  part: GuidePart;
  onInspect: (part: GuidePart) => void;
}) {
  return (
    <div className="border border-gray-300 rounded p-3 w-64">
      {/* The picture is the handle: clicking it opens the catalog's own
          tag search, seeded with what narrowed this role down. While
          the guides are being written, "why did it pick that?" is the
          question being asked over and over. */}
      <button
        type="button"
        onClick={() => onInspect(part)}
        title="Open the tag search for this part"
        className="block cursor-zoom-in"
      >
        <GuideSprite blueprint={part.blueprint} />
      </button>
      <div className="mt-2 font-semibold">{part.title}</div>
      {part.blueprint ? (
        <>
          <a
            href={downloadUrl(part.blueprint.id)}
            className="text-blue-700 underline break-all text-xs block"
          >
            {part.blueprint.blueprint_name}
          </a>
          <TagList tags={part.blueprint.tags ?? []} />
        </>
      ) : (
        <span className="text-xs">
          Nothing in the catalog matches this combination yet.
        </span>
      )}
    </div>
  );
}

function TagList({ tags }: { tags: string[] }) {
  if (tags.length === 0) return null;
  return (
    <ul className="mt-2 flex flex-wrap gap-1">
      {tags.map((tag) => (
        <li
          key={tag}
          className="bg-gray-100 rounded px-1 text-[10px] font-mono break-all"
        >
          {tag}
        </li>
      ))}
    </ul>
  );
}
