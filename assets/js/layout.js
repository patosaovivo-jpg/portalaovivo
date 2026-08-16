/* ============================================================
   PORTAL AO VIVO - LAYOUT SEMI-DINÂMICO
   Puxa header, rodapé e colunas laterais de fragmentos únicos
   em /parts/. Edite um arquivo lá e vale para todo o site.
   Cada elemento com data-fragment é substituído pelo conteúdo
   do arquivo indicado.
   ============================================================ */
(function () {
  function carregarFragmentos() {
    document.querySelectorAll('[data-fragment]').forEach(function (alvo) {
      var url = alvo.getAttribute('data-fragment');
      if (!url) return;
      fetch(url)
        .then(function (res) { return res.text(); })
        .then(function (html) { alvo.outerHTML = html; })
        .catch(function () {});
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', carregarFragmentos);
  } else {
    carregarFragmentos();
  }
})();
