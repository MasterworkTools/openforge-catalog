import React from 'react';

interface BlueprintRelatedLinksProps {
  onSwap: (e: React.MouseEvent, tagType: string) => void;
}

const BlueprintRelatedLinks: React.FC<BlueprintRelatedLinksProps> = ({ onSwap }) => (
  <p>
    <strong>Find related:</strong>&nbsp;
    <a className='visibleLink' href="#" onClick={e => onSwap(e, 'texture')}>textures</a>,&nbsp;
    <a className='visibleLink' href="#" onClick={e => onSwap(e, 'size')}>sizes</a>,&nbsp;
    <a className='visibleLink' href="#" onClick={e => onSwap(e, 'connection')}>connections</a>
  </p>
);

export default BlueprintRelatedLinks;
