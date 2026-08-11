import { loadConfig } from '../src/config.mjs';
import { GoogleSheetsRepository, NEWS_HEADERS, LEAD_HEADERS } from '../src/services/google-sheets.mjs';

const config = loadConfig();
const repository = await GoogleSheetsRepository.fromConfig(config.google);
await repository.ensureSchema();
console.log(`Sheets ready: ${config.google.newsSheetName} (${NEWS_HEADERS.join(', ')})`);
console.log(`Sheets ready: ${config.google.leadsSheetName} (${LEAD_HEADERS.join(', ')})`);
