'use client';

import React from 'react';
import {
  GuideChoice,
  GuideRefinement,
  GuideStep,
} from '@/services/guide-service';

/**
 * The questions. A step is a set of options, one of which is chosen; a
 * refinement is either a toggle or a tag picked from a namespace.
 * Answering either one re-resolves the parts.
 */

/**
 * Which answers are dead, keyed by question.
 *
 * Arrives separately from the resolution and a moment later, because
 * working it out costs several times what the parts cost. Null until
 * it lands, and null means "nothing known to be dead" rather than
 * "nothing is" — so every answer stays clickable in the meantime and
 * the worst case is the honest "nothing matches" on the part itself.
 */
export type Unavailable = Record<string, string[]> | null;

interface GuideStepsProps {
  steps: GuideStep[];
  unavailable?: Unavailable;
  /**
   * Which answered question has been reopened, if any.
   *
   * Lifted out of the section that owns it because the column beside
   * it has to know as well: reopening a question puts its explanation
   * back, and a section keeping that to itself could not say so.
   */
  opened?: string | null;
  onOpenChange?: (key: string | null) => void;
  onSelect: (key: string, value: string | null) => void;
}

export function GuideSteps({
  steps,
  unavailable,
  opened,
  onOpenChange,
  onSelect,
}: GuideStepsProps) {
  return (
    <div className="guide-steps">
      {steps.map((step) => {
        const dead = unavailable?.[step.key] ?? step.unavailable ?? [];
        return step.selected === null ? (
          <OpenStep
            key={step.key}
            step={step}
            dead={dead}
            onSelect={onSelect}
          />
        ) : (
          <AnsweredStep
            key={step.key}
            step={step}
            dead={dead}
            open={opened === step.key}
            onOpenChange={onOpenChange}
            onSelect={onSelect}
          />
        );
      })}
    </div>
  );
}

/**
 * A question still being asked: every answer, laid out to be read.
 */
function OpenStep({
  step,
  dead,
  onSelect,
}: {
  step: GuideStep;
  dead: string[];
  onSelect: (key: string, value: string | null) => void;
}) {
  return (
    <section className="mb-8">
      <h2 id={`step-${step.key}`} className="text-xl font-bold mb-3">
        {step.prompt}
      </h2>
      {/* Tied to the heading so a screen reader announces which
          question these buttons answer. */}
      <div
        role="group"
        aria-labelledby={`step-${step.key}`}
        className="flex flex-col gap-2"
      >
        {step.options.map((option) => (
          <Answer
            key={option.key}
            label={option.title}
            chosen={false}
            dead={dead.includes(option.key)}
            onPick={() => onSelect(step.key, option.key)}
          />
        ))}
      </div>
    </section>
  );
}

/**
 * A question already answered, collapsed to one line.
 *
 * The wizard is a column of questions and it grows as you go, so a
 * question that is settled keeps only what it settled. Clicking it
 * reopens it — the answer is the control, which is why it is a button
 * rather than a heading with an edit link beside it.
 */
function AnsweredStep({
  step,
  dead,
  open,
  onOpenChange,
  onSelect,
}: {
  step: GuideStep;
  dead: string[];
  open: boolean;
  onOpenChange?: (key: string | null) => void;
  onSelect: (key: string, value: string | null) => void;
}) {
  const chosen = step.options.find((option) => option.key === step.selected);

  if (open) {
    return (
      <section className="mb-8">
        <h2 id={`step-${step.key}`} className="text-xl font-bold mb-3">
          {step.prompt}
        </h2>
        <div
          role="group"
          aria-labelledby={`step-${step.key}`}
          className="flex flex-col gap-2"
        >
          {step.options.map((option) => (
            <Answer
              key={option.key}
              label={option.title}
              chosen={step.selected === option.key}
              dead={dead.includes(option.key)}
              onPick={() => {
                onOpenChange?.(null);
                // Re-picking the current answer would rewrite the same
                // URL and re-resolve it for no change.
                if (step.selected !== option.key) {
                  onSelect(step.key, option.key);
                }
              }}
            />
          ))}
        </div>
      </section>
    );
  }

  return (
    <section className="mb-3">
      <button
        type="button"
        onClick={() => onOpenChange?.(step.key)}
        aria-expanded={false}
        className="w-full text-left rounded border border-gray-200 px-3 py-2 hover:border-gray-400"
      >
        <span className="block text-xs uppercase tracking-wide text-gray-500">
          {step.prompt}
        </span>
        <span className="block font-semibold">
          {chosen?.title ?? step.selected}
        </span>
      </button>
    </section>
  );
}

/**
 * One answer to one question, whatever kind of question it is.
 *
 * `dead` means the catalog has nothing for it given everything else
 * chosen. Greyed and still focusable rather than removed: "pegs, but
 * not in this texture" is a fact worth seeing, and a list that
 * reshuffles itself as you change your mind is hard to use.
 */
function Answer({
  label,
  hint,
  chosen,
  dead,
  onPick,
}: {
  label: string;
  /** What this answer is, when the catalog has something to say. */
  hint?: string;
  chosen: boolean;
  dead: boolean;
  onPick: () => void;
}) {
  return (
    <button
      type="button"
      aria-pressed={chosen}
      disabled={dead && !chosen}
      title={
        dead
          ? 'Nothing in the catalog matches this with your other choices'
          : hint
      }
      onClick={onPick}
      className={`border rounded p-3 text-left ${
        chosen
          ? 'border-blue-600 bg-blue-50 font-semibold'
          : dead
            ? 'border-gray-200 text-gray-400 bg-gray-50 cursor-not-allowed'
            : 'border-gray-300'
      }`}
    >
      {label}
    </button>
  );
}

interface GuideRefinementsProps {
  refinements: GuideRefinement[];
  unavailable?: Unavailable;
  onSelect: (key: string, value: string | null) => void;
}

export function GuideRefinements({
  refinements,
  unavailable,
  onSelect,
}: GuideRefinementsProps) {
  const deadFor = (refinement: GuideRefinement) =>
    unavailable?.[refinement.key] ?? refinement.unavailable ?? [];
  if (refinements.length === 0) return null;
  // A section each, in document order. A question is its own section
  // headed by its own prompt — "Change anything" over the lot of them
  // said nothing and made four unrelated questions look like one.
  //
  // A `group` joins several into one section under a shared heading,
  // for the ones that really are a single decision: which clip the
  // bases use, and then its variants.
  const sections: { name: string; grouped: boolean; of: GuideRefinement[] }[] =
    [];
  for (const refinement of refinements) {
    const last = sections[sections.length - 1];
    if (refinement.group && last?.grouped && last.name === refinement.group) {
      last.of.push(refinement);
      continue;
    }
    sections.push({
      name: refinement.group ?? refinement.prompt,
      grouped: Boolean(refinement.group),
      of: [refinement],
    });
  }
  return (
    <>
      {sections.map((section) => (
        <RefinementGroup
          key={section.name}
          name={section.name}
          // A lone question's prompt is already the heading, so
          // repeating it inside would ask it twice.
          showPrompts={section.grouped}
          refinements={section.of}
          deadFor={deadFor}
          onSelect={onSelect}
        />
      ))}
    </>
  );
}

function RefinementGroup({
  name,
  showPrompts,
  refinements,
  deadFor,
  onSelect,
}: {
  name: string;
  showPrompts: boolean;
  refinements: GuideRefinement[];
  deadFor: (refinement: GuideRefinement) => string[];
  onSelect: (key: string, value: string | null) => void;
}) {
  const headingId = `refinements-${name.replace(/\W+/g, '-').toLowerCase()}`;
  return (
    <section className="guide-refinements mb-8">
      <h2 id={headingId} className="text-xl font-bold mb-3">
        {name}
      </h2>
      <div className="flex flex-col gap-3">
        {refinements.map((refinement) => {
          if (refinement.on_tags) {
            return (
              <Toggle
                key={refinement.key}
                refinement={refinement}
                showPrompt={showPrompts}
                dead={deadFor(refinement)}
                onSelect={onSelect}
              />
            );
          }
          // A closed list is a question you can answer by looking at
          // it, so it gets buttons like a step. The open namespace has
          // no list to show and stays a text box.
          return refinement.choices?.length ? (
            <ChoicePicker
              key={refinement.key}
              refinement={refinement}
              showPrompt={showPrompts}
              labelledBy={headingId}
              dead={deadFor(refinement)}
              onSelect={onSelect}
            />
          ) : (
            <NamespacePicker
              key={refinement.key}
              refinement={refinement}
              showPrompt={showPrompts}
              onSelect={onSelect}
            />
          );
        })}
      </div>
    </section>
  );
}

/**
 * A refinement with a closed list of answers, drawn as the step
 * options are drawn — because to the person answering it is the same
 * kind of question, and the only reason it is a refinement is that it
 * applies to whatever parts happen to be in play.
 *
 * Picking the selected answer again clears it, which is how you get
 * back to "no preference" without a separate control.
 */
function ChoicePicker({
  refinement,
  showPrompt,
  labelledBy,
  dead,
  onSelect,
}: {
  refinement: GuideRefinement;
  /** False when the section heading is already this question. */
  showPrompt: boolean;
  /** The section heading, to name the group by when it is. */
  labelledBy: string;
  dead: string[];
  onSelect: (key: string, value: string | null) => void;
}) {
  // Named by its own prompt when it has one, and by the section
  // heading when the heading *is* its prompt — rather than a hidden
  // copy of the same words, which a screen reader would read twice.
  const heading = showPrompt ? `refinement-${refinement.key}` : labelledBy;
  return (
    <section aria-labelledby={heading}>
      {showPrompt && (
        <h3 id={heading} className="font-semibold mb-2">
          {refinement.prompt}
        </h3>
      )}
      <div role="group" aria-labelledby={heading} className="flex flex-col gap-1">
        {refinement.choices?.map((choice) => {
          const chosen = refinement.selected === choice.tag;
          return (
            <Answer
              key={choice.tag}
              label={labelFor(choice)}
              hint={choice.blurb}
              chosen={chosen}
              dead={dead.includes(choice.tag)}
              onPick={() => onSelect(refinement.key, chosen ? null : choice.tag)}
            />
          );
        })}
      </div>
    </section>
  );
}

/**
 * What to call a derived answer.
 *
 * A curated choice carries its own title. A derived one carries only
 * the tag, so the label is its last element with the underscores taken
 * out — and the count beside it, because "OpenLOCK (135)" and
 * "DragonLock (46)" is the difference between two answers that
 * otherwise look equally good.
 */
function labelFor(choice: GuideChoice): string {
  if (choice.title) return choice.title;
  // A derived answer is a tag: its last element, underscores out, and
  // the first letter up. Not a brand's own capitalisation — a list of
  // those would be the stale thing deriving exists to avoid — but
  // enough that "openlock" does not read as a typo.
  const name = (choice.tag.split('|').pop() ?? choice.tag).replace(/_/g, ' ');
  const pretty = name.charAt(0).toUpperCase() + name.slice(1);
  // The count is the difference between two answers that otherwise
  // look equally good: 135 pieces behind one and 46 behind another.
  return choice.count === undefined ? pretty : `${pretty} (${choice.count})`;
}

function Toggle({
  refinement,
  showPrompt,
  dead: deadValues,
  onSelect,
}: {
  refinement: GuideRefinement;
  /** False when the section heading is already this question. */
  showPrompt: boolean;
  dead: string[];
  onSelect: (key: string, value: string | null) => void;
}) {
  // A yes/no the catalog cannot always answer: four of the eight wall
  // textures have no pegged wall at all. Disabled rather than hidden,
  // with the reason on hover, because "not with this texture" is the
  // useful half of the answer.
  const dead = deadValues.includes('on') && refinement.selected !== 'on';
  return (
    <label
      className={`flex items-center gap-2 ${dead ? 'text-gray-400' : ''}`}
      title={
        dead
          ? 'Nothing in the catalog matches this with your other choices'
          : undefined
      }
    >
      <input
        type="checkbox"
        aria-label={showPrompt ? undefined : refinement.prompt}
        disabled={dead}
        checked={refinement.selected === 'on'}
        onChange={(e) =>
          onSelect(refinement.key, e.target.checked ? 'on' : 'off')
        }
      />
      {showPrompt && <span>{refinement.prompt}</span>}
    </label>
  );
}

/**
 * A namespace refinement is a free tag within its namespace. Until the
 * catalog offers "which of these tags do the candidates carry", this is
 * a text entry rather than a menu — deliberately plain, and the backend
 * rejects a tag from the wrong namespace.
 */
function NamespacePicker({
  refinement,
  showPrompt,
  onSelect,
}: {
  refinement: GuideRefinement;
  /** False when the section heading is already this question. */
  showPrompt: boolean;
  onSelect: (key: string, value: string | null) => void;
}) {
  const box = (
    <input
      type="text"
      // Named either by the visible label or by `aria-label`, never
      // by a hidden copy of the heading above it.
      aria-label={showPrompt ? undefined : refinement.prompt}
      className="border border-gray-300 rounded px-2 py-1"
      placeholder={`${refinement.from_namespace}|...`}
      defaultValue={refinement.selected ?? ''}
      onBlur={(e) => onSelect(refinement.key, e.target.value.trim() || null)}
    />
  );
  if (!showPrompt) return box;
  return (
    <label className="flex items-center gap-2">
      <span>{refinement.prompt}</span>
      {box}
    </label>
  );
}
