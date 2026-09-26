'use client';

import React from 'react';
import {
  GuideChoice,
  GuideRefinement,
  GuideStep,
  MissingReason,
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

/** Why answers are missing, by question then by answer. */
export type Because = Record<string, Record<string, MissingReason>> | null;

/**
 * What is not on offer, and why.
 *
 * Missing answers are not drawn at all — an answer you cannot pick is
 * not an answer. But "no rough stone floor" is baffling on its own and
 * obvious once you know which choice did it, so the list says what it
 * would have left empty and, where one answer is responsible, which.
 */
function Missing({
  hidden,
  because,
  labels,
}: {
  hidden: string[];
  because?: Record<string, MissingReason>;
  labels: (value: string) => string;
}) {
  if (hidden.length === 0) return null;
  return (
    <ul className="mt-2 text-xs text-gray-500 list-none">
      {hidden.map((value) => {
        const why = because?.[value];
        return (
          <li key={value}>
            {labels(value)} — no {why?.part ?? 'match'}
            {why?.prompt ? ` for your "${why.prompt}" answer` : ''}
          </li>
        );
      })}
    </ul>
  );
}

interface GuideStepsProps {
  steps: GuideStep[];
  unavailable?: Unavailable;
  because?: Because;
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
  because,
  opened,
  onOpenChange,
  onSelect,
}: GuideStepsProps) {
  return (
    <div className="guide-steps">
      {steps.map((step) => {
        const dead = unavailable?.[step.key] ?? step.unavailable ?? [];
        const why = because?.[step.key] ?? step.because;
        return step.selected === null ? (
          <OpenStep
            key={step.key}
            step={step}
            dead={dead}
            because={why}
            onSelect={onSelect}
          />
        ) : (
          <AnsweredStep
            key={step.key}
            step={step}
            dead={dead}
            because={why}
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
  because,
  onSelect,
}: {
  step: GuideStep;
  dead: string[];
  because?: Record<string, MissingReason>;
  onSelect: (key: string, value: string | null) => void;
}) {
  const live = step.options.filter((option) => !dead.includes(option.key));
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
        {live.map((option) => (
          <Answer
            key={option.key}
            label={option.title}
            chosen={false}
            recommended={step.recommended === option.key}
            assumed={step.recommended === option.key}
            onPick={() => onSelect(step.key, option.key)}
          />
        ))}
      </div>
      <Missing
        hidden={dead}
        because={because}
        labels={(value) =>
          step.options.find((o) => o.key === value)?.title ?? value
        }
      />
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
  because,
  open,
  onOpenChange,
  onSelect,
}: {
  step: GuideStep;
  dead: string[];
  because?: Record<string, MissingReason>;
  open: boolean;
  onOpenChange?: (key: string | null) => void;
  onSelect: (key: string, value: string | null) => void;
}) {
  const chosen = step.options.find((option) => option.key === step.selected);
  // The answer in force is always drawn, dead or not: it is the one
  // thing this section is here to show, and hiding it would leave a
  // reopened question looking as though it was never answered.
  const live = step.options.filter(
    (option) => option.key === step.selected || !dead.includes(option.key)
  );

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
          {live.map((option) => (
            <Answer
              key={option.key}
              label={option.title}
              chosen={step.selected === option.key}
              recommended={step.recommended === option.key}
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
        <Missing
          hidden={dead.filter((value) => value !== step.selected)}
          because={because}
          labels={(value) =>
            step.options.find((o) => o.key === value)?.title ?? value
          }
        />
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
 * Every answer drawn here is one you can pick. The ones the catalog
 * has nothing for never reach this — see `Missing`.
 */
function Answer({
  label,
  hint,
  chosen,
  recommended,
  assumed,
  onPick,
}: {
  label: string;
  /** What this answer is, when the catalog has something to say. */
  hint?: string;
  chosen: boolean;
  /** Marked as the one to pick if you have no opinion. */
  recommended?: boolean;
  /** Recommended *and* in force, because nothing else was chosen. */
  assumed?: boolean;
  onPick: () => void;
}) {
  return (
    <button
      type="button"
      aria-pressed={chosen}
      title={hint}
      onClick={onPick}
      className={`border rounded p-3 text-left ${
        chosen
          ? 'border-blue-600 bg-blue-50 font-semibold'
          : // Dashed, not solid: this is what the parts are being
            // built from, but nobody has said so yet.
            assumed
            ? 'border-blue-400 border-dashed bg-blue-50/40'
            : 'border-gray-300'
      }`}
    >
      {label}
      {recommended && (
        <span className="ml-2 text-xs font-normal text-blue-700">
          Recommended
        </span>
      )}
    </button>
  );
}

interface GuideRefinementsProps {
  refinements: GuideRefinement[];
  unavailable?: Unavailable;
  because?: Because;
  /** The one answered question reopened, shared with the steps. */
  opened?: string | null;
  onOpenChange?: (key: string | null) => void;
  onSelect: (key: string, value: string | null) => void;
}

export function GuideRefinements({
  refinements,
  unavailable,
  because,
  opened,
  onOpenChange,
  onSelect,
}: GuideRefinementsProps) {
  const deadFor = (refinement: GuideRefinement) =>
    unavailable?.[refinement.key] ?? refinement.unavailable ?? [];
  const becauseFor = (refinement: GuideRefinement) =>
    because?.[refinement.key] ?? refinement.because;
  // A yes/no question whose "yes" is dead is not a question — pegs in
  // a texture that has none is nothing to decide. Dropped here rather
  // than inside, so a section left with nothing is never headed.
  const asked = refinements.filter(
    (refinement) =>
      !refinement.on_tags ||
      refinement.selected !== null ||
      !deadFor(refinement).includes('on')
  );
  if (asked.length === 0) return null;
  // A section each, in document order. A question is its own section
  // headed by its own prompt — "Change anything" over the lot of them
  // said nothing and made four unrelated questions look like one.
  //
  // A `group` joins several into one section under a shared heading,
  // for the ones that really are a single decision: which clip the
  // bases use, and then its variants.
  const sections: { name: string; grouped: boolean; of: GuideRefinement[] }[] =
    [];
  for (const refinement of asked) {
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
          becauseFor={becauseFor}
          opened={opened}
          onOpenChange={onOpenChange}
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
  becauseFor,
  opened,
  onOpenChange,
  onSelect,
}: {
  name: string;
  showPrompts: boolean;
  refinements: GuideRefinement[];
  deadFor: (refinement: GuideRefinement) => string[];
  becauseFor: (
    refinement: GuideRefinement
  ) => Record<string, MissingReason> | undefined;
  opened?: string | null;
  onOpenChange?: (key: string | null) => void;
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
          // Answered and not reopened: folded to its answer, exactly
          // as a settled step is. Clicking it opens it again.
          if (refinement.selected !== null && opened !== refinement.key) {
            return (
              <AnsweredRefinement
                key={refinement.key}
                refinement={refinement}
                showPrompt={showPrompts}
                onOpen={() => onOpenChange?.(refinement.key)}
              />
            );
          }
          // Answering closes it, so the next question is what is open.
          const answer = (key: string, value: string | null) => {
            onOpenChange?.(null);
            onSelect(key, value);
          };
          if (refinement.on_tags) {
            return (
              <Toggle
                key={refinement.key}
                refinement={refinement}
                showPrompt={showPrompts}
                onSelect={answer}
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
              because={becauseFor(refinement)}
              onSelect={answer}
            />
          ) : (
            <NamespacePicker
              key={refinement.key}
              refinement={refinement}
              showPrompt={showPrompts}
              onSelect={answer}
            />
          );
        })}
      </div>
    </section>
  );
}

/**
 * A settled question, folded to its answer.
 *
 * The same shape as a settled step, and for the same reason: the
 * column grows as you go, and a question that is answered keeps only
 * what it answered. Clicking it opens it again, which is also how you
 * clear it — the answers inside toggle.
 */
function AnsweredRefinement({
  refinement,
  showPrompt,
  onOpen,
}: {
  refinement: GuideRefinement;
  showPrompt: boolean;
  onOpen: () => void;
}) {
  const chosen = refinement.choices?.find(
    (choice) => choice.tag === refinement.selected
  );
  const answer = chosen
    ? labelFor(chosen)
    : refinement.selected === 'on'
      ? 'Yes'
      : refinement.selected === 'off'
        ? 'No'
        : (refinement.selected ?? '');
  return (
    <button
      type="button"
      onClick={onOpen}
      aria-expanded={false}
      className="w-full text-left rounded border border-gray-200 px-3 py-2 hover:border-gray-400"
    >
      {showPrompt && (
        <span className="block text-xs uppercase tracking-wide text-gray-500">
          {refinement.prompt}
        </span>
      )}
      <span className="block font-semibold">{answer}</span>
    </button>
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
  because,
  onSelect,
}: {
  refinement: GuideRefinement;
  /** False when the section heading is already this question. */
  showPrompt: boolean;
  /** The section heading, to name the group by when it is. */
  labelledBy: string;
  dead: string[];
  because?: Record<string, MissingReason>;
  onSelect: (key: string, value: string | null) => void;
}) {
  // Named by its own prompt when it has one, and by the section
  // heading when the heading *is* its prompt — rather than a hidden
  // copy of the same words, which a screen reader would read twice.
  const heading = showPrompt ? `refinement-${refinement.key}` : labelledBy;
  const live = (refinement.choices ?? []).filter(
    (choice) => choice.tag === refinement.selected || !dead.includes(choice.tag)
  );
  return (
    <section aria-labelledby={heading}>
      {showPrompt && (
        <h3 id={heading} className="font-semibold mb-2">
          {refinement.prompt}
        </h3>
      )}
      <div role="group" aria-labelledby={heading} className="flex flex-col gap-1">
        {live.map((choice) => {
          const chosen = refinement.selected === choice.tag;
          return (
            <Answer
              key={choice.tag}
              label={labelFor(choice)}
              hint={choice.blurb}
              chosen={chosen}
              recommended={refinement.recommended === choice.tag}
              assumed={
                refinement.selected === null &&
                refinement.recommended === choice.tag
              }
              onPick={() => onSelect(refinement.key, chosen ? null : choice.tag)}
            />
          );
        })}
      </div>
      <Missing
        hidden={dead.filter((tag) => tag !== refinement.selected)}
        because={because}
        labels={(tag) => {
          const choice = refinement.choices?.find((c) => c.tag === tag);
          return choice ? labelFor(choice) : tag;
        }}
      />
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
  onSelect,
}: {
  refinement: GuideRefinement;
  /** False when the section heading is already this question. */
  showPrompt: boolean;
  onSelect: (key: string, value: string | null) => void;
}) {
  // A yes/no the catalog cannot always answer — four of the eight wall
  // textures have no pegged wall at all — is not drawn at all. That is
  // decided by the caller, which drops the whole question rather than
  // heading a section over an unanswerable one.
  return (
    <label className="flex items-center gap-2">
      <input
        type="checkbox"
        aria-label={showPrompt ? undefined : refinement.prompt}
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
