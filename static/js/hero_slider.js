(() => {
  const hero = document.querySelector('.hero-slider');
  if (!hero) return;

  const imagesRaw = hero.getAttribute('data-hero-images') || '[]';
  let images = [];
  try {
    images = JSON.parse(imagesRaw);
  } catch {
    images = [];
  }
  if (!Array.isArray(images) || images.length === 0) return;

  const layerA = hero.querySelector('.hero-bg.hero-bg-a');
  const layerB = hero.querySelector('.hero-bg.hero-bg-b');
  if (!layerA || !layerB) return;

  let index = 0;
  let showingA = true;

  const setBg = (el, url) => {
    el.style.backgroundImage = `url("${url}")`;
  };

  setBg(layerA, images[0]);
  setBg(layerB, images[1 % images.length]);
  layerA.classList.add('is-visible');

  const intervalMs = 6000;

  const tick = () => {
    index = (index + 1) % images.length;
    const nextIndex = (index + 1) % images.length;

    const incoming = showingA ? layerB : layerA;
    const outgoing = showingA ? layerA : layerB;

    setBg(incoming, images[index]);
    incoming.classList.add('is-visible');
    outgoing.classList.remove('is-visible');

    showingA = !showingA;

    setTimeout(() => {
      setBg(outgoing, images[nextIndex]);
    }, 350);
  };

  setInterval(tick, intervalMs);
})();

