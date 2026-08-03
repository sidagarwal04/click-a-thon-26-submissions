import {
  FOUNDATION_ERROR_CODE,
  FoundationError,
  OPFS_FILE_TYPE,
} from '@open-zentra/foundation-data-model';
import type { DataSourceFileInfo } from '@open-zentra/foundation-data-model';

import {
  DownloadError,
  FileDownloadService,
  type DownloadRetryConfig,
  type OpfsManagerOperations,
} from './file-download-service';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const SHORT_RETRY: DownloadRetryConfig = Object.freeze({
  maxRetries: 2,
  initialDelayMs: 1,
  maxDelayMs: 10,
  backoffMultiplier: 2,
});

const makeFile = (overrides: Partial<DataSourceFileInfo> = {}): DataSourceFileInfo => ({
  url: 'https://cdn.example.com/file.parquet',
  filename: 'file.parquet',
  size: 1024,
  rowCount: 100,
  ...overrides,
});

const makeArrayBuffer = (size = 8): ArrayBuffer => new ArrayBuffer(size);

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

// Object.assign rather than assigning onto the mock: a vi.fn() has no `get`,
// so the property has to exist when the object is built for the type to carry
// it, and then no cast is needed to read it back.
const createMockAxios = () => Object.assign(vi.fn(), { get: vi.fn() });

const createMockOpfs = (): OpfsManagerOperations & { writeFile: ReturnType<typeof vi.fn> } => ({
  writeFile: vi.fn().mockResolvedValue(undefined),
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('DownloadError', () => {
  it('extends FoundationError', () => {
    const err = new DownloadError('boom', 'test.parquet');
    expect(err).toBeInstanceOf(FoundationError);
    expect(err).toBeInstanceOf(DownloadError);
    expect(err).toBeInstanceOf(Error);
  });

  it('has correct code, filename, and statusCode', () => {
    const cause = new Error('root cause');
    const err = new DownloadError('Download failed', 'data.parquet', 502, cause);

    expect(err.code).toBe(FOUNDATION_ERROR_CODE.NETWORK_REQUEST_FAILED);
    expect(err.filename).toBe('data.parquet');
    expect(err.statusCode).toBe(502);
    expect(err.message).toBe('Download failed');
    expect(err.name).toBe('DownloadError');
    expect(err.cause).toBe(cause);
  });

  it('allows statusCode to be undefined', () => {
    const err = new DownloadError('Network error', 'x.parquet');
    expect(err.statusCode).toBeUndefined();
  });
});

describe('FileDownloadService', () => {
  let mockAxios: ReturnType<typeof createMockAxios>;
  let mockOpfs: ReturnType<typeof createMockOpfs>;
  let service: FileDownloadService;

  beforeEach(() => {
    mockAxios = createMockAxios();
    mockOpfs = createMockOpfs();
    service = new FileDownloadService({
      opfsManager: mockOpfs,
      retry: SHORT_RETRY,
      concurrency: 1,
      debug: false,
      axiosInstance: mockAxios as never,
    });
  });

  // -----------------------------------------------------------------------
  // downloadFile
  // -----------------------------------------------------------------------

  describe('downloadFile', () => {
    it('makes GET request with arraybuffer responseType', async () => {
      const buf = makeArrayBuffer();
      mockAxios.get.mockResolvedValue({ data: buf });

      const file = makeFile();
      await service.downloadFile(file);

      expect(mockAxios.get).toHaveBeenCalledOnce();
      expect(mockAxios.get).toHaveBeenCalledWith(
        file.url,
        expect.objectContaining({
          responseType: 'arraybuffer',
        }),
      );
    });

    it('calls onProgress during download', async () => {
      const buf = makeArrayBuffer();
      mockAxios.get.mockImplementation(
        (
          _url: string,
          config: { onDownloadProgress?: (e: { loaded: number; total: number }) => void },
        ) => {
          // Simulate progress events
          config?.onDownloadProgress?.({ loaded: 256, total: 1024 });
          config?.onDownloadProgress?.({ loaded: 1024, total: 1024 });
          return Promise.resolve({ data: buf });
        },
      );

      const onProgress = vi.fn();
      const file = makeFile({ size: 1024 });
      await service.downloadFile(file, onProgress);

      expect(onProgress).toHaveBeenCalledWith(256, 1024);
      expect(onProgress).toHaveBeenCalledWith(1024, 1024);
      expect(onProgress).toHaveBeenCalledTimes(2);
    });

    it('throws DownloadError on HTTP errors', async () => {
      mockAxios.get.mockRejectedValue({
        response: { status: 500, statusText: 'Internal Server Error' },
        message: 'Request failed',
      });

      const file = makeFile({ filename: 'broken.parquet' });

      await expect(service.downloadFile(file)).rejects.toThrow(DownloadError);

      try {
        await service.downloadFile(file);
      } catch (err) {
        expect(err).toBeInstanceOf(DownloadError);
        const dlErr = err as DownloadError;
        expect(dlErr.statusCode).toBe(500);
        expect(dlErr.filename).toBe('broken.parquet');
      }
    });

    it('throws DownloadError on network errors', async () => {
      mockAxios.get.mockRejectedValue(new Error('Network Error'));

      const file = makeFile({ filename: 'net.parquet' });

      await expect(service.downloadFile(file)).rejects.toThrow(DownloadError);

      try {
        await service.downloadFile(file);
      } catch (err) {
        const dlErr = err as DownloadError;
        expect(dlErr).toBeInstanceOf(DownloadError);
        expect(dlErr.filename).toBe('net.parquet');
        expect(dlErr.statusCode).toBeUndefined();
        expect(dlErr.message).toBe('Network Error');
      }
    });
  });

  // -----------------------------------------------------------------------
  // downloadFileWithRetry
  // -----------------------------------------------------------------------

  describe('downloadFileWithRetry', () => {
    it('retries on transient errors', async () => {
      const buf = makeArrayBuffer();
      mockAxios.get
        .mockRejectedValueOnce(new Error('timeout'))
        .mockResolvedValueOnce({ data: buf });

      const file = makeFile();
      const result = await service.downloadFileWithRetry(file);

      expect(result).toBeInstanceOf(ArrayBuffer);
      expect(mockAxios.get).toHaveBeenCalledTimes(2);
    });

    it('does not retry on 4xx client errors (except 429)', async () => {
      // 403 should not be retried
      mockAxios.get.mockRejectedValue({
        response: { status: 403, statusText: 'Forbidden' },
        message: 'Forbidden',
      });

      const file = makeFile();
      await expect(service.downloadFileWithRetry(file)).rejects.toThrow(DownloadError);
      // 1 initial attempt, no retries
      expect(mockAxios.get).toHaveBeenCalledTimes(1);
    });

    it('retries on 429 Too Many Requests', async () => {
      const buf = makeArrayBuffer();
      mockAxios.get
        .mockRejectedValueOnce({
          response: { status: 429, statusText: 'Too Many Requests' },
          message: 'Too Many Requests',
        })
        .mockResolvedValueOnce({ data: buf });

      const file = makeFile();
      const result = await service.downloadFileWithRetry(file);

      expect(result).toBeInstanceOf(ArrayBuffer);
      expect(mockAxios.get).toHaveBeenCalledTimes(2);
    });

    it('throws after max retries', async () => {
      mockAxios.get.mockRejectedValue(new Error('connection reset'));

      const file = makeFile({ filename: 'fail.parquet' });

      await expect(service.downloadFileWithRetry(file)).rejects.toThrow(DownloadError);
      // maxRetries = 2 → initial + 2 retries = 3 total attempts
      expect(mockAxios.get).toHaveBeenCalledTimes(3);

      try {
        mockAxios.get.mockClear();
        mockAxios.get.mockRejectedValue(new Error('still broken'));
        await service.downloadFileWithRetry(file);
      } catch (err) {
        const dlErr = err as DownloadError;
        expect(dlErr.message).toContain('after');
        expect(dlErr.filename).toBe('fail.parquet');
      }
    });
  });

  // -----------------------------------------------------------------------
  // downloadAndSaveFiles
  // -----------------------------------------------------------------------

  describe('downloadAndSaveFiles', () => {
    it('downloads and saves all files', async () => {
      const buf = makeArrayBuffer(16);
      mockAxios.get.mockResolvedValue({ data: buf });

      const files: DataSourceFileInfo[] = [
        makeFile({
          filename: 'a.parquet',
          url: 'https://cdn.example.com/a.parquet',
          size: 100,
          rowCount: 10,
        }),
        makeFile({
          filename: 'b.parquet',
          url: 'https://cdn.example.com/b.parquet',
          size: 200,
          rowCount: 20,
        }),
      ];

      await service.downloadAndSaveFiles('events', files);

      expect(mockAxios.get).toHaveBeenCalledTimes(2);
      expect(mockOpfs.writeFile).toHaveBeenCalledTimes(2);

      // Verify writeFile was called with correct args
      expect(mockOpfs.writeFile).toHaveBeenNthCalledWith(
        1,
        'events/a.parquet',
        expect.any(ArrayBuffer),
        expect.objectContaining({
          tableName: 'events',
          fileType: OPFS_FILE_TYPE.PARQUET,
          rowCount: 10,
        }),
      );
      expect(mockOpfs.writeFile).toHaveBeenNthCalledWith(
        2,
        'events/b.parquet',
        expect.any(ArrayBuffer),
        expect.objectContaining({
          tableName: 'events',
          fileType: OPFS_FILE_TYPE.PARQUET,
          rowCount: 20,
        }),
      );
    });

    it('reports progress', async () => {
      const buf = makeArrayBuffer(8);
      mockAxios.get.mockResolvedValue({ data: buf });

      const files: DataSourceFileInfo[] = [
        makeFile({ filename: 'only.parquet', size: 500, rowCount: 50 }),
      ];

      const onProgress = vi.fn();
      await service.downloadAndSaveFiles('metrics', files, onProgress);

      // At minimum: one call at start of file + one final completion call
      expect(onProgress).toHaveBeenCalled();

      // Final call should report completion
      const lastCall = onProgress.mock.calls[onProgress.mock.calls.length - 1][0];
      expect(lastCall).toEqual(
        expect.objectContaining({
          isDownloading: false,
          progress: 100,
          filesTotal: 1,
          filesCompleted: 1,
          currentFile: null,
        }),
      );
    });

    it('returns early for empty files array', async () => {
      const onProgress = vi.fn();
      await service.downloadAndSaveFiles('empty_table', [], onProgress);

      expect(mockAxios.get).not.toHaveBeenCalled();
      expect(mockOpfs.writeFile).not.toHaveBeenCalled();
      expect(onProgress).not.toHaveBeenCalled();
    });
  });
});
