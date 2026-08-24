(() => {
  "use strict";

  const boot = document.querySelector(".boot");
  if (!boot) return;

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reducedMotion) {
    boot.remove();
    return;
  }

  const log = document.getElementById("bootLog");
  const bar = document.getElementById("bootBar");
  const percent = document.getElementById("bootPercent");

  const lines = [
    ["info", "NETPULSE OS // HOME NETWORK OBSERVATORY v0.1"],
    ["ok", "> カーネル読込 ...................... OK"],
    ["ok", "> ニュートリノIF .................... ONLINE"],
    ["ok", "> LOCAL NETWORK ..................... LINK"],
    ["ok", "> GATEWAY HANDSHAKE ................. OK"],
    ["ok", "> SIGNAL COLLECTOR .................. RUNNING"],
    ["warn", "> ANOMALY RADAR ..................... STANDBY"],
    ["ok", "> OBSERVATION START // I CAN SEE YOU"],
  ];

  const sleep = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms));
  let concluded = false;

  const finish = () => {
    boot.classList.add("boot--done");
    window.setTimeout(() => boot.remove(), 680);
  };

  const conclude = (fast) => {
    if (concluded) return;
    concluded = true;
    if (bar) bar.style.width = "100%";
    if (percent) percent.textContent = "100%";
    boot.classList.add("boot--title");
    window.setTimeout(() => {
      boot.classList.add("boot--flash");
      window.setTimeout(finish, fast ? 140 : 360);
    }, fast ? 140 : 320);
  };

  boot.addEventListener("click", () => conclude(true), { once: true });
  window.addEventListener("keydown", () => conclude(true), { once: true });

  const run = async () => {
    for (let i = 0; i < lines.length; i += 1) {
      if (concluded) return;
      const [tone, text] = lines[i];
      const row = document.createElement("div");
      row.className = `boot__line boot__line--${tone}`;
      const body = document.createElement("span");
      row.append(body);
      log.append(row);
      for (let c = 0; c <= text.length; c += 1) {
        if (concluded) break;
        body.textContent = text.slice(0, c);
        await sleep(8);
      }
      if (concluded) return;
      const pct = Math.round(((i + 1) / lines.length) * 100);
      if (bar) bar.style.width = `${pct}%`;
      if (percent) percent.textContent = `${pct}%`;
      await sleep(34);
    }
    conclude(false);
  };

  run();
})();
