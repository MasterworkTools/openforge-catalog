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
  onSelect: (key: string, value: string | null) => void;
}

export function GuideSteps({
  steps,
  unavailable,
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
  onSelect,
}: {
  step: GuideStep;
  dead: string[];
  onSelect: (key: string, value: string | null) => void;
}) {
  const [open, setOpen] = React.useState(false);
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
                setOpen(false);
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
        onClick={() => setOpen(true)}
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
  return (
    <section className="guide-refinements mb-8">
      <h2 className="text-xl font-bold mb-3">Change anything</h2>
      <div className="flex flex-col gap-3">
        {refinements.map((refinement) => {
          if (refinement.on_tags) {
            return (
              <Toggle
                key={refinement.key}
                refinement={refinement}
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
              dead={deadFor(refinement)}
              onSelect={onSelect}
            />
          ) : (
            <NamespacePicker
              key={refinement.key}
              refinement={refinement}
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
  dead,
  onSelect,
}: {
  refinement: GuideRefinement;
  dead: string[];
  onSelect: (key: string, value: string | null) => void;
}) {
  const heading = `refinement-${refinement.key}`;
  return (
    <section aria-labelledby={heading}>
      <h3 id={heading} className="font-semibold mb-2">
        {refinement.prompt}
      </h3>
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
  dead: deadValues,
  onSelect,
}: {
  refinement: GuideRefinement;
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
        disabled={dead}
        checked={refinement.selected === 'on'}
        onChange={(e) =>
          onSelect(refinement.key, e.target.checked ? 'on' : 'off')
        }
      />
      <span>{refinement.prompt}</span>
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
  onSelect,
}: {
  refinement: GuideRefinement;
  onSelect: (key: string, value: string | null) => void;
}) {
  return (
    <label className="flex items-center gap-2">
      <span>{refinement.prompt}</span>
      <input
        type="text"
        className="border border-gray-300 rounded px-2 py-1"
        placeholder={`${refinement.from_namespace}|...`}
        defaultValue={refinement.selected ?? ''}
        onBlur={(e) =>
          onSelect(refinement.key, e.target.value.trim() || null)
        }
      />
    </label>
  );
}
