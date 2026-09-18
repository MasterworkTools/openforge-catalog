import { renderHook, act } from '@testing-library/react';
import { useCopyToClipboard } from '../use-copy-to-clipboard';
import { copyToClipboard } from '@/utils/clipboard';

// Mock the clipboard utility
jest.mock('@/utils/clipboard', () => ({
  copyToClipboard: jest.fn(),
}));

// Mock navigator.clipboard
Object.assign(navigator, {
  clipboard: {
    writeText: jest.fn(),
  },
});

describe('useCopyToClipboard', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('should initialize with copied as false', () => {
    const { result } = renderHook(() => useCopyToClipboard());

    expect(result.current.copied).toBe(false);
  });

  it('should call copyToClipboard utility when copyText is called', () => {
    const { result } = renderHook(() => useCopyToClipboard());
    const mockCopyToClipboard = copyToClipboard as jest.MockedFunction<typeof copyToClipboard>;

    act(() => {
      result.current.copyText('test text');
    });

    expect(mockCopyToClipboard).toHaveBeenCalledWith('test text', expect.any(Function));
  });

  it('should set copied to true when copy succeeds', async () => {
    const { result } = renderHook(() => useCopyToClipboard());
    const mockCopyToClipboard = copyToClipboard as jest.MockedFunction<typeof copyToClipboard>;

    let successCallback: (() => void) | undefined;
    mockCopyToClipboard.mockImplementation((text, onSuccess) => {
      successCallback = onSuccess;
      return Promise.resolve();
    });

    act(() => {
      result.current.copyText('test text');
    });

    expect(result.current.copied).toBe(false);

    // Simulate successful copy
    act(() => {
      successCallback?.();
    });

    expect(result.current.copied).toBe(true);
  });

  it('should reset copied to false after 2 seconds', async () => {
    const { result } = renderHook(() => useCopyToClipboard());
    const mockCopyToClipboard = copyToClipboard as jest.MockedFunction<typeof copyToClipboard>;

    let successCallback: (() => void) | undefined;
    mockCopyToClipboard.mockImplementation((text, onSuccess) => {
      successCallback = onSuccess;
      return Promise.resolve();
    });

    act(() => {
      result.current.copyText('test text');
    });

    // Simulate successful copy
    act(() => {
      successCallback?.();
    });

    expect(result.current.copied).toBe(true);

    // Fast-forward time by 2 seconds
    act(() => {
      jest.advanceTimersByTime(2000);
    });

    expect(result.current.copied).toBe(false);
  });

  it('should not reset copied before 2 seconds', async () => {
    const { result } = renderHook(() => useCopyToClipboard());
    const mockCopyToClipboard = copyToClipboard as jest.MockedFunction<typeof copyToClipboard>;

    let successCallback: (() => void) | undefined;
    mockCopyToClipboard.mockImplementation((text, onSuccess) => {
      successCallback = onSuccess;
      return Promise.resolve();
    });

    act(() => {
      result.current.copyText('test text');
    });

    // Simulate successful copy
    act(() => {
      successCallback?.();
    });

    expect(result.current.copied).toBe(true);

    // Fast-forward time by 1.5 seconds (less than 2 seconds)
    act(() => {
      jest.advanceTimersByTime(1500);
    });

    expect(result.current.copied).toBe(true);
  });

  it('should handle multiple copy calls correctly', async () => {
    const { result } = renderHook(() => useCopyToClipboard());
    const mockCopyToClipboard = copyToClipboard as jest.MockedFunction<typeof copyToClipboard>;

    let successCallback: (() => void) | undefined;
    mockCopyToClipboard.mockImplementation((text, onSuccess) => {
      successCallback = onSuccess;
      return Promise.resolve();
    });

    // First copy
    act(() => {
      result.current.copyText('first text');
    });

    act(() => {
      successCallback?.();
    });

    expect(result.current.copied).toBe(true);

    // Fast-forward to reset
    act(() => {
      jest.advanceTimersByTime(2000);
    });

    expect(result.current.copied).toBe(false);

    // Second copy
    act(() => {
      result.current.copyText('second text');
    });

    act(() => {
      successCallback?.();
    });

    expect(result.current.copied).toBe(true);
  });

  it('should call copyToClipboard with correct parameters', () => {
    const { result } = renderHook(() => useCopyToClipboard());
    const mockCopyToClipboard = copyToClipboard as jest.MockedFunction<typeof copyToClipboard>;

    act(() => {
      result.current.copyText('test text');
    });

    expect(mockCopyToClipboard).toHaveBeenCalledWith('test text', expect.any(Function));
    expect(mockCopyToClipboard).toHaveBeenCalledTimes(1);
  });
});
