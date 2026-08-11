import { loadConfig } from '../src/config.mjs';
import { PostgresRepository } from '../src/services/postgres.mjs';

const config = loadConfig();
const repository = PostgresRepository.fromConfig(config.database);

try {
  await repository.migrate();
  console.log('Database migrations are up to date.');
} finally {
  await repository.close();
}
