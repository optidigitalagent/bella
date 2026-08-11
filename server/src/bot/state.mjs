export const BotState = Object.freeze({
  IDLE: 'IDLE',
  WAITING_TITLE: 'WAITING_TITLE',
  WAITING_DESCRIPTION: 'WAITING_DESCRIPTION',
  WAITING_MEDIA: 'WAITING_MEDIA',
  WAITING_INSTAGRAM: 'WAITING_INSTAGRAM',
  WAITING_CONFIRMATION: 'WAITING_CONFIRMATION',
  WAITING_EDIT_VALUE: 'WAITING_EDIT_VALUE',
  WAITING_EDIT_MEDIA: 'WAITING_EDIT_MEDIA'
});

export class DraftStore {
  constructor({ ttlMs, onExpire = async () => {} }) {
    this.ttlMs = ttlMs;
    this.onExpire = onExpire;
    this.entries = new Map();
    this.timer = setInterval(() => this.cleanup(), Math.min(ttlMs, 60_000));
    this.timer.unref?.();
  }

  get(userId) {
    const item = this.entries.get(String(userId));
    if (!item) return null;
    if (item.expiresAt <= Date.now()) {
      this.entries.delete(String(userId));
      void this.onExpire(item.value);
      return null;
    }
    return item.value;
  }

  set(userId, value) {
    this.entries.set(String(userId), { value, expiresAt: Date.now() + this.ttlMs });
    return value;
  }

  delete(userId) {
    const item = this.entries.get(String(userId));
    this.entries.delete(String(userId));
    return item?.value || null;
  }

  async cleanup() {
    const now = Date.now();
    for (const [key, item] of this.entries) {
      if (item.expiresAt <= now) {
        this.entries.delete(key);
        await this.onExpire(item.value);
      }
    }
  }

  close() {
    clearInterval(this.timer);
  }
}
