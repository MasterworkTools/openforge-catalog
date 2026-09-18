/**
 * Copy text to clipboard with optional success and error callbacks
 * @param text - The text to copy to clipboard
 * @param onSuccess - Optional callback to execute on successful copy
 * @param onError - Optional callback to execute on copy error
 * @returns Promise that resolves when copy operation completes
 */
export async function copyToClipboard(
  text: string,
  onSuccess?: () => void,
  onError?: () => void
): Promise<void> {
  try {
    await navigator.clipboard.writeText(text);
    onSuccess?.();
  } catch (error) {
    console.error('Failed to copy to clipboard:', error);
    onError?.();
  }
}
