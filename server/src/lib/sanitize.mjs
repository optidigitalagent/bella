const CONTROL_CHARACTERS = /[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]/g;

export function sanitizeText(value) {
  return String(value ?? '')
    .replace(CONTROL_CHARACTERS, '')
    .replace(/\r\n?/g, '\n')
    .trim();
}

export function normalizePhone(value) {
  return sanitizeText(value).replace(/[\u00A0\s]+/g, ' ');
}

export function safeLogError(error) {
  return {
    name: error?.name || 'Error',
    message: error?.message || 'Unknown error',
    service: error?.service,
    code: error?.code
  };
}
