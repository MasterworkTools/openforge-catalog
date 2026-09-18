import { formatFileSize } from '../format';

describe('formatFileSize', () => {
  it('formats bytes correctly', () => {
    expect(formatFileSize(512)).toBe('512 B');
    expect(formatFileSize(1023)).toBe('1023 B');
  });

  it('formats kilobytes correctly', () => {
    expect(formatFileSize(1024)).toBe('1 KB');
    expect(formatFileSize(2048)).toBe('2 KB');
    expect(formatFileSize(1536)).toBe('1.5 KB');
    expect(formatFileSize(1048575)).toBe('1024 KB');
  });

  it('formats megabytes correctly', () => {
    expect(formatFileSize(1048576)).toBe('1 MB');
    expect(formatFileSize(2097152)).toBe('2 MB');
    expect(formatFileSize(1572864)).toBe('1.5 MB');
    expect(formatFileSize(1073741823)).toBe('1024 MB');
  });

  it('formats gigabytes correctly', () => {
    expect(formatFileSize(1073741824)).toBe('1 GB');
    expect(formatFileSize(2147483648)).toBe('2 GB');
    expect(formatFileSize(1610612736)).toBe('1.5 GB');
    expect(formatFileSize(1099511627775)).toBe('1024 GB');
  });

  it('formats terabytes correctly', () => {
    expect(formatFileSize(1099511627776)).toBe('1 TB');
    expect(formatFileSize(2199023255552)).toBe('2 TB');
    expect(formatFileSize(1649267441664)).toBe('1.5 TB');
  });

  it('handles zero bytes', () => {
    expect(formatFileSize(0)).toBe('0 B');
  });

  it('handles very small numbers', () => {
    expect(formatFileSize(1)).toBe('1 B');
    expect(formatFileSize(100)).toBe('100 B');
  });

  it('handles decimal precision correctly', () => {
    expect(formatFileSize(1025)).toBe('1 KB');
    expect(formatFileSize(1536)).toBe('1.5 KB');
    expect(formatFileSize(1792)).toBe('1.75 KB');
  });

  it('handles large numbers', () => {
    expect(formatFileSize(Number.MAX_SAFE_INTEGER)).toBe('8192 TB');
  });

  it('handles negative numbers', () => {
    expect(formatFileSize(-1024)).toBe('-1024 B');
    expect(formatFileSize(-512)).toBe('-512 B');
  });
});
