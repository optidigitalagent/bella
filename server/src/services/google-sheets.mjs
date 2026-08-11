import { google } from 'googleapis';
import { ExternalServiceError } from '../lib/errors.mjs';

export const NEWS_HEADERS = [
  'id', 'status', 'published_at', 'updated_at', 'archived_at', 'title', 'description',
  'media_type', 'media_url', 'cloudinary_public_id', 'instagram_url',
  'created_by_telegram_id', 'publish_request_id'
];

export const LEAD_HEADERS = [
  'id', 'created_at', 'name', 'phone', 'comment', 'source', 'status', 'request_id'
];

function parseCredentials(rawJson, base64Json) {
  const source = rawJson || (base64Json ? Buffer.from(base64Json, 'base64').toString('utf8') : '');
  if (!source) throw new Error('Google service account credentials are missing');
  const parsed = JSON.parse(source);
  if (parsed.private_key) parsed.private_key = parsed.private_key.replace(/\\n/g, '\n');
  return parsed;
}

function quoteSheetName(name) {
  return `'${String(name).replace(/'/g, "''")}'`;
}

function rowToObject(headers, values, rowNumber) {
  const record = { _rowNumber: rowNumber };
  headers.forEach((header, index) => { record[header] = values[index] ?? ''; });
  return record;
}

function objectToRow(headers, record) {
  return headers.map((header) => record[header] ?? '');
}

export class GoogleSheetsRepository {
  constructor({ sheets, spreadsheetId, newsSheetName = 'News', leadsSheetName = 'Leads' }) {
    this.sheets = sheets;
    this.spreadsheetId = spreadsheetId;
    this.newsSheetName = newsSheetName;
    this.leadsSheetName = leadsSheetName;
  }

  static async fromConfig(config) {
    const credentials = parseCredentials(config.serviceAccountJson, config.serviceAccountJsonBase64);
    const auth = new google.auth.GoogleAuth({
      credentials,
      scopes: ['https://www.googleapis.com/auth/spreadsheets']
    });
    return new GoogleSheetsRepository({
      sheets: google.sheets({ version: 'v4', auth }),
      spreadsheetId: config.sheetId,
      newsSheetName: config.newsSheetName,
      leadsSheetName: config.leadsSheetName
    });
  }

  async ensureSchema() {
    try {
      const metadata = await this.sheets.spreadsheets.get({ spreadsheetId: this.spreadsheetId });
      const existing = new Set((metadata.data.sheets || []).map((sheet) => sheet.properties?.title));
      const requests = [];
      for (const title of [this.newsSheetName, this.leadsSheetName]) {
        if (!existing.has(title)) requests.push({ addSheet: { properties: { title } } });
      }
      if (requests.length) {
        await this.sheets.spreadsheets.batchUpdate({
          spreadsheetId: this.spreadsheetId,
          requestBody: { requests }
        });
      }
      await this.#ensureHeaders(this.newsSheetName, NEWS_HEADERS);
      await this.#ensureHeaders(this.leadsSheetName, LEAD_HEADERS);
    } catch (error) {
      throw new ExternalServiceError('google-sheets', 'Unable to initialize Google Sheets schema', { cause: error });
    }
  }

  async #ensureHeaders(sheetName, expectedHeaders) {
    const range = `${quoteSheetName(sheetName)}!1:1`;
    const response = await this.sheets.spreadsheets.values.get({ spreadsheetId: this.spreadsheetId, range });
    const current = response.data.values?.[0] || [];
    if (!current.length) {
      await this.sheets.spreadsheets.values.update({
        spreadsheetId: this.spreadsheetId,
        range: `${quoteSheetName(sheetName)}!A1`,
        valueInputOption: 'RAW',
        requestBody: { values: [expectedHeaders] }
      });
      return;
    }
    const mismatch = expectedHeaders.some((header, index) => current[index] !== header);
    if (mismatch) {
      throw new Error(`${sheetName} headers do not match the expected schema; existing data was not changed`);
    }
  }

  async listNews() {
    return this.#list(this.newsSheetName, NEWS_HEADERS);
  }

  async appendNews(record) {
    return this.#append(this.newsSheetName, NEWS_HEADERS, record);
  }

  async updateNews(id, patch) {
    return this.#updateById(this.newsSheetName, NEWS_HEADERS, id, patch);
  }

  async listLeads() {
    return this.#list(this.leadsSheetName, LEAD_HEADERS);
  }

  async appendLead(record) {
    return this.#append(this.leadsSheetName, LEAD_HEADERS, record);
  }

  async updateLead(id, patch) {
    return this.#updateById(this.leadsSheetName, LEAD_HEADERS, id, patch);
  }

  async #list(sheetName, headers) {
    try {
      const response = await this.sheets.spreadsheets.values.get({
        spreadsheetId: this.spreadsheetId,
        range: `${quoteSheetName(sheetName)}!A:${String.fromCharCode(64 + headers.length)}`
      });
      const rows = response.data.values || [];
      if (!rows.length) return [];
      const actualHeaders = rows[0];
      const mismatch = headers.some((header, index) => actualHeaders[index] !== header);
      if (mismatch) throw new Error(`${sheetName} headers do not match the expected schema`);
      return rows.slice(1)
        .map((values, index) => rowToObject(headers, values, index + 2))
        .filter((record) => record.id);
    } catch (error) {
      if (error instanceof ExternalServiceError) throw error;
      throw new ExternalServiceError('google-sheets', `Unable to read ${sheetName}`, { cause: error });
    }
  }

  async #append(sheetName, headers, record) {
    try {
      await this.sheets.spreadsheets.values.append({
        spreadsheetId: this.spreadsheetId,
        range: `${quoteSheetName(sheetName)}!A1`,
        valueInputOption: 'RAW',
        insertDataOption: 'INSERT_ROWS',
        requestBody: { values: [objectToRow(headers, record)] }
      });
      return record;
    } catch (error) {
      throw new ExternalServiceError('google-sheets', `Unable to append ${sheetName}`, { cause: error });
    }
  }

  async #updateById(sheetName, headers, id, patch) {
    const records = await this.#list(sheetName, headers);
    const current = records.find((record) => record.id === id);
    if (!current) return null;
    const updated = { ...current, ...patch };
    delete updated._rowNumber;
    try {
      await this.sheets.spreadsheets.values.update({
        spreadsheetId: this.spreadsheetId,
        range: `${quoteSheetName(sheetName)}!A${current._rowNumber}:${String.fromCharCode(64 + headers.length)}${current._rowNumber}`,
        valueInputOption: 'RAW',
        requestBody: { values: [objectToRow(headers, updated)] }
      });
      return updated;
    } catch (error) {
      throw new ExternalServiceError('google-sheets', `Unable to update ${sheetName}`, { cause: error });
    }
  }
}
