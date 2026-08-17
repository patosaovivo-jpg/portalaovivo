/* ============================================================
   PORTAL AO VIVO - SISTEMA DE PUBLICIDADE
   Carrega imagens do manifesto ads-imagens.json.
   Para adicionar um anuncio: coloque a imagem na pasta
   (ex: ads_topo/) e adicione o nome no manifesto JSON.
   ============================================================ */

var ADS_IMAGENS = {};

(function() {
  var xhr = new XMLHttpRequest();
  xhr.open('GET', '/assets/js/ads-imagens.json', true);
  xhr.onreadystatechange = function() {
    if (xhr.readyState === 4 && xhr.status === 200) {
      try {
        ADS_IMAGENS = JSON.parse(xhr.responseText);
      } catch(e) {
        console.warn('[ADS] Erro ao ler manifesto:', e);
      }
    }
  };
  xhr.send();
})();

function ADS_aleatorio(lista) {
  return lista[Math.floor(Math.random() * lista.length)];
}

function ADS_mostrar(pasta, idElemento) {
  var el = document.getElementById(idElemento);
  if (!el) return;
  var lista = ADS_IMAGENS[pasta];
  if (!lista || !lista.length) return;
  var nome = ADS_aleatorio(lista);
  var link = document.createElement('a');
  link.href = pasta + '/' + nome;
  link.target = '_blank';
  var img = document.createElement('img');
  img.src = pasta + '/' + nome;
  img.alt = 'Publicidade';
  link.appendChild(img);
  el.innerHTML = '';
  el.appendChild(link);
}
