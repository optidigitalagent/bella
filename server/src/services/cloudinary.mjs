import { v2 as cloudinary } from 'cloudinary';
import { ExternalServiceError } from '../lib/errors.mjs';

export class CloudinaryMediaService {
  constructor(config) {
    this.folder = config.folder;
    cloudinary.config({
      cloud_name: config.cloudName,
      api_key: config.apiKey,
      api_secret: config.apiSecret,
      secure: true
    });
    this.client = cloudinary;
  }

  async upload(buffer, mediaType) {
    try {
      const result = await new Promise((resolve, reject) => {
        const stream = this.client.uploader.upload_stream({
          folder: this.folder,
          resource_type: mediaType,
          use_filename: false,
          unique_filename: true,
          overwrite: false
        }, (error, uploaded) => error ? reject(error) : resolve(uploaded));
        stream.end(buffer);
      });
      if (!result?.secure_url || !result?.public_id) throw new Error('Cloudinary response is incomplete');
      return {
        mediaType,
        mediaUrl: result.secure_url,
        cloudinaryPublicId: result.public_id
      };
    } catch (error) {
      throw new ExternalServiceError('cloudinary', 'Unable to upload media', { cause: error });
    }
  }

  async remove(publicId, mediaType) {
    if (!publicId) return;
    try {
      await this.client.uploader.destroy(publicId, {
        resource_type: mediaType,
        invalidate: true
      });
    } catch (error) {
      throw new ExternalServiceError('cloudinary', 'Unable to remove media', { cause: error });
    }
  }
}
