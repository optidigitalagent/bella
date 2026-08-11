export class Mutex {
  #tail = Promise.resolve();

  async runExclusive(callback) {
    let release;
    const previous = this.#tail;
    this.#tail = new Promise((resolve) => { release = resolve; });
    await previous;
    try {
      return await callback();
    } finally {
      release();
    }
  }
}
