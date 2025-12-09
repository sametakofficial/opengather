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
    certification: "G",
    traktId: "",
    runtime: "1h 30m",
    otherIds: "",
    genres: "Animation, Family, Adventure, Fantasy",
    production: "Walt Disney Pictures",
    country: "United States",
    languages: "English",
    ratingText: "8.0/10 (169,456 Votes)",
    tagline:
      "Sokak çocuğu Alaaddin, sihirli bir lamba ve Cin sayesinde prenses Yasemin’in kalbini kazanmaya çalışır.",
    movieSet: "Aladdin Collection",
    tvShowLink: "",
    edition: "0",
    tags:
      "magic, villain, parrot, musical, tiger, sultan, flying carpet, wish, cartoon, princess, love, monkey, nostalgic, arab, aftercreditstinger, genie, arabian",
    paths: "data/srv/downloads/finished/movies/aladdin (1992).mkv",
    note: ""
  },
  {
    id: "mr_mrs_smith",
    title: "Bay ve Bayan Smith",
    originalTitle: "Mr. & Mrs. Smith",
    year: "2005",
    imdbId: "tt0356910",
    tmdbId: "787",
    releaseDate: "Jun 10, 2005",
    certification: "PG-13",
    traktId: "",
    runtime: "2h 0m",
    otherIds: "",
    genres: "Action, Comedy, Thriller",
    production: "Regency Enterprises",
    country: "United States",
    languages: "English",
    ratingText: "6.5/10",
    tagline:
      "Birbirinden habersiz iki kiralık katil, evli olduklarını ve hedeflerinin bazen birbirleri olduğunu keşfeder.",
    movieSet: "",
    tvShowLink: "",
    edition: "0",
    tags: "marriage, hitman, action, comedy, couple",
    paths:
      "data/srv/downloads/finished/movies/mr & mrs smith (2005).mkv",
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
      "Gerçek sandığın dünya aslında bir simülasyon. Neo, Morpheus ve Trinity ile birlikte sisteme karşı savaşır.",
    movieSet: "The Matrix Collection",
    tvShowLink: "",
    edition: "0",
    tags:
      "simulation, cyberpunk, hacker, kungfu, dystopia, chosen one, slow motion",
    paths:
      "data/srv/downloads/finished/movies/the matrix (1999).mkv",
    note: ""
  },
  {
    id: "inception",
    title: "Başlangıç",
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
      "Profesyonel hırsız Cobb, rüya içinde rüya tekniğiyle bilinçaltına fikir yerleştirmek için son bir iş alır.",
    movieSet: "",
    tvShowLink: "",
    edition: "0",
    tags: "dream, subconscious, heist, mind-bending, layered reality",
    paths:
      "data/srv/downloads/finished/movies/inception (2010).mkv",
    note: ""
  },
  {
    id: "toy_story",
    title: "Oyuncak Hikayesi",
    originalTitle: "Toy Story",
    year: "1995",
    imdbId: "tt0114709",
    tmdbId: "862",
    releaseDate: "Nov 22, 1995",
    certification: "G",
    traktId: "",
    runtime: "1h 21m",
    otherIds: "",
    genres: "Animation, Family, Comedy",
    production: "Pixar Animation Studios",
    country: "United States",
    languages: "English",
    ratingText: "8.3/10",
    tagline:
      "İnsanlar ortadan kaybolduğunda canlanan oyuncaklar, aralarına yeni katılan Buzz ile birlikte maceraya atılır.",
    movieSet: "Toy Story Collection",
    tvShowLink: "",
    edition: "0",
    tags: "toy, friendship, jealousy, nostalgia, animation",
    paths:
      "data/srv/downloads/finished/movies/toy story (1995).mkv",
    note: ""
  },
  {
    id: "lion_king",
    title: "Aslan Kral",
    originalTitle: "The Lion King",
    year: "1994",
    imdbId: "tt0110357",
    tmdbId: "8587",
    releaseDate: "Jun 24, 1994",
    certification: "G",
    traktId: "",
    runtime: "1h 28m",
    otherIds: "",
    genres: "Animation, Family, Drama",
    production: "Walt Disney Pictures",
    country: "United States",
    languages: "English",
    ratingText: "8.5/10",
    tagline:
      "Genç aslan Simba, babasının trajik ölümünden sonra sürgüne gider ve krallığını geri almak için büyümek zorundadır.",
    movieSet: "The Lion King Collection",
    tvShowLink: "",
    edition: "0",
    tags: "lion, kingdom, responsibility, coming of age, africa",
    paths:
      "data/srv/downloads/finished/movies/the lion king (1994).mkv",
    note: ""
  },
  {
    id: "interstellar",
    title: "Yıldızlararası",
    originalTitle: "Interstellar",
    year: "2014",
    imdbId: "tt0816692",
    tmdbId: "157336",
    releaseDate: "Nov 07, 2014",
    certification: "PG-13",
    traktId: "",
    runtime: "2h 49m",
    otherIds: "",
    genres: "Adventure, Drama, Science Fiction",
    production: "Paramount Pictures",
    country: "United States",
    languages: "English",
    ratingText: "8.6/10",
    tagline:
      "İnsanlık yok olmanın eşiğindeyken, bir grup astronot yeni bir yuva bulmak için solucan deliğinden geçer.",
    movieSet: "",
    tvShowLink: "",
    edition: "0",
    tags: "space, wormhole, time dilation, father daughter, sci-fi",
    paths:
      "data/srv/downloads/finished/movies/interstellar (2014).mkv",
    note: ""
  },
  {
    id: "avatar",
    title: "Avatar",
    originalTitle: "Avatar",
    year: "2009",
    imdbId: "tt0499549",
    tmdbId: "19995",
    releaseDate: "Dec 18, 2009",
    certification: "PG-13",
    traktId: "",
    runtime: "2h 42m",
    otherIds: "",
    genres: "Action, Adventure, Fantasy, Science Fiction",
    production: "20th Century Fox",
    country: "United States",
    languages: "English",
    ratingText: "7.8/10",
    tagline:
      "Paraplejik asker Jake, Pandora gezegeninde avatar bedeniyle yeni bir hayat bulur ve seçimini yapmak zorunda kalır.",
    movieSet: "Avatar Collection",
    tvShowLink: "",
    edition: "0",
    tags: "alien planet, avatar, environment, war, romance",
    paths:
      "data/srv/downloads/finished/movies/avatar (2009).mkv",
    note: ""
  },
  {
    id: "gladiator",
    title: "Gladyatör",
    originalTitle: "Gladiator",
    year: "2000",
    imdbId: "tt0172495",
    tmdbId: "98",
    releaseDate: "May 05, 2000",
    certification: "R",
    traktId: "",
    runtime: "2h 35m",
    otherIds: "",
    genres: "Action, Drama, Adventure",
    production: "DreamWorks Pictures",
    country: "United States",
    languages: "English",
    ratingText: "8.5/10",
    tagline:
      "İhanete uğrayıp köle edilen general Maximus, ailesinin intikamını almak için arena şampiyonu olur.",
    movieSet: "",
    tvShowLink: "",
    edition: "0",
    tags: "roman empire, revenge, gladiator, arena, honor",
    paths:
      "data/srv/downloads/finished/movies/gladiator (2000).mkv",
    note: ""
  },
  {
    id: "pulp_fiction",
    title: "Ucuz Roman",
    originalTitle: "Pulp Fiction",
    year: "1994",
    imdbId: "tt0110912",
    tmdbId: "680",
    releaseDate: "Oct 14, 1994",
    certification: "R",
    traktId: "",
    runtime: "2h 34m",
    otherIds: "",
    genres: "Crime, Drama",
    production: "Miramax",
    country: "United States",
    languages: "English",
    ratingText: "8.9/10",
    tagline:
      "Birbirine gevşekçe bağlı suç hikayeleri, Los Angeles’ın karanlık sokaklarında kesişir.",
    movieSet: "",
    tvShowLink: "",
    edition: "0",
    tags: "hitman, non linear, crime, dialogue heavy, diner",
    paths:
      "data/srv/downloads/finished/movies/pulp fiction (1994).mkv",
    note: ""
  },
  {
    id: "dark_knight",
    title: "Kara Şövalye",
    originalTitle: "The Dark Knight",
    year: "2008",
    imdbId: "tt0468569",
    tmdbId: "155",
    releaseDate: "Jul 18, 2008",
    certification: "PG-13",
    traktId: "",
    runtime: "2h 32m",
    otherIds: "",
    genres: "Action, Crime, Drama",
    production: "Warner Bros.",
    country: "United States",
    languages: "English",
    ratingText: "9.0/10",
    tagline:
      "Batman, Joker’in Gotham’ı kaosa sürükleyen planını durdurmaya çalışırken kendi sınırlarıyla yüzleşir.",
    movieSet: "The Dark Knight Collection",
    tvShowLink: "",
    edition: "0",
    tags: "joker, vigilantism, chaos, moral dilemma, superhero",
    paths:
      "data/srv/downloads/finished/movies/the dark knight (2008).mkv",
    note: ""
  },
  {
    id: "fight_club",
    title: "Dövüş Kulübü",
    originalTitle: "Fight Club",
    year: "1999",
    imdbId: "tt0137523",
    tmdbId: "550",
    releaseDate: "Oct 15, 1999",
    certification: "R",
    traktId: "",
    runtime: "2h 19m",
    otherIds: "",
    genres: "Drama",
    production: "20th Century Fox",
    country: "United States",
    languages: "English",
    ratingText: "8.8/10",
    tagline:
      "İsimsiz anlatıcı, karizmatik Tyler Durden ile birlikte sistem karşıtı gizli bir dövüş kulübü kurar.",
    movieSet: "",
    tvShowLink: "",
    edition: "0",
    tags: "identity, consumerism, anarchism, underground club",
    paths:
      "data/srv/downloads/finished/movies/fight club (1999).mkv",
    note: ""
  },
  {
    id: "forrest_gump",
    title: "Forrest Gump",
    originalTitle: "Forrest Gump",
    year: "1994",
    imdbId: "tt0109830",
    tmdbId: "13",
    releaseDate: "Jul 06, 1994",
    certification: "PG-13",
    traktId: "",
    runtime: "2h 22m",
    otherIds: "",
    genres: "Comedy, Drama, Romance",
    production: "Paramount Pictures",
    country: "United States",
    languages: "English",
    ratingText: "8.8/10",
    tagline:
      "Sıcak kalpli Forrest, tesadüflerle dolu hayatında Amerika tarihinin önemli anlarına istemeden tanıklık eder.",
    movieSet: "",
    tvShowLink: "",
    edition: "0",
    tags: "life story, vietnam war, running, love, destiny",
    paths:
      "data/srv/downloads/finished/movies/forrest gump (1994).mkv",
    note: ""
  },
  {
    id: "godfather",
    title: "Baba",
    originalTitle: "The Godfather",
    year: "1972",
    imdbId: "tt0068646",
    tmdbId: "238",
    releaseDate: "Mar 24, 1972",
    certification: "R",
    traktId: "",
    runtime: "2h 55m",
    otherIds: "",
    genres: "Crime, Drama",
    production: "Paramount Pictures",
    country: "United States",
    languages: "English, Italian",
    ratingText: "9.2/10",
    tagline:
      "Corleone ailesinin başı Vito, güç dengeleri değişirken oğlu Michael’in karanlık dünyaya inişine tanık olur.",
    movieSet: "The Godfather Collection",
    tvShowLink: "",
    edition: "0",
    tags: "mafia, family, loyalty, power, sicily",
    paths:
      "data/srv/downloads/finished/movies/the godfather (1972).mkv",
    note: ""
  },
  {
    id: "godfather2",
    title: "Baba 2",
    originalTitle: "The Godfather Part II",
    year: "1974",
    imdbId: "tt0071562",
    tmdbId: "240",
    releaseDate: "Dec 20, 1974",
    certification: "R",
    traktId: "",
    runtime: "3h 22m",
    otherIds: "",
    genres: "Crime, Drama",
    production: "Paramount Pictures",
    country: "United States",
    languages: "English, Italian",
    ratingText: "9.0/10",
    tagline:
      "Michael Corleone imparatorluğu genişletirken, genç Vito’nun yükselişinin paralel hikayesi anlatılır.",
    movieSet: "The Godfather Collection",
    tvShowLink: "",
    edition: "0",
    tags: "mafia, sequel, corruption, family, flashback",
    paths:
      "data/srv/downloads/finished/movies/the godfather part ii (1974).mkv",
    note: ""
  },
  {
    id: "shawshank",
    title: "Esaretin Bedeli",
    originalTitle: "The Shawshank Redemption",
    year: "1994",
    imdbId: "tt0111161",
    tmdbId: "278",
    releaseDate: "Sep 23, 1994",
    certification: "R",
    traktId: "",
    runtime: "2h 22m",
    otherIds: "",
    genres: "Drama, Crime",
    production: "Castle Rock Entertainment",
    country: "United States",
    languages: "English",
    ratingText: "9.3/10",
    tagline:
      "Haksız yere müebbet yiyen Andy, Shawshank hapishanesinde umudunu kaybetmeden özgürlüğün yolunu arar.",
    movieSet: "",
    tvShowLink: "",
    edition: "0",
    tags: "prison, hope, friendship, escape, narration",
    paths:
      "data/srv/downloads/finished/movies/the shawshank redemption (1994).mkv",
    note: ""
  },
  {
    id: "back_future",
    title: "Geleceğe Dönüş",
    originalTitle: "Back to the Future",
    year: "1985",
    imdbId: "tt0088763",
    tmdbId: "105",
    releaseDate: "Jul 03, 1985",
    certification: "PG",
    traktId: "",
    runtime: "1h 56m",
    otherIds: "",
    genres: "Adventure, Comedy, Science Fiction",
    production: "Universal Pictures",
    country: "United States",
    languages: "English",
    ratingText: "8.5/10",
    tagline:
      "Marty McFly ve çılgın bilim insanı Doc Brown, DeLorean ile zamanda yolculuk yaparken geçmişi düzeltmeye çalışır.",
    movieSet: "Back to the Future Collection",
    tvShowLink: "",
    edition: "0",
    tags: "time travel, 80s, high school, paradox",
    paths:
      "data/srv/downloads/finished/movies/back to the future (1985).mkv",
    note: ""
  },
  {
    id: "t2",
    title: "Terminatör 2: Mahşer Günü",
    originalTitle: "Terminator 2: Judgment Day",
    year: "1991",
    imdbId: "tt0103064",
    tmdbId: "280",
    releaseDate: "Jul 03, 1991",
    certification: "R",
    traktId: "",
    runtime: "2h 17m",
    otherIds: "",
    genres: "Action, Science Fiction",
    production: "TriStar Pictures",
    country: "United States",
    languages: "English",
    ratingText: "8.5/10",
    tagline:
      "Yeniden programlanmış bir Terminator, John Connor’ı daha gelişmiş bir ölüm makinesinden korumak için geçmişe gönderilir.",
    movieSet: "Terminator Collection",
    tvShowLink: "",
    edition: "0",
    tags: "robot, time travel, apocalypse, mother son, chase",
    paths:
      "data/srv/downloads/finished/movies/terminator 2 judgment day (1991).mkv",
    note: ""
  },
  {
    id: "spirited_away",
    title: "Ruhların Kaçışı",
    originalTitle: "Spirited Away",
    year: "2001",
    imdbId: "tt0245429",
    tmdbId: "129",
    releaseDate: "Jul 20, 2001",
    certification: "PG",
    traktId: "",
    runtime: "2h 5m",
    otherIds: "",
    genres: "Animation, Family, Fantasy",
    production: "Studio Ghibli",
    country: "Japan",
    languages: "Japanese",
    ratingText: "8.6/10",
    tagline:
      "Chihiro, ailesiyle gittiği terk edilmiş bir eğlence parkında ruhlar dünyasında kaybolur ve oradan kurtulmanın yolunu arar.",
    movieSet: "",
    tvShowLink: "",
    edition: "0",
    tags: "bathhouse, spirit world, coming of age, ghibli",
    paths:
      "data/srv/downloads/finished/movies/spirited away (2001).mkv",
    note: ""
  },
  {
    id: "incredibles",
    title: "İnanılmaz Aile",
    originalTitle: "The Incredibles",
    year: "2004",
    imdbId: "tt0317705",
    tmdbId: "9806",
    releaseDate: "Nov 05, 2004",
    certification: "PG",
    traktId: "",
    runtime: "1h 55m",
    otherIds: "",
    genres: "Animation, Action, Adventure, Family",
    production: "Pixar Animation Studios",
    country: "United States",
    languages: "English",
    ratingText: "8.0/10",
    tagline:
      "Süper güçlerini saklamak zorunda kalan Parr ailesi, yeni bir tehditle birlikte tekrar kostümlerini giymek zorundadır.",
    movieSet: "The Incredibles Collection",
    tvShowLink: "",
    edition: "0",
    tags: "superhero family, secret identity, midlife crisis",
    paths:
      "data/srv/downloads/finished/movies/the incredibles (2004).mkv",
    note: ""
  }
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
