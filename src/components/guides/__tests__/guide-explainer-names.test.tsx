import React from 'react';
import { render, screen } from '@testing-library/react';
import { GuideExplainer } from '../guide-explainer';
import { GuideRefinement } from '@/services/guide-service';

/**
 * A derived answer carries no title, only its tag. The card that
 * explains it is headed by a name, not by `texture|cave`.
 */
const derived = {
  key: 'texture',
  prompt: 'Floor texture',
  role: 'floor',
  browsable: true,
  selected: null,
  recommended: null,
  unavailable: [],
  because: {},
  choices: [
    { tag: 'texture|cave', count: 3, blurb: 'Rough, irregular rock.' },
    { tag: 'texture|dungeon_stone', count: 18, blurb: 'Cut flags.' },
  ],
} as unknown as GuideRefinement;

describe('the explainer names a derived answer', () => {
  it('heads the card with a name rather than the tag', () => {
    render(<GuideExplainer steps={[]} refinements={[derived]} />);

    expect(screen.getByText('Cave')).toBeInTheDocument();
    expect(screen.getByText('Dungeon stone')).toBeInTheDocument();
    expect(screen.queryByText('texture|cave')).not.toBeInTheDocument();
    expect(screen.queryByText('texture|dungeon_stone')).not.toBeInTheDocument();
  });

  it('leaves a curated title alone', () => {
    const curated = {
      ...derived,
      choices: [{ tag: 'texture|towne', title: 'Wood', blurb: 'Boarded.' }],
    } as unknown as GuideRefinement;

    render(<GuideExplainer steps={[]} refinements={[curated]} />);

    expect(screen.getByText('Wood')).toBeInTheDocument();
    expect(screen.queryByText('Towne')).not.toBeInTheDocument();
  });
});
