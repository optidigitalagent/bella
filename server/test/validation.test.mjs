import test from 'node:test';
import assert from 'node:assert/strict';
import { instagramUrlSchema, leadSchema, validateMediaBuffer, validateMediaDescriptor } from '../src/validation.mjs';

test('invalid Instagram origins are rejected', () => {
  assert.equal(instagramUrlSchema.safeParse('https://evil.example/instagram.com/post').success, false);
  assert.equal(instagramUrlSchema.safeParse('http://instagram.com/p/test').success, false);
  assert.equal(instagramUrlSchema.safeParse('https://www.instagram.com/p/test').success, true);
});

test('invalid and oversize media are rejected', () => {
  assert.throws(() => validateMediaDescriptor({ mediaType: 'document', fileSize: 20 }, 100));
  assert.throws(() => validateMediaDescriptor({ mediaType: 'image', fileSize: 101 }, 100));
  assert.doesNotThrow(() => validateMediaDescriptor({ mediaType: 'video', fileSize: 100 }, 100));
  assert.throws(() => validateMediaBuffer(Buffer.from('not-an-image'), 'image'));
  assert.doesNotThrow(() => validateMediaBuffer(Buffer.from([0xff, 0xd8, 0xff, 0x00]), 'image'));
});

test('lead requires phone and sanitizes control characters', () => {
  assert.equal(leadSchema.safeParse({ name: 'Анна', comment: '', website: '' }).success, false);
  const parsed = leadSchema.parse({ name: ' Ан\u0000на ', phone: '+380 67 123 45 67', comment: '', website: '' });
  assert.equal(parsed.name, 'Анна');
});
