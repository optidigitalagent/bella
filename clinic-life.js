(function () {
  'use strict';

  var apiBase = String(window.BELLA_API_BASE || '').replace(/\/$/, '');
  var section = document.getElementById('clinic-life');
  var grid = document.getElementById('clinic-life-grid');
  var dots = document.getElementById('clinic-life-dots');
  var form = document.getElementById('lead-form');
  var carouselBound = false;

  function apiUrl(path) { return apiBase + path; }

  function setText(element, value) {
    element.textContent = String(value == null ? '' : value);
    return element;
  }

  function optimizedImageUrl(url, featured) {
    if (!/\/image\/upload\//.test(url) || !/^https:\/\/res\.cloudinary\.com\//.test(url)) return url;
    return url.replace('/image/upload/', '/image/upload/f_auto,q_auto,c_limit,w_' + (featured ? '1400' : '900') + '/');
  }

  function formatDate(value) {
    var date = new Date(value);
    if (Number.isNaN(date.getTime())) return '';
    var dayMonth = new Intl.DateTimeFormat('uk-UA', { day: 'numeric', month: 'long' }).format(date);
    return dayMonth + ' ' + date.getFullYear();
  }

  function validNews(item) {
    return item && typeof item.id === 'string' && typeof item.title === 'string' &&
      typeof item.description === 'string' && ['image', 'video'].indexOf(item.mediaType) !== -1 &&
      typeof item.mediaUrl === 'string' && /^https:\/\//.test(item.mediaUrl) && typeof item.publishedAt === 'string';
  }

  function createMedia(item, featured) {
    var wrap = document.createElement('div');
    wrap.className = 'clinic-life-media';
    if (item.mediaType === 'video') {
      var video = document.createElement('video');
      video.src = item.mediaUrl;
      video.controls = true;
      video.preload = 'metadata';
      video.setAttribute('playsinline', '');
      video.setAttribute('aria-label', item.title);
      wrap.appendChild(video);
    } else {
      var image = document.createElement('img');
      image.src = optimizedImageUrl(item.mediaUrl, featured);
      image.alt = item.title;
      image.loading = 'lazy';
      image.decoding = 'async';
      image.width = featured ? 1400 : 900;
      image.height = featured ? 875 : 563;
      wrap.appendChild(image);
    }
    return wrap;
  }

  function createCard(item, index) {
    var card = document.createElement('article');
    card.className = 'clinic-life-card';
    card.dataset.newsId = item.id;
    card.appendChild(createMedia(item, index === 0));

    var content = document.createElement('div');
    content.className = 'clinic-life-content';
    var date = setText(document.createElement('time'), formatDate(item.publishedAt));
    date.className = 'clinic-life-date';
    date.dateTime = item.publishedAt;
    var title = setText(document.createElement('h3'), item.title);
    title.className = 'clinic-life-title';
    title.id = 'clinic-life-news-title-' + index;
    card.setAttribute('aria-labelledby', title.id);
    var description = setText(document.createElement('p'), item.description);
    description.className = 'clinic-life-description';
    description.id = 'clinic-life-description-' + index;
    content.appendChild(date);
    content.appendChild(title);
    content.appendChild(description);

    var hasInstagram = typeof item.instagramUrl === 'string' && /^https:\/\/(www\.)?instagram\.com\//.test(item.instagramUrl);
    var isLong = item.description.length > (index === 0 ? 280 : 150);
    if (hasInstagram) {
      var link = setText(document.createElement('a'), 'ЧИТАТИ БІЛЬШЕ');
      link.className = 'clinic-life-cta';
      link.href = item.instagramUrl;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.setAttribute('aria-label', 'Читати більше: ' + item.title);
      content.appendChild(link);
    } else if (isLong) {
      var button = setText(document.createElement('button'), 'ЧИТАТИ БІЛЬШЕ');
      button.type = 'button';
      button.className = 'clinic-life-cta';
      button.setAttribute('aria-expanded', 'false');
      button.setAttribute('aria-controls', description.id);
      button.addEventListener('click', function () {
        var expanded = description.classList.toggle('is-expanded');
        button.setAttribute('aria-expanded', expanded ? 'true' : 'false');
        button.textContent = expanded ? 'ЗГОРНУТИ' : 'ЧИТАТИ БІЛЬШЕ';
      });
      content.appendChild(button);
    }
    card.appendChild(content);
    return card;
  }

  function updateActiveDot(index) {
    dots.querySelectorAll('.clinic-life-dot').forEach(function (dot, dotIndex) {
      var active = dotIndex === index;
      dot.classList.toggle('is-active', active);
      dot.setAttribute('aria-current', active ? 'true' : 'false');
    });
  }

  function buildDots(items) {
    dots.replaceChildren();
    dots.hidden = items.length === 0;
    items.forEach(function (_, index) {
      var dot = document.createElement('button');
      dot.type = 'button';
      dot.className = 'clinic-life-dot' + (index === 0 ? ' is-active' : '');
      dot.setAttribute('aria-label', 'Новина ' + (index + 1));
      dot.setAttribute('aria-current', index === 0 ? 'true' : 'false');
      dot.addEventListener('click', function () {
        var card = grid.children[index];
        if (card) grid.scrollTo({ left: card.offsetLeft - grid.offsetLeft, behavior: 'smooth' });
      });
      dots.appendChild(dot);
    });
  }

  function renderStatus(message, state) {
    var empty = document.createElement('div');
    empty.className = 'clinic-life-empty';
    empty.dataset.state = state;
    empty.setAttribute('role', 'status');
    var rule = document.createElement('span');
    rule.className = 'clinic-life-empty-rule';
    rule.setAttribute('aria-hidden', 'true');
    empty.appendChild(rule);
    empty.appendChild(setText(document.createElement('p'), message));
    grid.replaceChildren(empty);
    grid.dataset.count = '0';
    grid.setAttribute('aria-busy', 'false');
    dots.replaceChildren();
    dots.hidden = true;
  }

  function bindCarousel() {
    if (carouselBound) return;
    carouselBound = true;
    var scheduled = false;
    grid.addEventListener('scroll', function () {
      if (scheduled || window.innerWidth > 900) return;
      scheduled = true;
      requestAnimationFrame(function () {
        scheduled = false;
        var current = 0;
        var distance = Infinity;
        Array.prototype.forEach.call(grid.children, function (card, index) {
          var nextDistance = Math.abs(card.offsetLeft - grid.offsetLeft - grid.scrollLeft);
          if (nextDistance < distance) { distance = nextDistance; current = index; }
        });
        updateActiveDot(current);
      });
    }, { passive: true });
  }

  async function loadNews() {
    if (!section || !grid || !dots) return;
    section.hidden = false;
    if (!apiBase) {
      renderStatus('Новини тимчасово недоступні. Завітайте, будь ласка, трохи пізніше.', 'error');
      console.warn('Bella Dent Clinic Life: BELLA_API_BASE is not configured.');
      return;
    }
    try {
      var response = await fetch(apiUrl('/api/news'), { headers: { Accept: 'application/json' }, cache: 'no-store' });
      if (!response.ok) throw new Error('News API returned HTTP ' + response.status);
      var payload = await response.json();
      if (!Array.isArray(payload)) throw new Error('News API payload must be an array');
      var items = payload.filter(validNews).slice(0, 3);
      if (!items.length) {
        if (payload.length) throw new Error('News API payload contains no valid public items');
        renderStatus('Незабаром тут зʼявляться новини та події клініки.', 'empty');
        return;
      }
      grid.replaceChildren();
      grid.setAttribute('aria-busy', 'false');
      grid.dataset.count = String(items.length);
      items.forEach(function (item, index) { grid.appendChild(createCard(item, index)); });
      buildDots(items);
      bindCarousel();
    } catch (error) {
      renderStatus('Новини тимчасово недоступні. Завітайте, будь ласка, трохи пізніше.', 'error');
      console.error('Bella Dent Clinic Life failed to load:', error.message);
    }
  }

  function makeRequestId() {
    if (window.crypto && typeof window.crypto.randomUUID === 'function') return window.crypto.randomUUID();
    return 'lead_' + Date.now() + '_' + Math.random().toString(36).slice(2);
  }

  function setFormStatus(message, type) {
    var status = document.getElementById('lead-form-status');
    if (!status) return;
    status.textContent = message;
    status.className = 'lead-form-status' + (type ? ' is-' + type : '');
  }

  function bindLeadForm() {
    if (!form) return;
    form.addEventListener('submit', async function (event) {
      event.preventDefault();
      if (!form.reportValidity()) return;
      if (!apiBase) {
        setFormStatus('Онлайн-запис тимчасово недоступний. Зателефонуйте нам за номером 096 430 37 19.', 'error');
        return;
      }
      var submit = form.querySelector('[type="submit"]');
      var formData = new FormData(form);
      var requestId = form.dataset.pendingRequestId || makeRequestId();
      form.dataset.pendingRequestId = requestId;
      var payload = {
        name: String(formData.get('name') || ''),
        phone: String(formData.get('phone') || ''),
        comment: String(formData.get('comment') || ''),
        website: String(formData.get('website') || ''),
        requestId: requestId
      };
      submit.disabled = true;
      setFormStatus('Надсилаємо заявку…', '');
      try {
        var response = await fetch(apiUrl('/api/leads'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
          body: JSON.stringify(payload)
        });
        if (!response.ok) throw new Error('Lead API returned HTTP ' + response.status);
        setFormStatus('Дякуємо! Заявку передано адміністратору.', 'success');
        form.reset();
        delete form.dataset.pendingRequestId;
      } catch (error) {
        console.error('Bella Dent lead submission failed:', error.message);
        setFormStatus('Не вдалося підтвердити відправлення. Спробуйте ще раз або зателефонуйте нам.', 'error');
      } finally {
        submit.disabled = false;
      }
    });
  }

  bindLeadForm();
  loadNews();
})();
