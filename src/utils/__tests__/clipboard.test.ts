import { copyToClipboard } from '../clipboard';

// Mock navigator.clipboard
const mockClipboard = {
  writeText: jest.fn(),
};

Object.defineProperty(navigator, 'clipboard', {
  value: mockClipboard,
  writable: true,
});

describe('clipboard', () => {
  let mockConsoleError: jest.SpyInstance;

  beforeEach(() => {
    jest.clearAllMocks();
    mockConsoleError = jest.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    mockConsoleError.mockRestore();
  });

  describe('copyToClipboard', () => {
    it('successfully copies text to clipboard', async () => {
      const text = 'test text';
      const onSuccess = jest.fn();
      const onError = jest.fn();

      mockClipboard.writeText.mockResolvedValueOnce(undefined);

      await copyToClipboard(text, onSuccess, onError);

      expect(mockClipboard.writeText).toHaveBeenCalledWith(text);
      expect(onSuccess).toHaveBeenCalled();
      expect(onError).not.toHaveBeenCalled();
      expect(mockConsoleError).not.toHaveBeenCalled();
    });

    it('handles clipboard write error', async () => {
      const text = 'test text';
      const onSuccess = jest.fn();
      const onError = jest.fn();
      const error = new Error('Clipboard write failed');

      mockClipboard.writeText.mockRejectedValueOnce(error);

      await copyToClipboard(text, onSuccess, onError);

      expect(mockClipboard.writeText).toHaveBeenCalledWith(text);
      expect(onSuccess).not.toHaveBeenCalled();
      expect(onError).toHaveBeenCalled();
      expect(mockConsoleError).toHaveBeenCalledWith('Failed to copy to clipboard:', error);
    });

    it('works without success callback', async () => {
      const text = 'test text';
      const onError = jest.fn();

      mockClipboard.writeText.mockResolvedValueOnce(undefined);

      await copyToClipboard(text, undefined, onError);

      expect(mockClipboard.writeText).toHaveBeenCalledWith(text);
      expect(onError).not.toHaveBeenCalled();
    });

    it('works without error callback', async () => {
      const text = 'test text';
      const onSuccess = jest.fn();
      const error = new Error('Clipboard write failed');

      mockClipboard.writeText.mockRejectedValueOnce(error);

      await copyToClipboard(text, onSuccess);

      expect(mockClipboard.writeText).toHaveBeenCalledWith(text);
      expect(onSuccess).not.toHaveBeenCalled();
      expect(mockConsoleError).toHaveBeenCalledWith('Failed to copy to clipboard:', error);
    });

    it('works without any callbacks', async () => {
      const text = 'test text';

      mockClipboard.writeText.mockResolvedValueOnce(undefined);

      await copyToClipboard(text);

      expect(mockClipboard.writeText).toHaveBeenCalledWith(text);
      expect(mockConsoleError).not.toHaveBeenCalled();
    });

    it('handles error without any callbacks', async () => {
      const text = 'test text';
      const error = new Error('Clipboard write failed');

      mockClipboard.writeText.mockRejectedValueOnce(error);

      await copyToClipboard(text);

      expect(mockClipboard.writeText).toHaveBeenCalledWith(text);
      expect(mockConsoleError).toHaveBeenCalledWith('Failed to copy to clipboard:', error);
    });

    it('handles empty string', async () => {
      const text = '';
      const onSuccess = jest.fn();

      mockClipboard.writeText.mockResolvedValueOnce(undefined);

      await copyToClipboard(text, onSuccess);

      expect(mockClipboard.writeText).toHaveBeenCalledWith('');
      expect(onSuccess).toHaveBeenCalled();
    });

    it('handles special characters in text', async () => {
      const text = 'test\n\t\r"\'\\text';
      const onSuccess = jest.fn();

      mockClipboard.writeText.mockResolvedValueOnce(undefined);

      await copyToClipboard(text, onSuccess);

      expect(mockClipboard.writeText).toHaveBeenCalledWith(text);
      expect(onSuccess).toHaveBeenCalled();
    });
  });
});
