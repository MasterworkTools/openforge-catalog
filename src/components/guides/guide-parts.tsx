'use client';

import React, { useCallback, useRef, useState } from 'react';
import {
  GuidePart,
  GuideRefinement,
  impliedBy,
  pinKey,
} from '@/services/guide-service';
import { stepView, useDragRotation } from '@/hooks/use-drag-rotation';
import { ConfigTags } from '@/types';
import { downloadFiles, downloadUrl } from '@/utils/blueprint-utils';
import PartSelectionModal from '../part-selection-modal';
import { GuideSprite } from './guide-sprite';
import { SpriteControls } from '../sprite-controls';

interface GuidePartsProps {
  parts: GuidePart[];
  /**
   * The questions, so that picking a part by hand can bring the ones
   * it answers into line with what was picked.
   */
  refinements?: GuideRefinement[];
  /**
   * How many pieces each role could have been, when it is known.
   * Arrives with availability, a moment after the parts.
   */
  options?: Record<string, number> | null;
  /** Same setter the questions use: a pin is a selection like any other. */
  onSelect?: (key: string, value: string | null) => void;
  /**
   * Several answers at once. Picking a part settles the pin and the
   * questions that part answers, and those have to be one write — the
   * URL is the state, and two writes would lose the first.
   */
  onSelectAll?: (changes: Record<string, string | null>) => void;
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
 * Drag anywhere in the list to turn them, and they all turn together
 * for the same reason — a list where one piece faced a different way
 * would be answering a different question. The angle is shared by
 * name, so sheets that order their frames differently still line up.
 *
 * Every piece shows its tags. A guide recommending the wrong thing is
 * far easier to diagnose from the tags than from the filename, and
 * while the guides are being written that is most of what this page is
 * for.
 */
export function GuideParts({
  parts,
  refinements = [],
  options,
  onSelect,
  onSelectAll,
}: GuidePartsProps) {
  const [inspecting, setInspecting] = useState<GuidePart | null>(null);
  const [view, setView] = useState<string>('front');
  // Where the drag began, so each move is measured from there rather
  // than accumulating rounding as the pointer travels.
  const viewAtStart = useRef(view);
  // Whether this gesture turned anything. The picture is also a button
  // that opens the tag search, and letting go after a drag must not
  // count as a click on it.
  const turned = useRef(false);

  const onStart = useCallback(() => {
    viewAtStart.current = view;
    turned.current = false;
  }, [view]);
  const onHorizontal = useCallback((steps: number) => {
    if (steps !== 0) turned.current = true;
    setView(stepView(viewAtStart.current, steps));
  }, []);
  const onVertical = useCallback((face: 'top' | 'bottom') => {
    turned.current = true;
    setView(face);
  }, []);
  const { handleMouseDown, isDragging } = useDragRotation({
    onStart,
    onHorizontal,
    onVertical,
  });

  const swallowDragClick = useCallback((e: React.MouseEvent) => {
    if (!turned.current) return;
    e.stopPropagation();
    e.preventDefault();
    turned.current = false;
  }, []);

  const urls = parts.flatMap((part) =>
    part.blueprint ? [downloadUrl(part.blueprint.id)] : []
  );
  if (parts.length === 0) return null;

  return (
    <section className="guide-parts mb-8">
      <h2 className="text-xl font-bold mb-3">What to print</h2>
      {/* Pieces and controls side by side, and stacked when there is
          not room for both — `flex-wrap` rather than a breakpoint,
          because what matters is whether *this column* is wide enough
          and the column's width depends on the window, the questions
          beside it and how many pieces the build has. */}
      <div className="flex flex-wrap items-start gap-6">
        {/* The whole list is the handle, not each picture: you are
            turning the build, not a piece of it. */}
        <div
          onMouseDown={handleMouseDown}
          onClickCapture={swallowDragClick}
          className={`flex flex-wrap gap-6 items-start select-none ${
            isDragging ? 'cursor-grabbing' : 'cursor-grab'
          }`}
        >
          {stacks(parts).map((stack) => (
            <div key={stack[0].role} className="flex flex-col gap-1">
              {stack.map((part) => (
                <Part
                  key={part.role}
                  part={part}
                  view={view}
                  options={options?.[part.role]}
                  onInspect={setInspecting}
                  onUnpin={
                    onSelect ? () => onSelect(pinKey(part.role), null) : undefined
                  }
                />
              ))}
            </div>
          ))}
        </div>
        {/* The widget is here to be seen as much as used: dragging is
            not discoverable, and a flattened cube offering "front,
            left, top" says the pictures turn without anyone reading a
            line of help text. */}
        <div className="flex flex-col gap-3">
          <SpriteControls view={view} onView={setView} />
          <p className="text-xs text-gray-500 max-w-[10rem]">
            Pick a side, or drag the pieces. They all turn together.
          </p>
          {urls.length > 0 && (
            <button
              type="button"
              className="border border-gray-300 rounded px-3 py-2 text-sm"
              onClick={() => downloadFiles(urls)}
            >
              Download{' '}
              {urls.length === 1 ? 'the file' : `all ${urls.length} files`}
            </button>
          )}
        </div>
      </div>
      <PartSelectionModal
        isOpen={inspecting !== null}
        onClose={() => setInspecting(null)}
        partName={inspecting ? `${inspecting.title} (${inspecting.role})` : ''}
        // What the guide actually resolved, not a wider set. Opening
        // on your own wall is the useful place to start looking for
        // another one — and the restrictions that are only a
        // preference come off from inside, a chip at a time.
        configValues={inspecting ? asConfigTags(inspecting.query) : null}
        removable={inspecting?.relaxable ?? []}
        // Open on the piece that was clicked. You were looking at it;
        // the dialog should not make you find it again.
        initialMd5={inspecting?.blueprint?.file_md5 ?? null}
        onPartSelected={
          onSelectAll && inspecting
            ? (_name, blueprint) => {
                onSelectAll({
                  [pinKey(inspecting.role)]: blueprint.file_md5,
                  // What was picked is now the answer to the questions
                  // it answers, or the page would show a rough stone
                  // wall beside the word "dungeon stone".
                  ...impliedBy(blueprint, inspecting.role, refinements),
                });
                setInspecting(null);
              }
            : undefined
        }
      />
    </section>
  );
}

/**
 * A role's predicate, in the shape the part-selection modal seeds its
 * tag search from.
 *
 * Every term the search can act on — four of the five. `accept` is
 * the exception and the body says why. The tag tree can only add and
 * remove exact tags, so a sweep stays as it arrived while you explore
 * around it, which is the right way round: the sweep is what keeps
 * the arrow slits and the curved corners out, and those are their own
 * builds rather than alternatives to this one.
 */
function asConfigTags(query: GuidePart['query']): ConfigTags {
  const tags = (names?: string[]) => (names ?? []).map((tag) => ({ tag }));
  // `accept` is deliberately not passed. The tag search has no subtree
  // predicate — `processConfigValues` reads require, deny,
  // deny_children and allow, and drops anything else — so sending it
  // would seed the modal wider than intended. No guide uses `accept`
  // yet; the day one does, the search needs the predicate before this
  // line changes.
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
  view,
  options,
  onInspect,
  onUnpin,
}: {
  part: GuidePart;
  view: string;
  /** How many pieces this role could have been, when it is known. */
  options?: number;
  onInspect: (part: GuidePart) => void;
  /** Undoes a pin, putting the role back on the guide's own answer. */
  onUnpin?: () => void;
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
        <GuideSprite blueprint={part.blueprint} view={view} />
      </button>
      <div className="mt-2 flex items-baseline justify-between gap-2">
        <span className="font-semibold">{part.title}</span>
        {/* Only when there is a choice to make. One piece behind the
            answer is the guide having decided; six is towne having
            six kinds of wall and nothing on the page saying so. */}
        {options !== undefined && options > 1 && (
          <button
            type="button"
            onClick={() => onInspect(part)}
            className="text-xs text-blue-700 underline shrink-0"
          >
            {options} options
          </button>
        )}
      </div>
      {/* A pinned part is no longer an answer to the questions on the
          left, and saying so is the only way the page can explain why
          changing a texture leaves this piece alone. */}
      {part.pinned && (
        <div className="text-xs text-blue-700 flex items-center gap-2">
          <span>You picked this part</span>
          {onUnpin && (
            <button type="button" onClick={onUnpin} className="underline">
              undo
            </button>
          )}
        </div>
      )}
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
