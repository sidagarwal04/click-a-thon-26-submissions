/**
 * PII Scrubber Tests
 * @module compliance/pii-scrubber.spec
 */

import { describe, expect, it } from 'vitest';

import { createDefaultScrubber, createPIIScrubber, scrubHeaders, scrubUrl } from './pii-scrubber';

describe('PII Scrubber', () => {
  describe('createPIIScrubber', () => {
    it('should detect and scrub email addresses', () => {
      const scrubber = createPIIScrubber({ enabled: true });
      const result = scrubber.scrubString('Contact me at john@example.com for more info');

      expect(result.detected).toBe(true);
      expect(result.type).toBe('email');
      expect(result.redactedValue).toBe('Contact me at [EMAIL_REDACTED] for more info');
    });

    it('should detect and scrub phone numbers', () => {
      const scrubber = createPIIScrubber({ enabled: true });
      const result = scrubber.scrubString('Call me at 555-123-4567');

      expect(result.detected).toBe(true);
      expect(result.redactedValue).toContain('[PHONE_REDACTED]');
    });

    it('should detect and scrub SSN', () => {
      const scrubber = createPIIScrubber({ enabled: true });
      const result = scrubber.scrubString('SSN: 123-45-6789');

      expect(result.detected).toBe(true);
      expect(result.type).toBe('ssn');
      expect(result.redactedValue).toBe('SSN: [SSN_REDACTED]');
    });

    it('should detect and scrub credit card numbers', () => {
      const scrubber = createPIIScrubber({ enabled: true });
      const result = scrubber.scrubString('Card: 4111-1111-1111-1111');

      expect(result.detected).toBe(true);
      expect(result.type).toBe('creditCard');
      expect(result.redactedValue).toBe('Card: [CC_REDACTED]');
    });

    it('should detect and scrub JWT tokens', () => {
      const scrubber = createPIIScrubber({ enabled: true });
      const jwt =
        'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U';
      const result = scrubber.scrubString(`Bearer ${jwt}`);

      expect(result.detected).toBe(true);
      expect(result.redactedValue).toContain('[JWT_REDACTED]');
    });

    it('should not modify string when disabled', () => {
      const scrubber = createPIIScrubber({ enabled: false });
      const input = 'Email: john@example.com';
      const result = scrubber.scrubString(input);

      expect(result.detected).toBe(false);
      expect(result.redactedValue).toBe(input);
    });

    it('should scrub objects recursively', () => {
      const scrubber = createPIIScrubber({ enabled: true });
      const input = {
        user: {
          name: 'John',
          email: 'john@example.com',
          phone: '555-123-4567',
        },
        data: 'Some data',
      };

      // scrubObject preserves shape but is typed Record<string, unknown>,
      // because it accepts anything. The caller knows what it passed in.
      const result = scrubber.scrubObject(input) as {
        user: Record<string, string>;
        data: string;
      };

      expect(result.user.email).toBe('[EMAIL_REDACTED]');
      expect(result.user.phone).toContain('[PHONE_REDACTED]');
      expect(result.user.name).toBe('John');
      expect(result.data).toBe('Some data');
    });

    it('should scrub fields by name', () => {
      const scrubber = createPIIScrubber({
        enabled: true,
        piiFields: ['password', 'secret'],
      });

      const input = {
        username: 'john',
        password: 'super-secret-123',
        secret: 'another-secret',
      };

      const result = scrubber.scrubObject(input);

      expect(result.username).toBe('john');
      expect(result.password).toBe('[REDACTED]');
      expect(result.secret).toBe('[REDACTED]');
    });

    it('should detect PII presence', () => {
      const scrubber = createPIIScrubber({ enabled: true });

      expect(scrubber.containsPII('No PII here')).toBe(false);
      expect(scrubber.containsPII('Email: test@example.com')).toBe(true);
      expect(scrubber.containsPII('SSN: 123-45-6789')).toBe(true);
    });

    it('should detect PII type', () => {
      const scrubber = createPIIScrubber({ enabled: true });

      expect(scrubber.detectPIIType('test@example.com')).toBe('email');
      expect(scrubber.detectPIIType('123-45-6789')).toBe('ssn');
      expect(scrubber.detectPIIType('Hello world')).toBe(null);
    });
  });

  describe('createDefaultScrubber', () => {
    it('should create a working scrubber', () => {
      const scrubber = createDefaultScrubber();
      const result = scrubber.scrubString('test@example.com');

      expect(result.detected).toBe(true);
      expect(result.redactedValue).toBe('[EMAIL_REDACTED]');
    });
  });

  describe('scrubUrl', () => {
    it('should scrub sensitive query parameters', () => {
      const url = 'https://example.com/api?token=secret123&page=1';
      const result = scrubUrl(url);

      expect(result).toContain('token=[REDACTED]');
      expect(result).toContain('page=1');
    });

    it('should scrub api_key parameter', () => {
      const url = 'https://example.com/api?api_key=mykey123';
      const result = scrubUrl(url);

      expect(result).toContain('api_key=[REDACTED]');
    });

    it('should handle URLs without sensitive params', () => {
      const url = 'https://example.com/api?page=1&sort=name';
      const result = scrubUrl(url);

      expect(result).toBe(url);
    });
  });

  describe('scrubHeaders', () => {
    it('should scrub authorization header', () => {
      const headers = {
        Authorization: 'Bearer secret-token',
        'Content-Type': 'application/json',
      };

      const result = scrubHeaders(headers);

      expect(result['Authorization']).toBe('[REDACTED]');
      expect(result['Content-Type']).toBe('application/json');
    });

    it('should scrub cookie header', () => {
      const headers = {
        Cookie: 'session=abc123',
        Accept: 'application/json',
      };

      const result = scrubHeaders(headers);

      expect(result['Cookie']).toBe('[REDACTED]');
      expect(result['Accept']).toBe('application/json');
    });

    it('should be case-insensitive', () => {
      const headers = {
        authorization: 'Bearer token',
        COOKIE: 'session=123',
      };

      const result = scrubHeaders(headers);

      expect(result['authorization']).toBe('[REDACTED]');
      expect(result['COOKIE']).toBe('[REDACTED]');
    });
  });
});
