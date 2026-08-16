/* ============================================================
   PORTAL AO VIVO - SISTEMA DE PUBLICIDADE
   Mostra uma IMAGEM ALEATÓRIA de cada pasta de anúncios.
   Para adicionar um anúncio: coloque a imagem na pasta (ex:
   ads_topo/) e acrescente o nome do arquivo na lista abaixo.
   ============================================================ */
var ADS_IMAGENS = {
  'ads_topo':      ['topo1.svg', 'topo2.svg'],
  'ads_esquerda':  ['esquerda1.svg', 'esquerda2.svg'],
  'ads_lateral':   ['lateral1.svg', 'lateral2.svg'],
  'ads_materia':   ['materia1.svg', 'materia2.svg'],
  'ads_rodape':    ['rodape1.svg', 'rodape2.svg']
};

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
