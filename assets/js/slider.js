(function () {
  var wrap = document.querySelector('[data-slider]');
  if (!wrap) return;

  var slides = wrap.querySelectorAll('.slide');
  var dots = wrap.querySelectorAll('[data-slider-dot]');
  var btnPrev = wrap.parentElement.querySelector('[data-slider-prev]');
  var btnNext = wrap.parentElement.querySelector('[data-slider-next]');
  var atual = 0;
  var timer = null;
  var total = slides.length;

  function mostrar(i) {
    atual = (i + total) % total;
    slides.forEach(function (s, idx) {
      s.classList.toggle('ativo', idx === atual);
    });
    dots.forEach(function (d, idx) {
      d.classList.toggle('ativo', idx === atual);
    });
  }

  function autoPlay() {
    clearInterval(timer);
    timer = setInterval(function () {
      mostrar(atual + 1);
    }, 6000);
  }

  btnPrev.addEventListener('click', function () { mostrar(atual - 1); autoPlay(); });
  btnNext.addEventListener('click', function () { mostrar(atual + 1); autoPlay(); });
  dots.forEach(function (d) {
    d.addEventListener('click', function () {
      mostrar(parseInt(d.getAttribute('data-slider-dot'), 10));
      autoPlay();
    });
  });

  wrap.addEventListener('mouseenter', function () { clearInterval(timer); });
  wrap.addEventListener('mouseleave', autoPlay);

  mostrar(0);
  autoPlay();
})();