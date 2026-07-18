/* ============================================================
   DORAMAS BOOK — interações + checkout PIX (NexusPag)
   ============================================================ */
"use strict";

const EBOOK = {
  id: "o-guarda-chuva-que-ela-esqueceu",
  title: "O Guarda-Chuva Que Ela Esqueceu",
  price: 6.0,
  readUrl: "https://online.fliphtml5.com/marcous/yphc/#p=1",
  pdfUrl: "assets/o-guarda-chuva-que-ela-esqueceu.pdf",
  pdfName: "O-Guarda-Chuva-Que-Ela-Esqueceu.pdf",
};

const STORAGE_KEY = "doramasbook_purchase";
const POLL_INTERVAL = 4000; // 4s

/* ---------------- helpers ---------------- */
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

function toast(msg, ms = 2600) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => t.classList.remove("show"), ms);
}

/* ---------------- header / menu ---------------- */
const header = $("#header");
window.addEventListener("scroll", () => {
  header.classList.toggle("scrolled", window.scrollY > 30);
});

const navToggle = $("#navToggle");
const navLinks = $("#navLinks");
navToggle.addEventListener("click", () => {
  navLinks.classList.toggle("open");
  navToggle.classList.toggle("open");
});
navLinks.querySelectorAll("a").forEach((a) =>
  a.addEventListener("click", () => {
    navLinks.classList.remove("open");
    navToggle.classList.remove("open");
  })
);

/* ---------------- reveal on scroll ---------------- */
const io = new IntersectionObserver(
  (entries) => {
    entries.forEach((e) => {
      if (e.isIntersecting) {
        e.target.classList.add("visible");
        io.unobserve(e.target);
      }
    });
  },
  { threshold: 0.12 }
);
$$(".reveal").forEach((el) => io.observe(el));

/* ---------------- contadores animados ---------------- */
const counterIO = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      const el = entry.target;
      const target = parseInt(el.dataset.count, 10);
      const isRating = target === 49;
      const dur = 1400;
      const start = performance.now();
      function tick(now) {
        const p = Math.min((now - start) / dur, 1);
        const eased = 1 - Math.pow(1 - p, 3);
        const val = Math.round(target * eased);
        el.textContent = isRating ? (val / 10).toFixed(1).replace(".", ",") : val >= 1000 ? (val / 1000).toFixed(1).replace(".", ",") + "k+" : "+" + val;
        if (p < 1) requestAnimationFrame(tick);
      }
      requestAnimationFrame(tick);
      counterIO.unobserve(el);
    });
  },
  { threshold: 0.6 }
);
$$("[data-count]").forEach((el) => counterIO.observe(el));

/* ---------------- pétalas de sakura ---------------- */
(function petals() {
  const box = $("#petals");
  const N = window.innerWidth < 640 ? 7 : 12;
  for (let i = 0; i < N; i++) {
    const p = document.createElement("span");
    p.className = "petal";
    const size = 8 + Math.random() * 12;
    p.style.width = size + "px";
    p.style.height = size * 0.8 + "px";
    p.style.left = Math.random() * 100 + "vw";
    p.style.setProperty("--sway", (Math.random() * 16 - 8).toFixed(1) + "vw");
    p.style.animationDuration = 7 + Math.random() * 9 + "s";
    p.style.animationDelay = -Math.random() * 14 + "s";
    p.style.opacity = 0.35 + Math.random() * 0.45;
    box.appendChild(p);
  }
})();

/* ---------------- tilt 3D no livro ---------------- */
(function tilt() {
  const stage = $("#bookStage");
  const book = $("#book3d");
  if (!stage || !book) return;
  stage.addEventListener("mousemove", (e) => {
    const r = stage.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width - 0.5;
    const y = (e.clientY - r.top) / r.height - 0.5;
    book.style.transform = `rotateY(${x * 18}deg) rotateX(${-y * 14}deg)`;
  });
  stage.addEventListener("mouseleave", () => {
    book.style.transform = "rotateY(0) rotateX(0)";
  });
})();

/* ============================================================
   CHECKOUT + PAGAMENTO PIX
   ============================================================ */
const modal = $("#checkoutModal");
const steps = {
  resumo: $("#stepResumo"),
  pix: $("#stepPix"),
  sucesso: $("#stepSucesso"),
  erro: $("#stepErro"),
};

let pollTimer = null;
let countdownTimer = null;
let currentTxId = null;

function showStep(name) {
  Object.values(steps).forEach((s) => s.classList.add("hidden"));
  steps[name].classList.remove("hidden");
}

function stopPolling() {
  if (pollTimer) clearInterval(pollTimer);
  if (countdownTimer) clearInterval(countdownTimer);
  pollTimer = countdownTimer = null;
}

function openModal() {
  modal.classList.add("open");
  modal.setAttribute("aria-hidden", "false");
  document.body.style.overflow = "hidden";
  // se já comprou, vai direto para a tela de acesso
  if (getPurchase()) {
    showStep("sucesso");
  } else {
    showStep("resumo");
  }
}

function closeModal() {
  modal.classList.remove("open");
  modal.setAttribute("aria-hidden", "true");
  document.body.style.overflow = "";
  stopPolling();
}

$$("[data-buy]").forEach((b) => b.addEventListener("click", openModal));
$("#modalClose").addEventListener("click", closeModal);
modal.addEventListener("click", (e) => {
  if (e.target === modal) closeModal();
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && modal.classList.contains("open")) closeModal();
});

/* ---------------- compra salva (localStorage) ---------------- */
function getPurchase() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY));
  } catch {
    return null;
  }
}
function savePurchase(txId) {
  localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({ ebook: EBOOK.id, txId, date: new Date().toISOString() })
  );
  updateBuyButtons();
}

/* muda os botões do site quando já comprou */
function updateBuyButtons() {
  if (!getPurchase()) return;
  $$("[data-buy]").forEach((b) => {
    b.innerHTML = "📖 Acessar meu e-book";
  });
}
updateBuyButtons();

/* ---------------- criar cobrança PIX ---------------- */
$("#btnGerarPix").addEventListener("click", createPixCharge);
$("#btnTentarNovamente").addEventListener("click", createPixCharge);

async function createPixCharge() {
  const btn = $("#btnGerarPix");
  const btnRetry = $("#btnTentarNovamente");
  [btn, btnRetry].forEach((b) => {
    b.disabled = true;
    b.dataset.label = b.textContent;
    b.textContent = "Gerando QR Code… ⏳";
  });

  try {
    const resp = await fetch("/api/create-pix", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ external_id: `doramasbook-${Date.now()}` }),
    });
    const data = await resp.json();

    if (!resp.ok || !data.success || !data.transaction) {
      throw new Error(data.error || data.message || "Erro ao gerar cobrança PIX");
    }

    const tx = data.transaction;
    currentTxId = tx.id || tx.txid;

    // QR code + copia e cola
    const qrSrc = (tx.qr_code_base64 || "").startsWith("data:")
      ? tx.qr_code_base64
      : "data:image/png;base64," + (tx.qr_code_base64 || "");
    $("#qrImage").src = qrSrc;
    $("#pixCode").value = tx.pix_copia_cola || "";

    // status visual
    const st = $("#pixStatus");
    st.classList.remove("paid");
    st.innerHTML = '<span class="pulse-dot"></span> Aguardando pagamento…';

    showStep("pix");
    startCountdown(tx.expires_at);
    startPolling(currentTxId);
  } catch (err) {
    console.error(err);
    $("#erroTitulo").textContent = "Não consegui gerar o PIX 😢";
    $("#erroMsg").textContent =
      "Verifique sua internet e tente novamente. (" + err.message + ")";
    showStep("erro");
  } finally {
    [btn, btnRetry].forEach((b) => {
      b.disabled = false;
      if (b.dataset.label) b.textContent = b.dataset.label;
    });
  }
}

/* ---------------- copiar código ---------------- */
$("#btnCopyPix").addEventListener("click", async () => {
  const input = $("#pixCode");
  try {
    await navigator.clipboard.writeText(input.value);
  } catch {
    input.select();
    document.execCommand("copy");
  }
  toast("✅ Código PIX copiado!");
});

/* ---------------- countdown de expiração ---------------- */
function startCountdown(expiresAt) {
  if (countdownTimer) clearInterval(countdownTimer);
  const el = $("#pixCountdown");
  let end = expiresAt ? new Date(expiresAt).getTime() : Date.now() + 30 * 60 * 1000;
  if (isNaN(end)) end = Date.now() + 30 * 60 * 1000;

  function tick() {
    const diff = end - Date.now();
    if (diff <= 0) {
      el.textContent = "00:00";
      stopPolling();
      $("#erroTitulo").textContent = "Ops… ⏰";
      $("#erroMsg").textContent = "O código PIX expirou. Gere um novo para continuar.";
      showStep("erro");
      return;
    }
    const m = Math.floor(diff / 60000);
    const s = Math.floor((diff % 60000) / 1000);
    el.textContent = String(m).padStart(2, "0") + ":" + String(s).padStart(2, "0");
  }
  tick();
  countdownTimer = setInterval(tick, 1000);
}

/* ---------------- polling do status ---------------- */
function startPolling(txId) {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(() => checkStatus(txId), POLL_INTERVAL);
}

async function checkStatus(txId) {
  try {
      const resp = await fetch("/api/pix-status?id=" + encodeURIComponent(txId));
    const data = await resp.json();
    const status = (data.status || (data.transaction && data.transaction.status) || "").toLowerCase();

    if (status === "paid" || status === "confirmed" || status === "completed" || status === "approved") {
      stopPolling();
      onPaymentConfirmed(txId);
    } else if (status === "expired" || status === "cancelled" || status === "canceled") {
      stopPolling();
      $("#erroTitulo").textContent = "Pagamento " + (status === "expired" ? "expirado ⏰" : "cancelado ❌");
      $("#erroMsg").textContent = "Gere um novo código PIX para tentar de novo.";
      showStep("erro");
    }
  } catch (err) {
    console.warn("poll error:", err);
  }
}

/* ---------------- pagamento confirmado ---------------- */
function onPaymentConfirmed(txId) {
  savePurchase(txId);
  const st = $("#pixStatus");
  st.classList.add("paid");
  st.innerHTML = "✅ Pagamento confirmado!";
  setTimeout(() => {
    showStep("sucesso");
    confettiBurst();
    toast("🎉 Pagamento aprovado! Boa leitura 💜", 4000);
  }, 700);
}

/* ---------------- download PDF + leitor offline ---------------- */
(function dualDownload() {
  const btnPdf = $("#btnDownloadPdf");
  const linkLeitor = $("#linkLeitorOffline");
  if (!btnPdf || !linkLeitor) return;

  btnPdf.addEventListener("click", () => {
    // baixa o leitor offline (HTML) logo em seguida
    setTimeout(() => {
      const a = document.createElement("a");
      a.href = linkLeitor.getAttribute("href");
      a.download = linkLeitor.getAttribute("download") || "LER-AGORA-doramas-book.html";
      document.body.appendChild(a);
      a.click();
      a.remove();
      toast("📥 Baixando PDF + leitor offline (HTML)…", 3500);
    }, 600);
  });
})();

/* ---------------- confete ---------------- */
function confettiBurst() {
  const colors = ["#ff4d8d", "#a855f7", "#22d3ee", "#fbbf24", "#4ade80", "#ffffff"];
  for (let i = 0; i < 90; i++) {
    const c = document.createElement("div");
    c.className = "confetti";
    c.style.left = Math.random() * 100 + "vw";
    c.style.background = colors[(Math.random() * colors.length) | 0];
    c.style.animationDuration = 2.2 + Math.random() * 2.4 + "s";
    c.style.animationDelay = Math.random() * 0.6 + "s";
    c.style.transform = `rotate(${Math.random() * 360}deg)`;
    document.body.appendChild(c);
    setTimeout(() => c.remove(), 6000);
  }
}
