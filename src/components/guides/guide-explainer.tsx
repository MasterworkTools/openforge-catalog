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
export function GuideExplainer({ steps, opened }: GuideExplainerProps) {
  // A reopened question wins. Going back to a settled choice is
  // exactly when the explanation is wanted again — that is what
  // reopening it is *for* — and it should not have to be read from
  // memory against the one question still outstanding.
  const reopened = steps.find((step) => step.key === opened);
  const asking = reopened ?? currentStep(steps);
  // While a question stands, explain its answers — but only if it has
  // anything to say. Not every question does: "what size tiles?" is
  // eight numbers and explaining them would be padding.
  const offered =
    asking?.options
      .filter((option) => option.blurb)
      .map((option) => ({ step: asking.key, option })) ?? [];
  // Otherwise the column explains what *was* chosen, rather than going
  // blank. The same words, still the reason this build is this build,
  // and it keeps a third of the page from being empty for two of the
  // five questions.
  const explaining = offered.length > 0;
  const heading = explaining ? 'What these mean' : 'What you chose';
  const described = explaining
    ? offered
    : chosenOptions(steps).filter(({ option }) => option.blurb);
  if (described.length === 0) return null;

  return (
    <section className="guide-explainer mb-8" aria-labelledby="explainer">
      {/* Not the step's own prompt — that is asked on the left, and
          repeating it here would read as two questions. */}
      <h2 id="explainer" className="text-xl font-bold mb-3">
        {heading}
      </h2>
      <div className="flex flex-col gap-4">
        {described.map(({ step, option }) => (
          // Keyed by step *and* option: option keys are only unique
          // within their own question, and two questions here really
          // do share one — `wall-print` and `floor-print` both offer
          // `with-base`. Keyed on the option alone, React treats them
          // as the same card and draws one of them twice.
          <article
            key={`${step}:${option.key}`}
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
  steps: GuideStep[];
  /** An answered question the person has gone back to. */
  opened?: string | null;
}

/** The option chosen for each answered step, in the order asked. */
function chosenOptions(steps: GuideStep[]) {
  return steps.flatMap((step) => {
    const chosen = step.options.find((option) => option.key === step.selected);
    return chosen ? [{ step: step.key, option: chosen }] : [];
  });
}

/**
 * The step the person is being asked right now: the first one with no
 * answer. Null once every reachable step is answered.
 */
export function currentStep(steps: GuideStep[]): GuideStep | null {
  return steps.find((step) => step.selected === null) ?? null;
}
