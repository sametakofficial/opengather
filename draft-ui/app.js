// Basit tab sistemi
function setupTabs(groupName) {
  const tabs = document.querySelectorAll('[data-tab-group="' + groupName + '"]');
  if (!tabs.length) return;

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const target = tab.getAttribute("data-tab-target");

      // Tab butonlarının aktif sınıfı
      tabs.forEach((t) => t.classList.remove("is-active"));
      tab.classList.add("is-active");

      // İçerik bloklarını gizle/göster
      const contents = document.querySelectorAll(
        '[data-tab-content-group="' + groupName + '"]'
      );
      contents.forEach((c) => {
        if (c.getAttribute("data-tab-content") === target) {
          c.hidden = false;
        } else {
          c.hidden = true;
        }
      });
    });
  });
}

// Filtre inputlarını kur
function setupFilters() {
  const inputs = document.querySelectorAll(".js-filter-input");
  inputs.forEach((input) => {
    const tableId = input.getAttribute("data-target-table");
    const table = document.getElementById(tableId);
    if (!table) return;

    input.addEventListener("input", () => {
      const query = input.value.toLowerCase();
      const rows = table.querySelectorAll("tbody tr");
      rows.forEach((row) => {
        const firstCell = row.querySelector("td");
        const text = (firstCell?.textContent || "").toLowerCase();
        row.style.display = text.includes(query) ? "" : "none";
      });
    });
  });
}

// Files : N sayaçlarını doldur
function setupFileCounters() {
  const footers = document.querySelectorAll(".panel-left-footer[data-count-table]");
  footers.forEach((footer) => {
    const tableId = footer.getAttribute("data-count-table");
    const table = document.getElementById(tableId);
    if (!table) {
      footer.textContent = "Files : 0";
      return;
    }
    const rows = table.querySelectorAll("tbody tr");
    footer.textContent = "Files : " + rows.length;
  });
}

// Init
document.addEventListener("DOMContentLoaded", () => {
  // Sol panel tabları
  setupTabs("io");
  setupTabs("input-sub");
  setupTabs("output-sub");

  // Sağ panel tabları
  setupTabs("right-main");
  setupTabs("right-all-sub");

  setupFilters();
  setupFileCounters();
});
