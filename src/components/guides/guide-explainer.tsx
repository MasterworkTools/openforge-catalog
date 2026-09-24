import React from 'react';
import { GuideStep } from '@/services/guide-service';

/**
 * The question, explained, in the column where the answer will appear.
 *
 * A wizard's first screen has nothing to show yet — no method chosen
 * means no parts — and the options on the left are three words each.
 * The difference between the three ways to build a wall is the whole
 * decision, so it belongs in the big column rather than in a tooltip.
 *
 * Shown for the first unanswered step only. Once it is answered the
 * parts take the space, which is the right trade: by then the person
 * has made the choice this was explaining.
 */
export function GuideExplainer({ step }: GuideExplainerProps) {
  const described = step.options.filter((option) => option.blurb);
  if (described.length === 0) return null;

  return (
    <section className="guide-explainer mb-8" aria-labelledby="explainer">
      {/* Not the step's own prompt — that is asked on the left, and
          repeating it here would read as two questions. */}
      <h2 id="explainer" className="text-xl font-bold mb-3">
        What these mean
      </h2>
      <div className="flex flex-col gap-4">
        {described.map((option) => (
          <article
            key={option.key}
            className="rounded border border-gray-200 p-4"
          >
            <h3 className="font-semibold mb-1">{option.title}</h3>
            <p className="text-sm text-gray-700">{option.blurb}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

interface GuideExplainerProps {
  step: GuideStep;
}

/**
 * The step the person is being asked right now: the first one with no
 * answer. Null once every reachable step is answered.
 */
export function currentStep(steps: GuideStep[]): GuideStep | null {
  return steps.find((step) => step.selected === null) ?? null;
}
