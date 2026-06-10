/* ═══════════════════════════════════════════════════════════════════════
   GOOGLE SHEETS CMS — Bella Dent Clinic
   ───────────────────────────────────────────────────────────────────────
   Як підключити:
   1. Відкрийте Google Таблицю → «Поділитися» → «Усі, хто має посилання» → Готово
   2. Скопіюйте ID з адреси: docs.google.com/spreadsheets/d/ ВОТ-ЦЕЙ-ID /edit
   3. Вставте ID нижче замість PASTE_YOUR_SPREADSHEET_ID_HERE

   Лист «Прайс» — 3 стовпці:
     A: Категорія   B: Назва послуги   C: Ціна

   Лист «Лікарі» — 3 стовпці:
     A: Імʼя   B: Спеціалізація   C: Фото URL

   Як додати фото лікаря:
   1. Завантажте фото на Google Drive
   2. Правою кнопкою → «Поділитися» → «Усі, хто має посилання» → Готово
   3. Натисніть «Копіювати посилання» і вставте його в стовпець C — сайт сам все зробить
   ═══════════════════════════════════════════════════════════════════════ */

(function (win) {

  var SPREADSHEET_ID = '1O5KDSudkOZNILi-P_HUepXzI_ab6PoCvvD7WxsVx6ko';
  var PRICE_SHEET    = 'ПРАЙС';
  var DOCTORS_SHEET  = 'ЛІКАРІ';

  var READY = SPREADSHEET_ID !== 'PASTE_YOUR_SPREADSHEET_ID_HERE';

  function sheetURL(name) {
    return 'https://docs.google.com/spreadsheets/d/' + SPREADSHEET_ID +
           '/gviz/tq?tqx=out:csv&sheet=' + encodeURIComponent(name);
  }

  /* ── CSV parser ── */
  function parseCSV(text) {
    var rows = [], row = [], field = '', i = 0, c;
    text = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
    while (i < text.length) {
      c = text[i];
      if (c === '"') {
        i++;
        while (i < text.length) {
          if (text[i] === '"' && text[i + 1] === '"') { field += '"'; i += 2; }
          else if (text[i] === '"') { i++; break; }
          else { field += text[i++]; }
        }
      } else if (c === ',') {
        row.push(field.trim()); field = ''; i++;
      } else if (c === '\n') {
        row.push(field.trim()); field = '';
        if (row.some(Boolean)) rows.push(row);
        row = []; i++;
      } else {
        field += c; i++;
      }
    }
    if (field || row.length) { row.push(field.trim()); if (row.some(Boolean)) rows.push(row); }
    return rows;
  }

  function col(row, n) { return (row[n] || '').trim(); }

  /* ── Прайс: Категорія | Назва послуги | Ціна ── */
  function toPriceData(rows) {
    if (rows.length < 2) return null;
    var catMap = {}, catOrder = [];
    for (var i = 1; i < rows.length; i++) {
      var r        = rows[i];
      var catName  = col(r, 0);
      var itemName = col(r, 1);
      var itemPrice = col(r, 2);
      if (!catName || !itemName) continue;
      if (!catMap[catName]) {
        catMap[catName] = {
          title: catName,
          slug:  catName.toLowerCase()
                   .replace(/[іїєґ]/g, function(c) { return {і:'i',ї:'yi',є:'ye',ґ:'g'}[c]||c; })
                   .replace(/[^a-z0-9]+/gi, '-')
                   .replace(/^-|-$/g, ''),
          desc:  '',
          items: []
        };
        catOrder.push(catName);
      }
      catMap[catName].items.push({ name: itemName, price: itemPrice });
    }
    return catOrder
      .map(function (name) { return catMap[name]; })
      .filter(function (cat) { return cat.items.length > 0; });
  }

  /* ── Конвертує будь-яке посилання Google Drive у пряме посилання на фото ── */
  function fixPhotoUrl(url) {
    if (!url) return '';
    var id = null;
    var m1 = url.match(/drive\.google\.com\/file\/d\/([^/?]+)/);
    if (m1) id = m1[1];
    var m2 = url.match(/drive\.google\.com\/open\?id=([^&]+)/);
    if (m2) id = m2[1];
    var m3 = url.match(/[?&]id=([^&]+)/);
    if (!id && m3) id = m3[1];
    if (id) return 'https://lh3.googleusercontent.com/d/' + id;
    return url;
  }

  /* ── Лікарі: Імʼя | Спеціалізація | Фото URL ── */
  function toDoctors(rows) {
    if (rows.length < 2) return null;
    var out = [];
    for (var i = 1; i < rows.length; i++) {
      var r    = rows[i];
      var name = col(r, 0);
      var role = col(r, 1);
      if (!name) continue;
      out.push({
        name:    name,
        role:    role,
        photo:   fixPhotoUrl(col(r, 2)),
        isNurse: /медсестра|медична сестра|сестра/i.test(role)
      });
    }
    return out.length ? out : null;
  }

  function fetchSheet(name) {
    return fetch(sheetURL(name)).then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.text().then(parseCSV);
    });
  }

  win.SheetsLoader = {
    ready: READY,
    loadPriceData:   function () {
      if (!READY) return Promise.reject('not configured');
      return fetchSheet(PRICE_SHEET).then(toPriceData);
    },
    loadDoctorsData: function () {
      if (!READY) return Promise.reject('not configured');
      return fetchSheet(DOCTORS_SHEET).then(toDoctors);
    }
  };

})(window);
