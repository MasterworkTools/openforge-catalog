import React from 'react';

const ReactMarkdown: React.FC<{ children: string }> = ({ children }) => {
  return React.createElement('div', { 'data-testid': 'markdown-content' }, children);
};

export default ReactMarkdown;
