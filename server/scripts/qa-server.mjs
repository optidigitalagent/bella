import express from 'express';
import { resolve } from 'node:path';

const app = express();
const root = resolve(import.meta.dirname, '..', '..');
const port = Number(process.env.QA_PORT || 4173);

app.use(express.json());
app.get('/health-for-qa', (_request, response) => response.status(204).end());
app.get('/site-config.js', (_request, response) => {
  response.type('application/javascript').send("window.BELLA_API_BASE = window.location.origin;");
});
app.get('/api/news', (_request, response) => {
  response.set('Cache-Control', 'no-store').json([
    {
      id: 'qa-c',
      title: 'Новий простір турботи у Bella Dent',
      description: 'Ми оновили простір клініки, щоб кожен візит був ще спокійнішим і комфортнішим для дорослих та маленьких пацієнтів.',
      mediaType: 'image',
      mediaUrl: 'https://res.cloudinary.com/demo/image/upload/sample.jpg',
      instagramUrl: 'https://www.instagram.com/bella.dent.clinic/',
      publishedAt: '2026-08-11T09:00:00.000Z'
    },
    {
      id: 'qa-b',
      title: 'Навчання команди',
      description: 'Лікарі Bella Dent регулярно вдосконалюють навички та обмінюються клінічним досвідом.',
      mediaType: 'image',
      mediaUrl: 'https://res.cloudinary.com/demo/image/upload/couple.jpg',
      instagramUrl: '',
      publishedAt: '2026-08-10T09:00:00.000Z'
    },
    {
      id: 'qa-a',
      title: 'Технології для точного лікування',
      description: 'Сучасна діагностика допомагає планувати лікування точно, зрозуміло та передбачувано.',
      mediaType: 'video',
      mediaUrl: 'https://res.cloudinary.com/demo/video/upload/dog.mp4',
      instagramUrl: '',
      publishedAt: '2026-08-09T09:00:00.000Z'
    }
  ]);
});
app.post('/api/leads', (_request, response) => response.status(201).json({ ok: true, id: 'qa-lead' }));
app.use(express.static(root));
app.listen(port, '127.0.0.1', () => console.log(`QA server: http://127.0.0.1:${port}`));
