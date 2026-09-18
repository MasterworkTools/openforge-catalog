import React from 'react';

interface BlueprintMetaProps {
  type: string;
  lastModified: string;
  size: string;
}

const BlueprintMeta: React.FC<BlueprintMetaProps> = ({ type, lastModified, size }) => (
  <p>
    <strong>Type:</strong> {type}<br />
    <strong>Last Modified:</strong> {lastModified}, <strong>Size:</strong> {size}
  </p>
);

export default BlueprintMeta;
