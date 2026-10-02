import React from 'react';

interface BlueprintActionsProps {
  configValues: { partName: string } | null | undefined;
  onSelectPart: (() => void) | null;
  showDownload: boolean;
  onDownload: (e: React.MouseEvent) => void;
  issueUrl: string;
}

// Matches the pagination controls, which are the other primary action in
// this app.
const primary =
  'px-4 py-2 text-sm font-semibold bg-blue-500 text-white rounded hover:bg-blue-600';

/**
 * The actions on a blueprint.
 *
 * The primary action is a button and the report link is a link, because
 * they are not the same kind of thing: one is why the dialog is open,
 * the other is a way out of it.
 */
const BlueprintActions: React.FC<BlueprintActionsProps> = ({ configValues, onSelectPart, showDownload, onDownload, issueUrl }) => (
  <div className="flex items-center gap-3 flex-wrap my-2">
    {configValues ? (
      <button type="button" className={primary} onClick={() => onSelectPart?.()}>
        Select This Part
      </button>
    ) : (
      showDownload && (
        <button type="button" className={primary} onClick={onDownload}>
          Download
        </button>
      )
    )}
    <a className='visibleLink' href={issueUrl} target="_blank" rel="noopener noreferrer">Report Issue with this model</a>
  </div>
);

export default BlueprintActions;
