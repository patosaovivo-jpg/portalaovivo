/* ============================================================
   PAINEL DE ADMIN - Portal Ao Vivo
   Editor de matérias + gerenciador de hashtags.
   ============================================================ */

(function () {
  "use strict";

  var telaLogin = document.getElementById("tela-login");
  var telaPainel = document.getElementById("tela-painel");

  // ============================================================
  // LOGIN
  // ============================================================
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
    if (e.key === "Enter") document.getElementById("btn-login").click();
  });

  document.getElementById("btn-sair").addEventListener("click", function () {
    telaPainel.style.display = "none";
    telaLogin.style.display = "flex";
    document.getElementById("campo-senha").value = "";
    document.getElementById("erro-login").style.display = "none";
  });

  // ============================================================
  // TABS
  // ============================================================
  var adminTabs = document.querySelectorAll(".admin-tab");
  var secoesAdmin = document.querySelectorAll(".secao-admin");

  adminTabs.forEach(function (tab) {
    tab.addEventListener("click", function () {
      adminTabs.forEach(function (t) { t.classList.remove("ativo"); });
      secoesAdmin.forEach(function (s) { s.style.display = "none"; s.classList.remove("ativo"); });
      tab.classList.add("ativo");
      var sec = document.getElementById("sec-" + tab.getAttribute("data-tab"));
      if (sec) { sec.style.display = ""; sec.classList.add("ativo"); }
    });
  });

  // ============================================================
  // HELPERS
  // ============================================================
  function copiarCampo(idCampo, idMsg) {
    var campo = document.getElementById(idCampo);
    campo.select();
    campo.setSelectionRange(0, 99999);
    try {
      document.execCommand("copy");
    } catch (e) {
      if (navigator.clipboard) {
        navigator.clipboard.writeText(campo.value).catch(function () {});
      }
    }
    if (idMsg) {
      var msg = document.getElementById(idMsg);
      msg.style.display = "block";
      setTimeout(function () { msg.style.display = "none"; }, 2500);
    }
  }

  function slugify(texto) {
    return texto
      .toLowerCase()
      .normalize("NFD").replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-z0-9\s-]/g, "")
      .replace(/\s+/g, "-")
      .replace(/-+/g, "-")
      .replace(/^-|-$/g, "")
      .substring(0, 80);
  }

  function dataHoje() {
    var d = new Date();
    var y = d.getFullYear();
    var m = String(d.getMonth() + 1).padStart(2, "0");
    var dia = String(d.getDate()).padStart(2, "0");
    return y + "-" + m + "-" + dia;
  }

  function agoraUTC() {
    var d = new Date();
    return d.toISOString().replace("T", " ").substring(0, 19) + " +0000";
  }

  function extrairYoutube(texto) {
    if (!texto) return null;
    texto = texto.trim();
    // Already embed URL
    if (texto.indexOf("youtube.com/embed/") > -1) {
      var m = texto.match(/youtube\.com\/embed\/([^?&/]+)/);
      return m ? m[1] : null;
    }
    // watch URL
    if (texto.indexOf("youtube.com/watch") > -1) {
      var m2 = texto.match(/[?&]v=([^&]+)/);
      return m2 ? m2[1] : null;
    }
    // youtu.be short URL
    if (texto.indexOf("youtu.be/") > -1) {
      var m3 = texto.match(/youtu\.be\/([^?&/]+)/);
      return m3 ? m3[3] : null;
    }
    // Just the ID (11 chars)
    if (/^[A-Za-z0-9_-]{11}$/.test(texto)) return texto;
    return null;
  }

  // ============================================================
  // NOVA MATÉRIA
  // ============================================================
  var campoTitulo = document.getElementById("materia-titulo");
  var campoTexto = document.getElementById("materia-texto");
  var campoImagem = document.getElementById("materia-imagem");
  var campoYoutube = document.getElementById("materia-youtube");
  var campoTema = document.getElementById("materia-tema");
  var campoFonteNome = document.getElementById("materia-fonte-nome");
  var campoFonteLink = document.getElementById("materia-fonte-link");
  var campoResumo = document.getElementById("materia-resumo");
  var previewMarkdown = document.getElementById("preview-materia");
  var previewFilename = document.getElementById("preview-filename");

  function gerarMarkdownMateria() {
    var titulo = campoTitulo.value.trim();
    var texto = campoTexto.value.trim();
    if (!titulo || !texto) {
      alert("Preencha pelo menos o título e o texto da matéria.");
      return null;
    }

    var slug = slugify(titulo);
    var data = dataHoje();
    var filename = data + "-" + slug + ".md";
    var datetime = agoraUTC();
    var imagem = campoImagem.value.trim();
    var youtubeId = extrairYoutube(campoYoutube.value);
    var tema = campoTema.value;
    var fonteNome = campoFonteNome.value.trim();
    var fonteLink = campoFonteLink.value.trim();
    var resumo = campoResumo.value.trim();

    // Auto-resumo se vazio
    if (!resumo) {
      resumo = texto.replace(/\n+/g, " ").substring(0, 155).trim();
      if (resumo.length >= 150) resumo = resumo.substring(0, 150) + "...";
    }

    // Front matter
    var fm = "---\n";
    fm += 'title: "' + titulo.replace(/"/g, '\\"') + '"\n';
    fm += "date: " + datetime + "\n";
    if (imagem) {
      fm += "image: " + imagem + "\n";
    }
    fm += "tema: " + tema + "\n";
    if (fonteNome) {
      fm += 'fonte: "' + fonteNome.replace(/"/g, '\\"') + '"\n';
    }
    if (fonteLink) {
      fm += 'fonte_link: "' + fonteLink.replace(/"/g, '\\"') + '"\n';
    }
    fm += 'resumo: "' + resumo.replace(/"/g, '\\"') + '"\n';
    fm += "---\n\n";

    // Body
    var body = "";
    // Split paragraphs
    var paragrafos = texto.split(/\n\s*\n/);
    paragrafos.forEach(function (p) {
      p = p.trim();
      if (p) body += p + "\n\n";
    });

    // YouTube embed
    if (youtubeId) {
      body += '<div class="video-container">\n';
      body += '<iframe width="100%" height="400" src="https://www.youtube.com/embed/' + youtubeId + '" frameborder="0" allowfullscreen></iframe>\n';
      body += '</div>\n\n';
    }

    // Fonte link no final
    if (fonteNome && fonteLink) {
      body += "*Leia a matéria completa na fonte original:* [" + fonteNome + "](" + fonteLink + ")\n\n";
    }

    body += "---\n\n*Conteúdo publicado pelo Portal Ao Vivo.*\n";

    var markdown = fm + body;

    // Update preview
    previewMarkdown.value = markdown;
    previewFilename.textContent = "Arquivo: _posts/" + filename;

    return { filename: filename, markdown: markdown };
  }

  // Preview live
  [campoTitulo, campoTexto, campoImagem, campoYoutube, campoTema, campoFonteNome, campoFonteLink, campoResumo].forEach(function (el) {
    el.addEventListener("input", function () {
      if (campoTitulo.value.trim() && campoTexto.value.trim()) {
        gerarMarkdownMateria();
      }
    });
  });

  document.getElementById("btn-gerar-materia").addEventListener("click", function () {
    var result = gerarMarkdownMateria();
    if (result) copiarCampo("preview-materia", "msg-materia-copiado");
  });

  document.getElementById("btn-copiar-materia").addEventListener("click", function () {
    copiarCampo("preview-materia", "msg-materia-copiado");
  });

  document.getElementById("btn-abrir-github-materia").addEventListener("click", function () {
    var result = gerarMarkdownMateria();
    if (!result) return;
    var url = "https://github.com/" + REPO_OWNER + "/" + REPO_NAME + "/new/main?filename=_posts/" + result.filename;
    window.open(url, "_blank");
  });

  document.getElementById("btn-limpar-materia").addEventListener("click", function () {
    campoTitulo.value = "";
    campoTexto.value = "";
    campoImagem.value = "";
    campoYoutube.value = "";
    campoTema.value = "Notícias";
    campoFonteNome.value = "";
    campoFonteLink.value = "";
    campoResumo.value = "";
    previewMarkdown.value = "";
    previewFilename.textContent = "";
  });

  // ============================================================
  // HASHTAGS
  // ============================================================
  var DICAS = [
    "patosdeminas", "prefeituradepatos", "camarapatosdeminas", "acipatos",
    "unipam", "iftmpatos", "sebraeminas", "fiemg", "apae", "urt", "mamore",
    "fenamilho", "coopatos", "ligapatense", "sicoob", "expocaccer",
    "patrocinio", "coromandel", "serradosalitre", "altoparanaiba",
    "lagoaformosa", "presidenteolegario", "vazante", "ibia", "saogotardo",
    "montecarmelo", "araxa", "rioparanaiba", "patosdeminasmg", "triangulomineiro"
  ];

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
    document.getElementById("status-carregar").textContent = "Hashtag #" + tag + " adicionada. Gere o JSON para salvar.";
  }

  function lerHashtagsDoGitHub() {
    document.getElementById("status-carregar").textContent = "Carregando lista do GitHub...";
    var url = "https://raw.githubusercontent.com/" + REPO_OWNER + "/" + REPO_NAME + "/main/hashtags.json";
    return fetch(url)
      .then(function (r) {
        if (!r.ok) throw new Error("status " + r.status);
        return r.json();
      })
      .then(function (data) {
        var tags = (data.hashtags || data || []).filter(function (t) { return t; });
        document.getElementById("lista-hashtags").value = tags.join("\n");
        document.getElementById("status-carregar").textContent = "Lista carregada: " + tags.length + " hashtag(s).";
      })
      .catch(function (e) {
        document.getElementById("status-carregar").textContent = "Não foi possível carregar (" + e.message + ").";
        document.getElementById("lista-hashtags").value = "patosdeminas\nacipatos\nunipam";
      });
  }

  function gerarJsonHashtags() {
    var campo = document.getElementById("lista-hashtags");
    var tags = campo.value.split("\n").map(function (t) { return t.trim().toLowerCase().replace(/^#/, ""); }).filter(Boolean);
    var unicas = [];
    tags.forEach(function (t) { if (unicas.indexOf(t) === -1) unicas.push(t); });
    var json = JSON.stringify({ hashtags: unicas }, null, 2);
    document.getElementById("json-saida").value = json;
    return json;
  }

  document.getElementById("btn-gerar").addEventListener("click", function () {
    gerarJsonHashtags();
    copiarCampo("json-saida", "msg-copiado");
  });

  document.getElementById("btn-copiar").addEventListener("click", function () {
    copiarCampo("json-saida", "msg-copiado");
  });

  document.getElementById("btn-recarga").addEventListener("click", lerHashtagsDoGitHub);

  document.getElementById("btn-abrir-github").addEventListener("click", function () {
    gerarJsonHashtags();
    var url = "https://github.com/" + REPO_OWNER + "/" + REPO_NAME + "/blob/main/hashtags.json";
    window.open(url, "_blank");
  });

  // ============================================================
  // INICIA
  // ============================================================
  if (telaLogin && document.getElementById("campo-senha")) {
    document.getElementById("campo-senha").focus();
  }

})();
