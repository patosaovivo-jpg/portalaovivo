// ============================================================
// CONFIGURACAO DO PAINEL DE CONTROLE
// Senha de acesso + informacoes do repositorio.
// ATENCAO: este arquivo fica publico no site.
// ============================================================
var PAINEL_SENHA = "mudar123";
var REPO_OWNER = "patosaovivo-jpg";
var REPO_NAME = "portalaovivo";
var REPO_BRANCH = "main";

// URLs dos arquivos para edicao
var ARQUIVOS = {
  fonts: "fonts.json",
  hashtags: "hashtags.json",
  themes: "themes.json",
  ads_yml: "_data/ads.yml",
  ads_imagens: "assets/js/ads-imagens.json",
};

// URLs do GitHub Raw (para leitura publica)
var RAW_BASE = "https://raw.githubusercontent.com/" + REPO_OWNER + "/" + REPO_NAME + "/" + REPO_BRANCH + "/";
var GITHUB_EDIT = "https://github.com/" + REPO_OWNER + "/" + REPO_NAME + "/edit/" + REPO_BRANCH + "/";
var GITHUB_ACTIONS = "https://github.com/" + REPO_OWNER + "/" + REPO_NAME + "/actions/workflows/pipeline.yml";
