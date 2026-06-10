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
  operador: "OU",
  resultados: [],
  palavrasBusca: [],
  renderizados: 0,
  configCarregada: null,
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

const chipsBusca = criarChips("#chips-busca", "#inp-palavra");
const chipsConfig = criarChips("#chips-config", "#inp-palavra-config");
const chipsEmails = criarChips("#chips-emails", "#inp-email", (v) => v.includes("@"));

/* ------------------------------------------------------------ configuração */

async function carregarConfig() {
  try {
    const cfg = await chamarAPI("/config");
    estado.configCarregada = cfg;
    const v = cfg.varredura || {};
    chipsBusca.set(v.palavras_chave || []);
    chipsConfig.set(v.palavras_chave || []);
    definirOperador(v.operador || "OU");
    $("#chk-dou").checked = (v.fontes || {}).dou !== false;
    $("#chk-doesc").checked = (v.fontes || {}).doesc !== false;
    const r = cfg.relatorio || {};
    $("#chk-relatorio-ativo").checked = !!r.ativo;
    $("#chk-resumo-ia").checked = !!r.resumo_ia;
    chipsEmails.set(r.destinatarios || []);
    $("#hint-origem-config").hidden = !(v.palavras_chave || []).length;
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
          palavras_chave: chipsConfig.get(),
          operador: estado.operador,
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

function coletarRelatorio() {
  return {
    ativo: $("#chk-relatorio-ativo").checked,
    destinatarios: chipsEmails.get(),
    resumo_ia: $("#chk-resumo-ia").checked,
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

function definirOperador(op) {
  estado.operador = op === "E" ? "E" : "OU";
  document.querySelectorAll(".seg-btn").forEach((btn) => {
    const ativo = btn.dataset.op === estado.operador;
    btn.classList.toggle("is-active", ativo);
    btn.setAttribute("aria-checked", String(ativo));
  });
}

document.querySelectorAll(".seg-btn").forEach((btn) => {
  btn.addEventListener("click", () => definirOperador(btn.dataset.op));
});

/* ------------------------------------------------------------------- busca */

async function executarVarredura() {
  const btn = $("#btn-buscar");
  const telex = $("#sec-telex");
  const linha1 = $("#telex-linha-1");
  const linha2 = $("#telex-linha-2");

  const fontes = { dou: $("#chk-dou").checked, doesc: $("#chk-doesc").checked };
  if (!fontes.dou && !fontes.doesc) {
    alert("Selecione pelo menos uma fonte (DOU e/ou DOE-SC).");
    return;
  }

  const dataISO = $("#inp-data").value || hojeISO();
  const palavras = chipsBusca.get();

  if (!palavras.length) {
    const ok = confirm(
      "Nenhuma palavra-chave informada.\n\nA varredura retornará TODAS as " +
      "publicações do dia (centenas de resultados). Continuar mesmo assim?"
    );
    if (!ok) return;
  }

  btn.disabled = true;
  $("#sec-resultados").hidden = true;
  $("#sec-vazio").hidden = true;
  telex.hidden = false;
  linha1.textContent = `> VARRENDO EDIÇÃO DE ${isoParaBR(dataISO)} · OPERADOR ${estado.operador}`;
  linha1.classList.add("is-active");
  linha2.textContent = [
    fontes.dou ? "DOU (SEÇÕES 1, 2 E 3)" : null,
    fontes.doesc ? "DOE-SC" : null,
  ].filter(Boolean).join(" + ") + " …";

  try {
    const resposta = await chamarAPI("/buscar", {
      method: "POST",
      body: JSON.stringify({ data: dataISO, palavras, operador: estado.operador, fontes }),
    });
    estado.resultados = resposta.resultados || [];
    estado.palavrasBusca = palavras;
    renderizarResultados(resposta);
  } catch (e) {
    linha2.textContent = `ERRO: ${e.message}`;
    linha1.classList.remove("is-active");
    btn.disabled = false;
    return;
  }

  telex.hidden = true;
  linha1.classList.remove("is-active");
  btn.disabled = false;
}

/* ------------------------------------------------------------ renderização */

function renderizarResultados(resposta) {
  const secao = $("#sec-resultados");
  const grupos = $("#res-grupos");
  const erros = $("#res-erros");
  grupos.textContent = "";
  erros.textContent = "";
  estado.renderizados = 0;

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

  const partes = Object.entries(resposta.por_origem || {})
    .map(([origem, n]) => `${origem}: ${n}`)
    .join(" · ");
  const counter = $("#res-counter");
  counter.textContent = "";
  const strong = document.createElement("strong");
  strong.textContent = String(resposta.total);
  counter.append(strong, ` publicação(ões) encontrada(s) — ${partes}`);

  renderizarLote();
  secao.hidden = false;
  $("#sec-vazio").hidden = true;
  secao.scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderizarLote() {
  const grupos = $("#res-grupos");
  const ordenados = ordenarPorOrigem(estado.resultados);
  const fatia = ordenados.slice(estado.renderizados, estado.renderizados + LOTE_RENDERIZACAO);

  for (const registro of fatia) {
    const origem = registro.origem || "DOU";
    let grupoEl = grupos.querySelector(`[data-grupo="${origem}"]`);
    if (!grupoEl) {
      const titulo = document.createElement("h4");
      titulo.className = "group-title";
      titulo.textContent = NOMES_FONTES[origem] || origem;
      const count = document.createElement("span");
      count.className = "group-count";
      count.textContent = `${contarOrigem(origem)} registro(s)`;
      titulo.appendChild(count);
      grupoEl = document.createElement("div");
      grupoEl.dataset.grupo = origem;
      grupoEl.appendChild(titulo);
      grupos.appendChild(grupoEl);
    }
    grupoEl.appendChild(montarClip(registro));
  }

  estado.renderizados += fatia.length;
  $("#load-more-wrap").hidden = estado.renderizados >= estado.resultados.length;
}

function ordenarPorOrigem(lista) {
  const peso = { "DOU": 0, "DOE-SC": 1, "DOE-JOI": 2 };
  return [...lista].sort(
    (a, b) => (peso[a.origem] ?? 9) - (peso[b.origem] ?? 9)
  );
}

function contarOrigem(origem) {
  return estado.resultados.filter((r) => r.origem === origem).length;
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

document.addEventListener("DOMContentLoaded", () => {
  $("#folio-data").textContent = dataPorExtenso();
  $("#inp-data").value = hojeISO();

  $("#btn-buscar").addEventListener("click", executarVarredura);
  $("#btn-mais").addEventListener("click", renderizarLote);
  $("#btn-csv").addEventListener("click", baixarCSV);
  $("#btn-fhir").addEventListener("click", baixarFHIR);
  $("#btn-salvar-config").addEventListener("click", salvarConfig);
  $("#btn-usar-busca").addEventListener("click", () => chipsBusca.set(chipsConfig.get()));
  $("#btn-salvar-relatorio").addEventListener("click", salvarRelatorio);
  $("#btn-testar-email").addEventListener("click", testarEmail);

  $("#btn-config-toggle").addEventListener("click", () => {
    const sec = $("#sec-config");
    sec.hidden = !sec.hidden;
    $("#btn-config-toggle").setAttribute("aria-expanded", String(!sec.hidden));
    if (!sec.hidden) sec.scrollIntoView({ behavior: "smooth", block: "start" });
  });

  carregarConfig();
});
