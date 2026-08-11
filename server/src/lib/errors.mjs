export class HttpError extends Error {
  constructor(status, code, message, options = {}) {
    super(message, options);
    this.name = 'HttpError';
    this.status = status;
    this.code = code;
  }
}

export class ExternalServiceError extends Error {
  constructor(service, message, options = {}) {
    super(message, options);
    this.name = 'ExternalServiceError';
    this.service = service;
  }
}
