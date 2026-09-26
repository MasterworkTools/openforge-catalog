import React from 'react';
import { GuideRefinement, GuideStep } from '@/services/guide-service';

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
export function GuideExplainer({
  steps,
  refinements = [],
  opened,
}: GuideExplainerProps) {
  // Steps and refinements are one queue from here: the column
  // explains whatever question is open, and to the person answering
  // there is no difference between the two kinds.
  const questions: Question[] = [
    ...steps.map(asQuestion),
    ...refinements.map(asQuestion),
  ];
  // A reopened question wins. Going back to a settled choice is
  // exactly when the explanation is wanted again — that is what
  // reopening it is *for* — and it should not have to be read from
  // memory against the one question still outstanding.
  const reopened = questions.find((question) => question.key === opened);
  const asking = reopened ?? questions.find((q) => q.selected === null);
  // While a question stands, explain its answers — but only if it has
  // anything to say. Not every question does: "what size tiles?" is
  // eight numbers and explaining them would be padding.
  const offered =
    asking?.answers
      .filter((answer) => answer.blurb)
      .map((answer) => ({ step: asking.key, option: answer })) ?? [];
  // A step can also carry prose of its own, for what is true of the
  // question rather than of any one answer: that sizes are in inches,
  // and that a 1 inch hallway does not fit a mini. Repeating that on
  // eight size buttons would be absurd.
  const preamble = asking?.blurb;
  // Otherwise the column explains what *was* chosen, rather than going
  // blank. The same words, still the reason this build is this build,
  // and it keeps a third of the page from being empty for the
  // questions whose answers explain themselves.
  const explaining = offered.length > 0 || Boolean(preamble);
  const heading = explaining ? 'What these mean' : 'What you chose';
  const described = explaining
    ? offered
    : chosenOptions(questions).filter(({ option }) => option.blurb);
  if (described.length === 0 && !(explaining && preamble)) return null;

  return (
    <section className="guide-explainer mb-8" aria-labelledby="explainer">
      {/* Not the step's own prompt — that is asked on the left, and
          repeating it here would read as two questions. */}
      <h2 id="explainer" className="text-xl font-bold mb-3">
        {heading}
      </h2>
      {explaining && preamble && (
        <div className="mb-4">
          {paragraphs(preamble).map((para, i) => (
            <p key={i} className="text-sm text-gray-700 mb-2 last:mb-0">
              {linked(para, asking?.links)}
            </p>
          ))}
        </div>
      )}
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
            {/* A paragraph each, rather than one block with the breaks
                held by CSS: these descriptions run to three paragraphs
                and want the space between them. The author writes
                blank lines in the fixture and never sees any markup. */}
            {paragraphs(option.blurb).map((para, i) => (
              <p key={i} className="text-sm text-gray-700 mb-2 last:mb-0">
                {linked(para, option.links)}
              </p>
            ))}
          </article>
        ))}
      </div>
    </section>
  );
}

/** The blurb's paragraphs. A folded YAML blank line is one newline. */
function paragraphs(blurb?: string): string[] {
  return (blurb ?? '')
    .split('\n')
    .map((para) => para.trim())
    .filter(Boolean);
}

/**
 * The blurb with its named entities turned into links.
 *
 * The names live in the prose and the URLs live beside it, rather than
 * markup in the middle of a sentence an author is trying to write. A
 * name that appears twice links twice without anyone thinking about
 * it, and a link that is only ever data cannot inject markup.
 *
 * Longest phrase first, so "Fat Dragon Games" wins over a bare "Fat
 * Dragon" if both were ever listed.
 */
function linked(text: string, links?: Record<string, string>) {
  const phrases = Object.keys(links ?? {}).sort((a, b) => b.length - a.length);
  if (phrases.length === 0) return text;
  const pattern = new RegExp(
    `(${phrases.map(escapeForRegExp).join('|')})`,
    'g'
  );
  return text.split(pattern).map((piece, i) =>
    links?.[piece] ? (
      <a
        key={i}
        href={links[piece]}
        target="_blank"
        rel="noreferrer noopener"
        className="text-blue-700 underline"
      >
        {piece}
      </a>
    ) : (
      piece
    )
  );
}

function escapeForRegExp(phrase: string): string {
  return phrase.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

interface GuideExplainerProps {
  steps: GuideStep[];
  refinements?: GuideRefinement[];
  /** An answered question the person has gone back to. */
  opened?: string | null;
}

/**
 * A step and a refinement, seen as the same thing.
 *
 * They differ in what they do to the build — a step chooses which
 * parts there are, a refinement narrows the ones there already — and
 * not at all in how they are explained.
 */
interface Question {
  key: string;
  selected: string | null;
  blurb?: string;
  links?: Record<string, string>;
  answers: {
    key: string;
    title: string;
    blurb?: string;
    links?: Record<string, string>;
  }[];
}

function asQuestion(q: GuideStep | GuideRefinement): Question {
  const options = 'options' in q ? q.options : undefined;
  return {
    key: q.key,
    selected: q.selected,
    blurb: q.blurb,
    links: q.links,
    answers:
      options?.map((o) => ({
        key: o.key,
        title: o.title,
        blurb: o.blurb,
        links: o.links,
      })) ??
      (q as GuideRefinement).choices?.map((c) => ({
        key: c.tag,
        title: c.title ?? c.tag,
        blurb: c.blurb,
      })) ??
      [],
  };
}

/** The answer chosen for each settled question, in the order asked. */
function chosenOptions(questions: Question[]) {
  return questions.flatMap((question) => {
    const chosen = question.answers.find((a) => a.key === question.selected);
    return chosen ? [{ step: question.key, option: chosen }] : [];
  });
}
