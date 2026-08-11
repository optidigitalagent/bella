import { z } from 'zod';
import { sanitizeText, normalizePhone } from './lib/sanitize.mjs';

const sanitizedString = (min, max) => z.string().transform(sanitizeText).pipe(z.string().min(min).max(max));

export const instagramUrlSchema = z.union([
  z.literal(''),
  z.string().url().transform((value, ctx) => {
    const url = new URL(value);
    if (url.protocol !== 'https:' || !['instagram.com', 'www.instagram.com'].includes(url.hostname.toLowerCase())) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'Instagram URL must use https://instagram.com or https://www.instagram.com' });
      return z.NEVER;
    }
    return url.toString();
  })
]);

export const newsDraftSchema = z.object({
  title: sanitizedString(3, 120),
  description: sanitizedString(3, 1500),
  mediaType: z.enum(['image', 'video']),
  mediaUrl: z.string().url().refine((value) => new URL(value).protocol === 'https:', 'Media URL must use HTTPS'),
  cloudinaryPublicId: sanitizedString(1, 300),
  instagramUrl: instagramUrlSchema.default(''),
  createdByTelegramId: z.string().regex(/^\d+$/),
  publishRequestId: sanitizedString(1, 200)
});

export const newsPatchSchema = z.object({
  title: sanitizedString(3, 120).optional(),
  description: sanitizedString(3, 1500).optional(),
  instagramUrl: instagramUrlSchema.optional(),
  mediaType: z.enum(['image', 'video']).optional(),
  mediaUrl: z.string().url().optional(),
  cloudinaryPublicId: sanitizedString(1, 300).optional()
}).refine((patch) => Object.keys(patch).length > 0, 'At least one field is required');

export const leadSchema = z.object({
  name: sanitizedString(2, 100),
  phone: z.string().transform(normalizePhone).pipe(
    z.string().min(6).max(30).regex(/^[+()\-\d\s]+$/, 'Invalid phone number')
  ),
  comment: z.string().transform(sanitizeText).pipe(z.string().max(1000)).default(''),
  website: z.string().max(200).default(''),
  requestId: z.string().trim().min(8).max(100).regex(/^[A-Za-z0-9_-]+$/).optional()
});

export const allowedDocumentMimeTypes = new Map([
  ['image/jpeg', 'image'],
  ['image/png', 'image'],
  ['image/webp', 'image'],
  ['video/mp4', 'video'],
  ['video/quicktime', 'video'],
  ['video/webm', 'video']
]);

export function validateMediaDescriptor(media, maxBytes) {
  if (!media || !['image', 'video'].includes(media.mediaType)) {
    throw new Error('Unsupported media type');
  }
  if (!Number.isFinite(media.fileSize) || media.fileSize <= 0 || media.fileSize > maxBytes) {
    throw new Error(`Media must be between 1 and ${maxBytes} bytes`);
  }
  return media;
}

export function validateMediaBuffer(buffer, mediaType) {
  if (!Buffer.isBuffer(buffer) || buffer.length < 4) throw new Error('Media content is empty or invalid');
  const jpeg = buffer[0] === 0xff && buffer[1] === 0xd8 && buffer[2] === 0xff;
  const png = buffer.subarray(0, 8).equals(Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]));
  const webp = buffer.subarray(0, 4).toString('ascii') === 'RIFF' && buffer.subarray(8, 12).toString('ascii') === 'WEBP';
  const isoVideo = buffer.length >= 12 && buffer.subarray(4, 8).toString('ascii') === 'ftyp';
  const webm = buffer[0] === 0x1a && buffer[1] === 0x45 && buffer[2] === 0xdf && buffer[3] === 0xa3;
  if (mediaType === 'image' && (jpeg || png || webp)) return buffer;
  if (mediaType === 'video' && (isoVideo || webm)) return buffer;
  throw new Error('Media bytes do not match an allowed image/video signature');
}
