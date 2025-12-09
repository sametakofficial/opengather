// Dummy film datası
const movies = [
  {
    id: "aladdin",
    title: "Alaaddin",
    originalTitle: "Aladdin",
    year: "1992",
    imdbId: "tt0103639",
    tmdbId: "812",
    releaseDate: "Nov 25, 1992",
    certification: "0",
    traktId: "",
    runtime: "1h 30m",
    otherIds: "",
    genres: "Animation, Family, Adventure, Fantasy",
    production: "Walt Disney Pictures",
    country: "United States",
    languages: "English",
    ratingText: "8.0/10 (169,456 Votes)",
    tagline:
      "Agrabah şehrinin kalbinde, köylü Alaaddin ve onun yaramaz maymunu Abu, özgür ruhlu prenses Yasemin'i kurtarmaya çalışır. Sihirli lamba, Cin ve kötü kalpli vezir Câfer ile macera başlar.",
    movieSet: "Alaaddin Collection",
    tvShowLink: "Nov 25, 1992",
    edition: "0",
    tags:
      "magic, villain, parrot, musical, tiger, sultan, flying carpet, wish, cartoon, princess, love, monkey, nostalgic, arab, aftercreditstinger, genie, arabian",
    paths: "Media/downloads/downloading/movies",
    note: ""
  },
  {
    id: "matrix",
    title: "Matrix",
    originalTitle: "The Matrix",
    year: "1999",
    imdbId: "tt0133093",
    tmdbId: "603",
    releaseDate: "Mar 31, 1999",
    certification: "R",
    traktId: "",
    runtime: "2h 16m",
    otherIds: "",
    genres: "Action, Science Fiction",
    production: "Warner Bros.",
    country: "United States",
    languages: "English",
    ratingText: "8.7/10",
    tagline:
      "Gerçek dünya bir simülasyondur. Neo, Morpheus ve Trinity ile birlikte bu gerçeği keşfederken sistemle savaşmak zorunda kalır.",
    movieSet: "The Matrix Collection",
    tvShowLink: "",
    edition: "0",
    tags:
      "simulation, cyberpunk, hacker, kungfu, slow motion, dystopia, chosen one",
    paths: "data/srv/downloads/finished/movies/the matrix (1999).mkv",
    note: ""
  },
  {
    id: "inception",
    title: "Inception",
    originalTitle: "Inception",
    year: "2010",
    imdbId: "tt1375666",
    tmdbId: "27205",
    releaseDate: "Jul 16, 2010",
    certification: "PG-13",
    traktId: "",
    runtime: "2h 28m",
    otherIds: "",
    genres: "Action, Science Fiction, Thriller",
    production: "Warner Bros.",
    country: "United States",
    languages: "English",
    ratingText: "8.8/10",
    tagline:
      "Rüya içinde rüya kavramı ile bilinçaltına fikir yerleştirilir. Cobb ve ekibi son bir iş için yola çıkar.",
    movieSet: "",
    tvShowLink: "",
    edition: "0",
    tags: "dream, subconscious, heist, mind-bending",
    paths: "data/srv/downloads/finished/movies/inception (2010).mkv",
    note: ""
  }
  // diğer satırlar için istersen burada genişletebilirsin,
  // eşleşmeyen id'ler basitçe ilk filme fallback yapar.
];

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
        const firstCell = row.querySelector("td .path-cell-content, td");
        const text = (firstCell?.textContent || "").toLowerCase();
        row.style.display = text.includes(query) ? "" : "none";
      });
    });
  });
}

// Files : N sayaçlarını doldur
function setupFileCounters() {
  const footers = document.querySelectorAll(
    ".panel-left-footer[data-count-table]"
  );
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

// Sağ paneli seçilen filme göre güncelle
function updateMovieDetail(movieId) {
  let movie = movies.find((m) => m.id === movieId);
  if (!movie) {
    movie = movies[0]; // fallback
  }

  const setText = (id, value) => {
    const el = document.getElementById(id);
    if (el) el.textContent = value || "";
  };

  setText("detail-title", movie.title);
  setText("detail-subtitle", movie.originalTitle);
  setText("detail-year", movie.year);
  setText("detail-imdb-id", movie.imdbId);
  setText("detail-release-date", movie.releaseDate);
  setText("detail-tmdb-id", movie.tmdbId);
  setText("detail-certification", movie.certification);
  setText("detail-trakt-id", movie.traktId);
  setText("detail-runtime", movie.runtime);
  setText("detail-other-ids", movie.otherIds);
  setText("detail-genres", movie.genres);
  setText("detail-production", movie.production);
  setText("detail-country", movie.country);
  setText("detail-languages", movie.languages);
  setText("detail-rating-text", movie.ratingText);
  setText("detail-tagline", movie.tagline);
  setText("detail-movie-set", movie.movieSet);
  setText("detail-tv-link", movie.tvShowLink);
  setText("detail-edition", movie.edition);
  setText("detail-tags", movie.tags);
  setText("detail-paths", movie.paths);
  setText("detail-note", movie.note);
}

// Sol tablodaki satır seçimi
function setupRowSelection() {
  const table = document.getElementById("input-path-table");
  if (!table) return;

  const rows = table.querySelectorAll("tbody tr");

  const clearSelection = () => {
    rows.forEach((row) => row.classList.remove("is-selected"));
  };

  rows.forEach((row) => {
    row.addEventListener("click", () => {
      clearSelection();
      row.classList.add("is-selected");
      const movieId = row.getAttribute("data-movie-id");
      updateMovieDetail(movieId);
    });
  });

  // Default: ilk satırı seç
  const firstRow = rows[0];
  if (firstRow) {
    firstRow.classList.add("is-selected");
    updateMovieDetail(firstRow.getAttribute("data-movie-id"));
  }
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
  setupRowSelection();
});
