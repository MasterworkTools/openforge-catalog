import React from 'react';

interface BlueprintActionsProps {
  configValues: { partName: string } | null | undefined;
  onSelectPart: (() => void) | null;
  showDownload: boolean;
  onDownload: (e: React.MouseEvent) => void;
  issueUrl: string;
}

const BlueprintActions: React.FC<BlueprintActionsProps> = ({ configValues, onSelectPart, showDownload, onDownload, issueUrl }) => (
  <p>
    <strong>
      {configValues ? (
        <a className='visibleLink' href="#" onClick={e => {
          e.preventDefault();
          onSelectPart?.();
        }}>Select This Part</a>
      ) : (
        showDownload && (
          <a className='visibleLink' href="#" onClick={onDownload}>Download</a>
        )
      )}
    </strong>&nbsp;
    (<a className='visibleLink' href={issueUrl} target="_blank" rel="noopener noreferrer">Report Issue with this model</a>)
  </p>
);

export default BlueprintActions;
