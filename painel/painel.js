/* ============================================================
   PAINEL DE CONTROLE - Portal Ao Vivo
   JavaScript principal: login, tabs, edicao de configs.
   ============================================================ */

(function () {
  "use strict";

  // ---- Login ----
  var campoSenha = document.getElementById("campo-senha");
  var btnLogin = document.getElementById("btn-login");
  var erroLogin = document.getElementById("erro-login");
  var telaLogin = document.getElementById("tela-login");
  var telaPainel = document.getElementById("tela-painel");

  if (sessionStorage.getItem("painel_logado") === "1") {
    telaLogin.style.display = "none";
    telaPainel.style.display = "";
  }

  btnLogin.addEventListener("click", function () {
    if (campoSenha.value === PAINEL_SENHA) {
      sessionStorage.setItem("painel_logado", "1");
      telaLogin.style.display = "none";
      telaPainel.style.display = "";
      carregarTudo();
    } else {
      erroLogin.style.display = "";
      campoSenha.value = "";
      campoSenha.focus();
    }
  });

  campoSenha.addEventListener("keydown", function (e) {
    if (e.key === "Enter") btnLogin.click();
  });

  document.getElementById("btn-sair").addEventListener("click", function () {
    sessionStorage.removeItem("painel_logado");
    location.reload();
  });

  // ---- Tabs ----
  var tabs = document.querySelectorAll(".tab");
  var secoes = document.querySelectorAll(".secao");
  tabs.forEach(function (tab) {
    tab.addEventListener("click", function () {
      tabs.forEach(function (t) { t.classList.remove("ativo"); });
      secoes.forEach(function (s) { s.style.display = "none"; s.classList.remove("ativo"); });
      tab.classList.add("ativo");
      var sec = document.getElementById("sec-" + tab.getAttribute("data-tab"));
      if (sec) { sec.style.display = ""; sec.classList.add("ativo"); }
    });
  });

  // ---- Link Actions ----
  var linkActions = document.getElementById("link-actions");
  if (linkActions) linkActions.href = GITHUB_ACTIONS;

  // ---- Helpers ----
  function carregarJSON(url, cb) {
    var xhr = new XMLHttpRequest();
    xhr.open("GET", url, true);
    xhr.onreadystatechange = function () {
      if (xhr.readyState === 4) {
        if (xhr.status === 200) cb(null, xhr.responseText);
        else cb(new Error("HTTP " + xhr.status));
      }
    };
    xhr.send();
  }

  function copiarTextArea(idTextarea, idMsg) {
    var ta = document.getElementById(idTextarea);
    ta.select();
    document.execCommand("copy");
    var msg = document.getElementById(idMsg);
    if (msg) { msg.style.display = ""; setTimeout(function () { msg.style.display = "none"; }, 2000); }
  }

  function formatarJSON(texto) {
    try { return JSON.stringify(JSON.parse(texto), null, 2); }
    catch (e) { return texto; }
  }

  // ============================================================
  // FONTES
  // ============================================================
  var fontesDados = [];

  function carregarFontes() {
    document.getElementById("status-fontes").textContent = "Carregando...";
    carregarJSON(RAW_BASE + ARQUIVOS.fonts, function (err, texto) {
      if (err) { document.getElementById("status-fontes").textContent = "Erro ao carregar"; return; }
      try {
        fontesDados = JSON.parse(texto);
        renderizarFontes();
        gerarJSONFontes();
        document.getElementById("status-fontes").textContent = fontesDados.length + " fonte(s) carregada(s)";
      } catch (e) {
        document.getElementById("status-fontes").textContent = "Erro de JSON";
      }
    });
  }

  function renderizarFontes() {
    var container = document.getElementById("lista-fontes");
    container.innerHTML = "";
    fontesDados.forEach(function (f, i) {
      var div = document.createElement("div");
      div.className = "fonte-item";
      div.innerHTML =
        '<div class="fonte-campos">' +
          '<input type="text" placeholder="Nome" value="' + (f.nome || "") + '" data-i="' + i + '" data-campo="nome">' +
          '<select data-i="' + i + '" data-campo="tipo">' +
            '<option value="rss"' + (f.tipo === "rss" ? " selected" : "") + '>RSS</option>' +
            '<option value="sitemap"' + (f.tipo === "sitemap" ? " selected" : "") + '>Sitemap</option>' +
            '<option value="scrape"' + (f.tipo === "scrape" ? " selected" : "") + '>Scrape</option>' +
          '</select>' +
          '<input type="text" placeholder="URL da fonte" value="' + (f.url || "") + '" data-i="' + i + '" data-campo="url" class="fonte-campos-full">' +
          '<input type="text" placeholder="Link pattern (ex: {url}noticia/{id})" value="' + (f.link_pattern || "") + '" data-i="' + i + '" data-campo="link_pattern" class="fonte-campos-full">' +
        '</div>' +
        '<div class="fonte-acoes">' +
          '<button class="btn btn-perigo btn-pequeno remover-fonte" data-i="' + i + '">Remover</button>' +
        '</div>';
      container.appendChild(div);
    });

    container.querySelectorAll("input, select").forEach(function (el) {
      el.addEventListener("change", function () {
        var i = parseInt(el.getAttribute("data-i"));
        var campo = el.getAttribute("data-campo");
        fontesDados[i][campo] = el.value;
        gerarJSONFontes();
      });
    });
    container.querySelectorAll(".remover-fonte").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var i = parseInt(btn.getAttribute("data-i"));
        fontesDados.splice(i, 1);
        renderizarFontes();
        gerarJSONFontes();
      });
    });
  }

  function gerarJSONFontes() {
    document.getElementById("json-fontes").value = JSON.stringify(fontesDados, null, 2);
  }

  document.getElementById("btn-add-fonte").addEventListener("click", function () {
    fontesDados.push({ nome: "", tipo: "rss", url: "", link_pattern: "" });
    renderizarFontes();
    gerarJSONFontes();
  });
  document.getElementById("btn-copiar-fontes").addEventListener("click", function () { copiarTextArea("json-fontes", "msg-fontes"); });
  document.getElementById("btn-abrir-fontes").addEventListener("click", function () { window.open(GITHUB_EDIT + ARQUIVOS.fonts, "_blank"); });

  // ============================================================
  // BANNERS
  // ============================================================
  var espacos = ["topo", "esquerda", "lateral", "materia", "rodape"];
  var adsYml = {};
  var adsImagens = {};

  function carregarBanners() {
    document.getElementById("status-banners").textContent = "Carregando...";
    var pendentes = 2;
    function done() {
      pendentes--;
      if (pendentes <= 0) {
        renderizarBanners();
        gerarJSONBanners();
        document.getElementById("status-banners").textContent = "Carregado";
      }
    }
    carregarJSON(RAW_BASE + ARQUIVOS.ads_imagens, function (err, t) {
      if (!err) try { adsImagens = JSON.parse(t); } catch(e) {}
      done();
    });
    carregarJSON(RAW_BASE + ARQUIVOS.ads_yml, function (err, t) {
      if (!err) {
        var lines = t.split("\n");
        var current = "";
        for (var li = 0; li < lines.length; li++) {
          var line = lines[li].replace(/\s+$/, "");
          if (/^[a-z]+:/.test(line) && !line.startsWith("#")) {
            current = line.split(":")[0].trim();
          }
          if (current && line.indexOf("ativo:") > -1) {
            adsYml[current] = line.split("ativo:")[1].trim() === "true";
          }
        }
      }
      done();
    });
  }

  function renderizarBanners() {
    var container = document.getElementById("lista-espacos");
    container.innerHTML = "";
    espacos.forEach(function (e) {
      var ativo = adsYml[e] || false;
      var imagens = adsImagens["ads_" + e] || [];
      var div = document.createElement("div");
      div.className = "espaco-item" + (ativo ? "" : " inativo");
      div.innerHTML =
        '<div class="espaco-header">' +
          '<h3>' + e + '</h3>' +
          '<label class="espaco-toggle"><input type="checkbox" data-espaco="' + e + '"' + (ativo ? " checked" : "") + '> Ativo</label>' +
        '</div>' +
        '<div class="espaco-imagens" data-espaco="' + e + '">' +
          imagens.map(function (img) {
            return '<span class="espaco-img-tag">' + img + ' <span class="remover" data-espaco="' + e + '" data-img="' + img + '">&times;</span></span>';
          }).join("") +
        '</div>' +
        '<div class="espaco-add">' +
          '<input type="text" placeholder="nome-da-imagem.jpg" data-espaco="' + e + '">' +
          '<button class="btn btn-claro btn-pequeno adicionar-img" data-espaco="' + e + '">Adicionar</button>' +
        '</div>';
      container.appendChild(div);
    });

    container.querySelectorAll("input[type=checkbox]").forEach(function (cb) {
      cb.addEventListener("change", function () {
        adsYml[cb.getAttribute("data-espaco")] = cb.checked;
        renderizarBanners();
        gerarJSONBanners();
      });
    });
    container.querySelectorAll(".remover").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var e = btn.getAttribute("data-espaco");
        var img = btn.getAttribute("data-img");
        var lista = adsImagens["ads_" + e] || [];
        var idx = lista.indexOf(img);
        if (idx > -1) lista.splice(idx, 1);
        adsImagens["ads_" + e] = lista;
        renderizarBanners();
        gerarJSONBanners();
      });
    });
    container.querySelectorAll(".adicionar-img").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var e = btn.getAttribute("data-espaco");
        var input = container.querySelector('.espaco-add input[data-espaco="' + e + '"]');
        var nome = input.value.trim();
        if (!nome) return;
        if (!adsImagens["ads_" + e]) adsImagens["ads_" + e] = [];
        if (adsImagens["ads_" + e].indexOf(nome) === -1) adsImagens["ads_" + e].push(nome);
        input.value = "";
        renderizarBanners();
        gerarJSONBanners();
      });
    });
  }

  function gerarJSONBanners() {
    document.getElementById("json-banners").value = JSON.stringify(adsImagens, null, 2);
  }

  document.getElementById("btn-copiar-banners").addEventListener("click", function () { copiarTextArea("json-banners", "msg-banners"); });
  document.getElementById("btn-abrir-banners").addEventListener("click", function () { window.open(GITHUB_EDIT + ARQUIVOS.ads_imagens, "_blank"); });

  // ============================================================
  // HASHTAGS
  // ============================================================
  var campoHashtags = document.getElementById("lista-hashtags");

  function carregarHashtags() {
    document.getElementById("status-hashtags").textContent = "Carregando...";
    carregarJSON(RAW_BASE + ARQUIVOS.hashtags, function (err, t) {
      if (err) { document.getElementById("status-hashtags").textContent = "Erro ao carregar"; return; }
      try {
        var obj = JSON.parse(t);
        campoHashtags.value = (obj.hashtags || []).join("\n");
        document.getElementById("status-hashtags").textContent = (obj.hashtags || []).length + " hashtag(s)";
        gerarJSONHashtags();
      } catch (e) { document.getElementById("status-hashtags").textContent = "Erro de JSON"; }
    });
  }

  function gerarJSONHashtags() {
    var linhas = campoHashtags.value.split("\n").map(function (l) { return l.trim(); }).filter(Boolean);
    document.getElementById("json-hashtags").value = JSON.stringify({ hashtags: linhas }, null, 2);
  }

  campoHashtags.addEventListener("input", gerarJSONHashtags);
  document.getElementById("btn-copiar-hashtags").addEventListener("click", function () { copiarTextArea("json-hashtags", "msg-hashtags"); });
  document.getElementById("btn-abrir-hashtags").addEventListener("click", function () { window.open(GITHUB_EDIT + ARQUIVOS.hashtags, "_blank"); });

  // ============================================================
  // TEMAS
  // ============================================================
  var campoTemasEntrada = document.getElementById("json-temas-entrada");
  var campoTemasSaida = document.getElementById("json-temas-saida");

  function carregarTemas() {
    document.getElementById("status-temas").textContent = "Carregando...";
    carregarJSON(RAW_BASE + ARQUIVOS.themes, function (err, t) {
      if (err) { document.getElementById("status-temas").textContent = "Erro ao carregar"; return; }
      campoTemasEntrada.value = formatarJSON(t);
      campoTemasSaida.value = formatarJSON(t);
      document.getElementById("status-temas").textContent = "Carregado";
    });
  }

  document.getElementById("btn-validar-temas").addEventListener("click", function () {
    try {
      var obj = JSON.parse(campoTemasEntrada.value);
      campoTemasSaida.value = JSON.stringify(obj, null, 2);
      document.getElementById("status-temas").textContent = "Valido!";
    } catch (e) {
      document.getElementById("status-temas").textContent = "ERRO: " + e.message;
    }
  });

  document.getElementById("btn-copiar-temas").addEventListener("click", function () { copiarTextArea("json-temas-saida", "msg-temas"); });
  document.getElementById("btn-abrir-temas").addEventListener("click", function () { window.open(GITHUB_EDIT + ARQUIVOS.themes, "_blank"); });

  // ============================================================
  // CARREGAR TUDO
  // ============================================================
  function carregarTudo() {
    carregarFontes();
    carregarBanners();
    carregarHashtags();
    carregarTemas();
  }

})();
