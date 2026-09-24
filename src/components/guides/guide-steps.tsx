'use client';

import React from 'react';
import { GuideRefinement, GuideStep } from '@/services/guide-service';

/**
 * The questions. A step is a set of options, one of which is chosen; a
 * refinement is either a toggle or a tag picked from a namespace.
 * Answering either one re-resolves the parts.
 */

interface GuideStepsProps {
  steps: GuideStep[];
  onSelect: (key: string, value: string | null) => void;
}

export function GuideSteps({ steps, onSelect }: GuideStepsProps) {
  return (
    <div className="guide-steps">
      {steps.map((step) => (
        <section key={step.key} className="mb-8">
          <h2 id={`step-${step.key}`} className="text-xl font-bold mb-3">
            {step.prompt}
          </h2>
          {/* Tied to the heading so a screen reader announces which
              question these buttons answer. */}
          <div
            role="group"
            aria-labelledby={`step-${step.key}`}
            className="flex flex-wrap gap-3"
          >
            {step.options.map((option) => (
              <button
                key={option.key}
                type="button"
                aria-pressed={step.selected === option.key}
                // Re-picking the current answer would rewrite the same
                // URL and re-resolve it for no change.
                onClick={() =>
                  step.selected === option.key
                    ? undefined
                    : onSelect(step.key, option.key)
                }
                className={`border rounded p-3 text-left max-w-xs ${
                  step.selected === option.key
                    ? 'border-blue-600 bg-blue-50'
                    : 'border-gray-300'
                }`}
              >
                {/* Title only. The blurb is what the explainer shows
                    in the wide column while this question stands —
                    putting it here as well makes a narrow column of
                    paragraphs and says everything twice. */}
                <span className="block font-semibold">{option.title}</span>
              </button>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

interface GuideRefinementsProps {
  refinements: GuideRefinement[];
  onSelect: (key: string, value: string | null) => void;
}

export function GuideRefinements({
  refinements,
  onSelect,
}: GuideRefinementsProps) {
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
  onSelect,
}: {
  refinement: GuideRefinement;
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
            <button
              key={choice.tag}
              type="button"
              aria-pressed={chosen}
              onClick={() =>
                onSelect(refinement.key, chosen ? null : choice.tag)
              }
              className={`text-left rounded border px-3 py-2 ${
                chosen
                  ? 'border-blue-600 bg-blue-50 font-semibold'
                  : 'border-gray-300'
              }`}
            >
              {choice.title ?? choice.tag.split('|').pop()}
            </button>
          );
        })}
      </div>
    </section>
  );
}

function Toggle({
  refinement,
  onSelect,
}: {
  refinement: GuideRefinement;
  onSelect: (key: string, value: string | null) => void;
}) {
  return (
    <label className="flex items-center gap-2">
      <input
        type="checkbox"
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
