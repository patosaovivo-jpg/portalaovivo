/* ============================================================
   PAINEL DE ADMIN - Portal Ao Vivo
   Gerencia a lista de hashtags (copiar/colar manual no GitHub)
   ============================================================ */

var estado = { senhaOk: false };

var DICAS = [
  "patosdeminas", "prefeituradepatos", "camarapatosdeminas", "acipatos",
  "unipam", "iftmpatos", "sebraeminas", "fiemg", "apae", "urt", "mamore",
  "fenamilho", "coopatos", "ligapatense", "sicoob", "expocaccer",
  "patrocinio", "coromandel", "serradosalitre", "altoparanaiba",
  "lagoaformosa", "presidenteolegario", "vazante", "ibiá", "sãogotardo",
  "montecarmelo", "araxa", "rioparanaiba", "patosdeminasmg", "triangulomineiro"
];

var telaLogin = document.getElementById("tela-login");
var telaPainel = document.getElementById("tela-painel");

function carregarDicas() {
  var lista = document.getElementById("lista-dicas");
  lista.innerHTML = "";
  DICAS.forEach(function (dica) {
    var li = document.createElement("li");
    li.textContent = "#" + dica;
    li.addEventListener("click", function () {
      adicionarHashtag(dica);
    });
    lista.appendChild(li);
  });
}

function adicionarHashtag(tag) {
  var campo = document.getElementById("lista-hashtags");
  var atual = campo.value.split("\n").map(function (t) { return t.trim().toLowerCase().replace(/^#/, ""); }).filter(Boolean);
  if (atual.indexOf(tag.toLowerCase()) === -1) {
    atual.push(tag.toLowerCase());
  }
  campo.value = atual.join("\n");
  atualizarStatus("Hashtag #" + tag + " adicionada à lista. Gere o JSON para salvar.");
}

function atualizarStatus(msg) {
  var el = document.getElementById("status-carregar");
  if (el) { el.textContent = msg; }
}

function lerHashtagsDoGitHub() {
  atualizarStatus("Carregando lista do GitHub...");
  var url = "https://raw.githubusercontent.com/" + REPO_OWNER + "/" + REPO_NAME + "/main/" + HASHTAGS_PATH;
  return fetch(url)
    .then(function (r) {
      if (!r.ok) { throw new Error("status " + r.status); }
      return r.json();
    })
    .then(function (data) {
      var tags = (data.hashtags || data || []).filter(function (t) { return t; });
      document.getElementById("lista-hashtags").value = tags.join("\n");
      atualizarStatus("Lista carregada: " + tags.length + " hashtag(s) monitorada(s).");
    })
    .catch(function (e) {
      atualizarStatus("Não foi possível carregar do GitHub (" + e.message + "). Use a lista abaixo.");
      document.getElementById("lista-hashtags").value = "patosdeminas\nacipatos\nunipam";
    });
}

function gerarJson() {
  var campo = document.getElementById("lista-hashtags");
  var tags = campo.value.split("\n").map(function (t) { return t.trim().toLowerCase().replace(/^#/, ""); }).filter(Boolean);
  var unicas = [];
  tags.forEach(function (t) { if (unicas.indexOf(t) === -1) { unicas.push(t); } });
  var json = JSON.stringify({ hashtags: unicas }, null, 2);
  document.getElementById("json-saida").value = json;
  return json;
}

function copiarJson() {
  var campo = document.getElementById("json-saida");
  campo.select();
  campo.setSelectionRange(0, 99999);
  try {
    document.execCommand("copy");
  } catch (e) {
    if (navigator.clipboard) {
      navigator.clipboard.writeText(campo.value).catch(function () {});
    }
  }
  var msg = document.getElementById("msg-copiado");
  msg.style.display = "block";
  setTimeout(function () { msg.style.display = "none"; }, 2500);
}

/* ---------- LOGIN ---------- */
document.getElementById("btn-login").addEventListener("click", function () {
  var senha = document.getElementById("campo-senha").value;
  if (senha === (typeof ADMIN_PASSWORD !== "undefined" ? ADMIN_PASSWORD : "")) {
    telaLogin.style.display = "none";
    telaPainel.style.display = "block";
    lerHashtagsDoGitHub();
    carregarDicas();
  } else {
    document.getElementById("erro-login").style.display = "block";
  }
});
document.getElementById("campo-senha").addEventListener("keydown", function (e) {
  if (e.key === "Enter") { document.getElementById("btn-login").click(); }
});

document.getElementById("btn-sair").addEventListener("click", function () {
  telaPainel.style.display = "none";
  telaLogin.style.display = "flex";
  document.getElementById("campo-senha").value = "";
  document.getElementById("erro-login").style.display = "none";
});

/* ---------- AÇÕES ---------- */
document.getElementById("btn-gerar").addEventListener("click", function () {
  gerarJson();
  copiarJson();
});

document.getElementById("btn-copiar").addEventListener("click", copiarJson);

document.getElementById("btn-recarga").addEventListener("click", lerHashtagsDoGitHub);

document.getElementById("btn-abrir-github").addEventListener("click", function () {
  gerarJson();
  var url = "https://github.com/" + REPO_OWNER + "/" + REPO_NAME + "/blob/main/" + HASHTAGS_PATH;
  window.open(url, "_blank");
});

/* inicia */
if (telaLogin && document.getElementById("campo-senha")) {
  document.getElementById("campo-senha").focus();
}
