import { useState } from 'react';
import { copyToClipboard } from '@/utils/clipboard';

export function useCopyToClipboard() {
  const [copied, setCopied] = useState(false);

  const handleCopySuccess = () => {
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const copyText = (text: string) => {
    copyToClipboard(text, handleCopySuccess);
  };

  return { copied, copyText };
}
