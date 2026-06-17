/* ==========================================================================
   VIGÍLIA — SPA (vigiliasms.web.app)
   Toda renderização de dados externos usa textContent / escape explícito:
   nenhum conteúdo dos diários é injetado como HTML bruto (anti-XSS).
   ========================================================================== */

"use strict";

const API = "/api";
const LOTE_RENDERIZACAO = 30;

const NOMES_FONTES = {
  "DOU": "Diário Oficial da União",
  "DOE-SC": "Diário Oficial de Santa Catarina",
  "DOE-JOI": "Diário Oficial de Joinville",
};

const estado = {
  resultados: [],
  palavrasBusca: [],
  configCarregada: null,
  porFonte: {},               // { DOU: [...], "DOE-SC": [...] }
  renderizadosPorFonte: {},   // quantos cards já renderizados por aba
  abaAtiva: null,
  sinteseCache: {},           // síntese por assinatura de busca (evita recustear)
};

/* ------------------------------------------------------------------ utils */

const $ = (sel) => document.querySelector(sel);

function hojeISO() {
  const d = new Date();
  const off = d.getTimezoneOffset();
  return new Date(d.getTime() - off * 60000).toISOString().slice(0, 10);
}

function dataPorExtenso() {
  return new Date().toLocaleDateString("pt-BR", {
    weekday: "long", day: "numeric", month: "long", year: "numeric",
  }).toUpperCase();
}

function isoParaBR(iso) {
  const [a, m, d] = String(iso).split("-");
  return `${d}/${m}/${a}`;
}

/* Destaque seguro de palavras-chave: opera sobre TEXTO (não HTML) e monta
   nós DOM com textContent — imune a injeção e à corrupção de marcação. */
function montarTextoDestacado(texto, palavras) {
  const frag = document.createDocumentFragment();
  const limpo = String(texto || "");
  if (!palavras || !palavras.length) {
    frag.appendChild(document.createTextNode(limpo));
    return frag;
  }
  const escapadas = palavras
    .filter(Boolean)
    .map((p) => p.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  if (!escapadas.length) {
    frag.appendChild(document.createTextNode(limpo));
    return frag;
  }
  // split com UM grupo de captura alterna [texto, match, texto, match, ...]:
  // índices ímpares são sempre os termos encontrados.
  const re = new RegExp(`(${escapadas.join("|")})`, "gi");
  limpo.split(re).forEach((parte, i) => {
    if (parte === "") return;
    if (i % 2 === 1) {
      const m = document.createElement("mark");
      m.textContent = parte;
      frag.appendChild(m);
    } else {
      frag.appendChild(document.createTextNode(parte));
    }
  });
  return frag;
}

async function chamarAPI(rota, opcoes = {}) {
  const resp = await fetch(`${API}${rota}`, {
    headers: { "Content-Type": "application/json" },
    ...opcoes,
  });
  const corpo = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    throw new Error(corpo.erro || `Falha na API (${resp.status})`);
  }
  return corpo;
}

function baixarArquivo(nome, conteudo, mime) {
  const blob = new Blob([conteudo], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = nome;
  a.click();
  URL.revokeObjectURL(url);
}

/* ------------------------------------------------------- chips reutilizáveis */

function criarChips(containerSel, inputSel, validar) {
  const container = $(containerSel);
  const input = $(inputSel);
  const valores = [];

  function render() {
    container.querySelectorAll(".chip").forEach((c) => c.remove());
    for (const [i, valor] of valores.entries()) {
      const chip = document.createElement("span");
      chip.className = "chip";
      const txt = document.createElement("span");
      txt.textContent = valor;
      const x = document.createElement("button");
      x.type = "button";
      x.className = "chip-x";
      x.textContent = "×";
      x.setAttribute("aria-label", `Remover ${valor}`);
      x.addEventListener("click", () => {
        valores.splice(i, 1);
        render();
      });
      chip.append(txt, x);
      container.insertBefore(chip, input);
    }
  }

  function adicionar(valor) {
    const limpo = String(valor || "").trim();
    if (!limpo) return;
    if (validar && !validar(limpo)) return;
    if (valores.some((v) => v.toLowerCase() === limpo.toLowerCase())) return;
    valores.push(limpo);
    render();
  }

  input.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter" || ev.key === ",") {
      ev.preventDefault();
      adicionar(input.value.replace(/,$/, ""));
      input.value = "";
    } else if (ev.key === "Backspace" && !input.value && valores.length) {
      valores.pop();
      render();
    }
  });

  input.addEventListener("blur", () => {
    if (input.value.trim()) {
      adicionar(input.value);
      input.value = "";
    }
  });

  container.addEventListener("click", () => input.focus());

  return {
    get: () => [...valores],
    set: (lista) => {
      valores.length = 0;
      for (const v of lista || []) adicionar(v);
      render();
    },
  };
}

/* --------------------------------------------- kits (conjuntos de busca) ---- */
// Modelo DNF: lista de grupos; termos no MESMO grupo = E; entre grupos = OU.
function criarKits(containerId) {
  const container = document.getElementById(containerId);
  let grupos = [[]];

  function render() {
    container.textContent = "";

    grupos.forEach((grupo, gi) => {
      if (gi > 0) {
        const ou = document.createElement("div");
        ou.className = "kit-ou";
        ou.textContent = "OU";
        container.appendChild(ou);
      }

      const kit = document.createElement("div");
      kit.className = "kit";

      const head = document.createElement("div");
      head.className = "kit-head";
      const label = document.createElement("span");
      label.className = "kit-label";
      label.textContent = "contém todos (E)";
      head.appendChild(label);
      if (grupos.length > 1) {
        const del = document.createElement("button");
        del.type = "button";
        del.className = "kit-del";
        del.textContent = "remover";
        del.addEventListener("click", () => {
          grupos.splice(gi, 1);
          if (!grupos.length) grupos = [[]];
          render();
        });
        head.appendChild(del);
      }

      const chips = document.createElement("div");
      chips.className = "kit-chips";
      grupo.forEach((termo, ti) => {
        const chip = document.createElement("span");
        chip.className = "chip";
        const txt = document.createElement("span");
        txt.textContent = termo;
        const x = document.createElement("button");
        x.type = "button";
        x.className = "chip-x";
        x.textContent = "×";
        x.setAttribute("aria-label", `Remover ${termo}`);
        x.addEventListener("click", () => { grupo.splice(ti, 1); render(); });
        chip.append(txt, x);
        chips.appendChild(chip);
      });

      const input = document.createElement("input");
      input.type = "text";
      input.className = "kit-input chip-input";
      input.placeholder = grupo.length ? "+ E (termo ou frase)…" : "termo (ex.: Joinville)…";
      input.autocomplete = "off";
      input.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter" || ev.key === ",") {
          ev.preventDefault();
          const v = input.value.replace(/,$/, "");
          input.value = "";
          adicionarTermo(gi, v);
        } else if (ev.key === "Backspace" && !input.value && grupo.length) {
          grupo.pop();
          render();
          focarKit(gi);
        }
      });
      input.addEventListener("blur", () => {
        if (input.value.trim()) adicionarTermo(gi, input.value);
      });
      chips.appendChild(input);
      chips.addEventListener("click", () => input.focus());

      kit.append(head, chips);
      container.appendChild(kit);
    });

    const add = document.createElement("button");
    add.type = "button";
    add.className = "kit-add";
    add.textContent = "+ conjunto (OU)";
    add.addEventListener("click", () => {
      grupos.push([]);
      render();
      focarKit(grupos.length - 1);
    });
    container.appendChild(add);
  }

  function adicionarTermo(gi, valor) {
    const limpo = String(valor || "").trim();
    if (!limpo) return;
    const grupo = grupos[gi];
    if (grupo.some((t) => t.toLowerCase() === limpo.toLowerCase())) return;
    grupo.push(limpo);
    render();
    focarKit(gi);
  }

  function focarKit(gi) {
    const inputs = container.querySelectorAll(".kit .kit-input");
    if (inputs[gi]) inputs[gi].focus();
  }

  render();
  return {
    get: () => grupos.map((g) => g.filter(Boolean)).filter((g) => g.length),
    set: (novos) => {
      grupos = (Array.isArray(novos) && novos.length)
        ? novos.map((g) => (Array.isArray(g) ? [...g] : []))
        : [[]];
      if (!grupos.length) grupos = [[]];
      render();
    },
  };
}

// Achata os grupos em termos únicos (para o destaque nos cards).
function termosDeKits(grupos) {
  const vistos = [];
  for (const g of grupos || []) {
    for (const t of g) {
      if (!vistos.some((v) => v.toLowerCase() === t.toLowerCase())) vistos.push(t);
    }
  }
  return vistos;
}

const kitsBusca = criarKits("kits-busca");
const kitsConfig = criarKits("kits-config");
const chipsEmails = criarChips("#chips-emails", "#inp-email", (v) => v.includes("@"));

/* ------------------------------------------------------------ configuração */

async function carregarConfig() {
  try {
    const cfg = await chamarAPI("/config");
    estado.configCarregada = cfg;
    const v = cfg.varredura || {};
    const grupos = (v.grupos && v.grupos.length) ? v.grupos : [];
    kitsBusca.set(grupos);
    kitsConfig.set(grupos);
    $("#chk-dou").checked = (v.fontes || {}).dou !== false;
    $("#chk-doesc").checked = (v.fontes || {}).doesc !== false;
    const r = cfg.relatorio || {};
    $("#chk-relatorio-ativo").checked = !!r.ativo;
    $("#chk-resumo-ia").checked = !!r.resumo_ia;
    chipsEmails.set(r.destinatarios || []);
    $("#sel-horario").value = _horaCheia(r.horario || "07:00");
    $("#hint-origem-config").hidden = !grupos.length;
  } catch (e) {
    console.warn("Configuração indisponível (API offline?):", e.message);
  }
  // remetente real (vem do /health quando o SMTP está configurado)
  try {
    const saude = await chamarAPI("/health");
    if (saude.remetente_email && !saude.remetente_email.includes("não configurado")) {
      $("#remetente-preview").textContent = saude.remetente_email;
    }
  } catch (_) { /* silencioso */ }
}

async function salvarConfig() {
  const statusEl = $("#config-status");
  statusEl.textContent = "Salvando configuração…";
  try {
    const cfg = await chamarAPI("/config", {
      method: "POST",
      body: JSON.stringify({
        varredura: {
          grupos: kitsConfig.get(),
          fontes: { dou: $("#chk-dou").checked, doesc: $("#chk-doesc").checked },
        },
        relatorio: coletarRelatorio(),
      }),
    });
    estado.configCarregada = cfg;
    statusEl.textContent = "✓ Configuração salva na nuvem.";
    setTimeout(() => { statusEl.textContent = ""; }, 4000);
  } catch (e) {
    statusEl.textContent = `Erro ao salvar: ${e.message}`;
  }
}

function _horaCheia(horario) {
  const h = parseInt(String(horario).split(":")[0], 10);
  return `${String(isNaN(h) ? 7 : h).padStart(2, "0")}:00`;
}

function coletarRelatorio() {
  return {
    ativo: $("#chk-relatorio-ativo").checked,
    destinatarios: chipsEmails.get(),
    resumo_ia: $("#chk-resumo-ia").checked,
    horario: $("#sel-horario").value || "07:00",
  };
}

async function salvarRelatorio() {
  const statusEl = $("#config-status");
  statusEl.textContent = "Salvando configuração do relatório…";
  try {
    const cfg = await chamarAPI("/config", {
      method: "POST",
      body: JSON.stringify({ relatorio: coletarRelatorio() }),
    });
    estado.configCarregada = cfg;
    statusEl.textContent = "✓ Configuração do relatório salva.";
    setTimeout(() => { statusEl.textContent = ""; }, 4000);
  } catch (e) {
    statusEl.textContent = `Erro ao salvar: ${e.message}`;
  }
}

async function testarEmail() {
  const statusEl = $("#config-status");
  const emails = chipsEmails.get();
  if (!emails.length) {
    statusEl.textContent = "Adicione ao menos um destinatário antes de testar.";
    return;
  }
  const btn = $("#btn-testar-email");
  const original = btn.textContent;
  btn.disabled = true;
  btn.textContent = "Enviando…";
  statusEl.textContent = `Varrendo a edição de hoje e enviando para ${emails.length} destinatário(s)…`;
  try {
    const resp = await chamarAPI("/relatorio/testar", {
      method: "POST",
      body: JSON.stringify({ destinatarios: emails, data: $("#inp-data").value || hojeISO() }),
    });
    statusEl.textContent = `✓ ${resp.mensagem}`;
  } catch (e) {
    statusEl.textContent = `✉ Não foi possível enviar: ${e.message}`;
  } finally {
    btn.disabled = false;
    btn.textContent = original;
  }
}

/* ---------------------------------------------------------------- operador */

/* ----------------------------------------------------------------- loader */

const FRASES_BUSCA = [
  "Abrindo a edição do Diário Oficial…",
  "Garimpando portarias, decretos e atos…",
  "Cruzando as publicações com as palavras-chave…",
  "Separando o que interessa para Joinville…",
];
const FRASES_IA = [
  "Acionando a inteligência do Vigília…",
  "Lendo os atos e medindo o impacto…",
  "Destacando repasses, prazos e habilitações…",
  "Montando a análise executiva…",
];

let _loaderTimer = null;
let _loaderFrases = FRASES_BUSCA;
let _loaderIdx = 0;

function _trocarFrase() {
  const el = $("#loader-frase");
  el.style.opacity = "0";
  setTimeout(() => {
    _loaderIdx = (_loaderIdx + 1) % _loaderFrases.length;
    el.textContent = _loaderFrases[_loaderIdx];
    el.style.opacity = "1";
  }, 220);
}

function iniciarLoader(dataBR) {
  const sec = $("#sec-telex");
  sec.hidden = false;
  sec.classList.remove("loader-erro");
  $("#loader-titulo").textContent = `Varrendo a edição de ${dataBR}`;
  _loaderFrases = FRASES_BUSCA;
  _loaderIdx = 0;
  $("#loader-frase").style.opacity = "1";
  $("#loader-frase").textContent = _loaderFrases[0];
  clearInterval(_loaderTimer);
  _loaderTimer = setInterval(_trocarFrase, 2400);
}

function loaderFaseIA() {
  $("#loader-titulo").textContent = "Gerando a síntese inteligente…";
  _loaderFrases = FRASES_IA;
  _loaderIdx = 0;
  $("#loader-frase").textContent = _loaderFrases[0];
}

function pararLoader() {
  clearInterval(_loaderTimer);
  _loaderTimer = null;
  $("#sec-telex").hidden = true;
}

function loaderErro(msg) {
  clearInterval(_loaderTimer);
  _loaderTimer = null;
  const sec = $("#sec-telex");
  sec.classList.add("loader-erro");
  $("#loader-titulo").textContent = "Não foi possível concluir a varredura";
  $("#loader-frase").textContent = msg;
}

/* ------------------------------------------------------------------- busca */

async function executarVarredura() {
  const btn = $("#btn-buscar");

  const fontes = { dou: $("#chk-dou").checked, doesc: $("#chk-doesc").checked };
  if (!fontes.dou && !fontes.doesc) {
    alert("Selecione pelo menos uma fonte (DOU e/ou DOE-SC).");
    return;
  }

  const dataISO = $("#inp-data").value || hojeISO();
  const grupos = kitsBusca.get();

  if (!grupos.length) {
    const ok = confirm(
      "Nenhum conjunto de busca informado.\n\nA varredura retornará TODAS as " +
      "publicações do dia (centenas de resultados). Continuar mesmo assim?"
    );
    if (!ok) return;
  }

  btn.disabled = true;
  $("#sec-resultados").hidden = true;
  $("#sec-vazio").hidden = true;
  $("#sintese-ia").hidden = true;
  iniciarLoader(isoParaBR(dataISO));

  let resposta;
  try {
    resposta = await chamarAPI("/buscar", {
      method: "POST",
      body: JSON.stringify({ data: dataISO, grupos, fontes }),
    });
  } catch (e) {
    loaderErro(e.message);
    btn.disabled = false;
    return;
  }

  estado.resultados = resposta.resultados || [];
  estado.palavrasBusca = termosDeKits(grupos);

  const params = { data: dataISO, grupos, fontes, avisos: resposta.avisos || [] };
  const iaAtiva = !!estado.configCarregada?.relatorio?.resumo_ia && estado.resultados.length > 0;

  // Com IA ligada, os resultados só aparecem QUANDO a síntese estiver pronta
  // (o loader segue rodando com frases de efeito). Se a IA falhar/sem cota,
  // mostramos os resultados mesmo assim.
  let sintese = null;
  if (iaAtiva) {
    loaderFaseIA();
    sintese = await obterSintese(params);
  }

  pararLoader();
  renderizarResultados(resposta);
  if (sintese) {
    renderizarSintese(sintese);
  } else {
    $("#sintese-ia").hidden = true;
  }
  btn.disabled = false;
}

/* --------------------------------------------------------- síntese por IA */

// Obtém a síntese (cache local → API). Nunca lança: devolve o texto ou null.
async function obterSintese(params) {
  const assinatura = JSON.stringify({
    data: params.data,
    grupos: params.grupos,
    fontes: params.fontes,
  });
  if (estado.sinteseCache[assinatura]) return estado.sinteseCache[assinatura];

  try {
    const resp = await chamarAPI("/sintese", {
      method: "POST",
      body: JSON.stringify({ ...params, resultados: estado.resultados }),
    });
    if (resp.sintese) {
      estado.sinteseCache[assinatura] = resp.sintese;
      return resp.sintese;
    }
    return null;
  } catch (e) {
    console.warn("Síntese por IA indisponível:", e.message);
    return null;
  }
}

// Escapa HTML e aplica formatação inline do Markdown (**negrito**, *itálico*).
// Como o texto é escapado antes, as únicas tags inseridas são as nossas.
function _esc(s) {
  return String(s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
function _inlineMd(s) {
  return _esc(s)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>");
}

// Renderiza a síntese (Markdown: ## , ### , ✦ , * , **negrito**, *itálico*).
function renderizarSintese(texto) {
  const painel = $("#sintese-ia");
  painel.hidden = false;
  painel.className = "sintese-ia";
  painel.textContent = "";

  const corpo = document.createElement("div");
  corpo.className = "sintese-corpo";

  for (const linhaBruta of String(texto).split("\n")) {
    const linha = linhaBruta.trim();
    if (!linha) continue;

    let el;
    if (linha.startsWith("## ")) {
      el = document.createElement("div");
      el.className = "sintese-h2";
      el.innerHTML = _inlineMd(linha.slice(3).trim());
    } else if (linha.startsWith("### ")) {
      el = document.createElement("div");
      el.className = "sintese-h3";
      el.innerHTML = _inlineMd(linha.slice(4).trim());
    } else if (linha.startsWith("✦")) {
      el = document.createElement("div");
      el.className = "sintese-banner";
      el.innerHTML = _inlineMd(linha);
    } else if (/^[*\-•]\s/.test(linha)) {
      // os itens já começam com emoji/▢ semântico — só recuamos, sem marcador extra
      el = document.createElement("div");
      el.className = "sintese-item";
      el.innerHTML = _inlineMd(linha.replace(/^[*\-•]\s+/, ""));
    } else {
      el = document.createElement("p");
      el.className = "sintese-p";
      el.innerHTML = _inlineMd(linha);
    }
    corpo.appendChild(el);
  }

  const rodape = document.createElement("div");
  rodape.className = "sintese-rodape";
  rodape.textContent =
    "Resumo gerado por IA a partir das publicações abaixo. Confira sempre o ato oficial.";
  painel.append(corpo, rodape);
}

/* ------------------------------------------------------------ renderização */

const ORDEM_FONTES = { "DOU": 0, "DOE-SC": 1, "DOE-JOI": 2 };

function renderizarResultados(resposta) {
  const secao = $("#sec-resultados");
  const grupos = $("#res-grupos");
  const erros = $("#res-erros");
  const tabs = $("#res-tabs");
  grupos.textContent = "";
  erros.textContent = "";
  tabs.textContent = "";

  for (const erro of resposta.erros || []) {
    const div = document.createElement("div");
    div.className = "partial-error";
    div.textContent = `⚠ Falha parcial — ${erro}`;
    erros.appendChild(div);
  }

  if (!estado.resultados.length) {
    secao.hidden = true;
    $("#sec-vazio").hidden = false;
    return;
  }

  // contador geral (todas as fontes)
  const partes = Object.entries(resposta.por_origem || {})
    .map(([origem, n]) => `${origem}: ${n}`)
    .join(" · ");
  const counter = $("#res-counter");
  counter.textContent = "";
  const strong = document.createElement("strong");
  strong.textContent = String(resposta.total);
  counter.append(strong, ` publicação(ões) encontrada(s) — ${partes}`);

  // agrupa por fonte e ordena (DOU primeiro)
  estado.porFonte = {};
  for (const r of estado.resultados) {
    const origem = r.origem || "DOU";
    (estado.porFonte[origem] = estado.porFonte[origem] || []).push(r);
  }
  estado.renderizadosPorFonte = {};
  const fontes = Object.keys(estado.porFonte)
    .sort((a, b) => (ORDEM_FONTES[a] ?? 9) - (ORDEM_FONTES[b] ?? 9));

  // barra de abas — só aparece quando há mais de uma fonte
  if (fontes.length > 1) {
    for (const fonte of fontes) {
      const tab = document.createElement("button");
      tab.type = "button";
      tab.className = `res-tab res-tab-${fonte === "DOE-SC" ? "doesc" : "dou"}`;
      tab.dataset.fonte = fonte;
      tab.setAttribute("role", "tab");
      const nome = document.createElement("span");
      nome.textContent = NOMES_FONTES[fonte] || fonte;
      const cnt = document.createElement("span");
      cnt.className = "res-tab-count";
      cnt.textContent = String(estado.porFonte[fonte].length);
      tab.append(nome, cnt);
      tab.addEventListener("click", () => ativarAba(fonte));
      tabs.appendChild(tab);
    }
    tabs.hidden = false;
  } else {
    tabs.hidden = true;
  }

  ativarAba(fontes[0]);

  secao.hidden = false;
  $("#sec-vazio").hidden = true;
  secao.scrollIntoView({ behavior: "smooth", block: "start" });
}

function ativarAba(fonte) {
  estado.abaAtiva = fonte;
  document.querySelectorAll(".res-tab").forEach((t) => {
    const ativo = t.dataset.fonte === fonte;
    t.classList.toggle("is-active", ativo);
    t.setAttribute("aria-selected", String(ativo));
  });
  // renderiza a fonte ativa do zero (paginação independente por aba)
  $("#res-grupos").textContent = "";
  estado.renderizadosPorFonte[fonte] = 0;
  renderizarLote();
}

function renderizarLote() {
  const fonte = estado.abaAtiva;
  const lista = estado.porFonte[fonte] || [];
  const grupos = $("#res-grupos");
  const ja = estado.renderizadosPorFonte[fonte] || 0;
  const fatia = lista.slice(ja, ja + LOTE_RENDERIZACAO);

  for (const registro of fatia) {
    grupos.appendChild(montarClip(registro));
  }

  estado.renderizadosPorFonte[fonte] = ja + fatia.length;
  $("#load-more-wrap").hidden = estado.renderizadosPorFonte[fonte] >= lista.length;
}

function montarClip(registro) {
  const clip = document.createElement("article");
  clip.className = "clip";

  // linha de protocolo
  const protocolo = document.createElement("div");
  protocolo.className = "clip-protocol";
  const badge = document.createElement("span");
  badge.className = `clip-badge ${registro.origem === "DOE-SC" ? "b-doesc" : "b-dou"}`;
  badge.textContent = registro.origem || "DOU";
  protocolo.appendChild(badge);
  if (registro.secao) {
    const sec = document.createElement("span");
    sec.textContent = `Seção ${String(registro.secao).replace("DO", "")}`;
    protocolo.appendChild(sec);
  }
  if (registro.data) {
    const dt = document.createElement("span");
    dt.textContent = registro.data;
    protocolo.appendChild(dt);
  }
  const hier = document.createElement("span");
  hier.className = "clip-hier";
  hier.textContent = registro.hierarquia || "";
  protocolo.appendChild(hier);

  // título
  const titulo = document.createElement("h5");
  titulo.className = "clip-title";
  const link = String(registro.link || "");
  if (link.startsWith("http")) {
    const a = document.createElement("a");
    a.href = link;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    a.appendChild(montarTextoDestacado(registro.titulo || "(sem título)", estado.palavrasBusca));
    titulo.appendChild(a);
  } else {
    titulo.appendChild(montarTextoDestacado(registro.titulo || "(sem título)", estado.palavrasBusca));
  }

  // corpo: resumo (DOE-SC) ou descrição (DOU) — esquema garante strings
  const corpoTexto = registro.resumo || registro.descricao || "";
  const corpo = document.createElement("p");
  corpo.className = "clip-body";
  if (corpoTexto.length > 600) corpo.classList.add("is-long");
  corpo.appendChild(montarTextoDestacado(corpoTexto, estado.palavrasBusca));

  clip.append(protocolo, titulo, corpo);

  if (link.startsWith("http")) {
    const acesso = document.createElement("a");
    acesso.className = "clip-link";
    acesso.href = link;
    acesso.target = "_blank";
    acesso.rel = "noopener noreferrer";
    acesso.textContent = "Acessar publicação oficial ↗";
    clip.appendChild(acesso);
  }

  return clip;
}

/* -------------------------------------------------------------- downloads */

function baixarCSV() {
  if (!estado.resultados.length) return;
  const campos = ["origem", "secao", "data", "tipo", "orgao", "hierarquia", "titulo", "link", "descricao"];
  const esc = (v) => `"${String(v ?? "").replace(/"/g, '""').replace(/\r?\n/g, " ")}"`;
  const linhas = [campos.join(";")];
  for (const r of estado.resultados) {
    linhas.push(campos.map((c) => esc(r[c])).join(";"));
  }
  baixarArquivo(
    `vigilia_resultados_${hojeISO()}.csv`,
    "﻿" + linhas.join("\r\n"),
    "text/csv;charset=utf-8"
  );
}

async function baixarFHIR() {
  if (!estado.resultados.length) return;
  const btn = $("#btn-fhir");
  const original = btn.textContent;
  btn.textContent = "Gerando Bundle…";
  btn.disabled = true;
  try {
    const resposta = await chamarAPI("/fhir", {
      method: "POST",
      body: JSON.stringify({ resultados: estado.resultados }),
    });
    baixarArquivo(
      `vigilia_fhir_bundle_${hojeISO()}.json`,
      JSON.stringify(resposta.bundle, null, 2),
      "application/fhir+json"
    );
  } catch (e) {
    alert(`Não foi possível gerar o Bundle FHIR: ${e.message}`);
  } finally {
    btn.textContent = original;
    btn.disabled = false;
  }
}

/* ------------------------------------------------------------------ início */

function popularHorarios() {
  const sel = $("#sel-horario");
  sel.textContent = "";
  for (let h = 5; h <= 20; h++) {
    const valor = `${String(h).padStart(2, "0")}:00`;
    const opt = document.createElement("option");
    opt.value = valor;
    opt.textContent = valor;
    sel.appendChild(opt);
  }
  sel.value = "07:00";
}

document.addEventListener("DOMContentLoaded", () => {
  $("#folio-data").textContent = dataPorExtenso();
  $("#inp-data").value = hojeISO();
  popularHorarios();

  $("#btn-buscar").addEventListener("click", executarVarredura);
  $("#btn-mais").addEventListener("click", renderizarLote);
  $("#btn-csv").addEventListener("click", baixarCSV);
  $("#btn-fhir").addEventListener("click", baixarFHIR);
  $("#btn-salvar-config").addEventListener("click", salvarConfig);
  $("#btn-usar-busca").addEventListener("click", () => kitsBusca.set(kitsConfig.get()));
  $("#btn-salvar-relatorio").addEventListener("click", salvarRelatorio);
  $("#btn-testar-email").addEventListener("click", testarEmail);

  // Modal de configuração (engrenagem) — fora do fluxo da página
  const modalConfig = $("#modal-config");
  const abrirConfig = () => {
    modalConfig.hidden = false;
    document.body.classList.add("modal-aberto");
    $("#btn-config-toggle").setAttribute("aria-expanded", "true");
  };
  const fecharConfig = () => {
    modalConfig.hidden = true;
    document.body.classList.remove("modal-aberto");
    $("#btn-config-toggle").setAttribute("aria-expanded", "false");
  };
  $("#btn-config-toggle").addEventListener("click", abrirConfig);
  $("#btn-config-close").addEventListener("click", fecharConfig);
  modalConfig.addEventListener("click", (e) => {
    if (e.target === modalConfig) fecharConfig();  // clique no backdrop
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !modalConfig.hidden) fecharConfig();
  });

  carregarConfig();
});
