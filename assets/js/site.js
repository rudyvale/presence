(() => {
  "use strict";

  if (window.location.pathname.endsWith("/index.html")) {
    window.history.replaceState(null, "", window.location.pathname.slice(0, -10) + window.location.search + window.location.hash);
  }

  const toggle = document.querySelector(".nav__toggle");
  const menu = document.getElementById("nav-menu");
  if (toggle && menu) {
    const closeMenu = () => {
      const wasOpen = menu.classList.contains("is-open");
      menu.classList.remove("is-open");
      toggle.setAttribute("aria-expanded", "false");
      toggle.setAttribute("aria-label", "Menu");
      return wasOpen;
    };

    toggle.addEventListener("click", () => {
      const open = menu.classList.toggle("is-open");
      toggle.setAttribute("aria-expanded", String(open));
      toggle.setAttribute("aria-label", open ? "Close menu" : "Menu");
      if (open) {
        const firstLink = menu.querySelector("a");
        if (firstLink && typeof firstLink.focus === "function") {
          if (typeof window.requestAnimationFrame === "function") {
            window.requestAnimationFrame(() => firstLink.focus());
          } else {
            firstLink.focus();
          }
        }
      }
    });

    menu.addEventListener("click", (event) => {
      if (event.target.closest("a")) closeMenu();
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && closeMenu()) toggle.focus();
    });

    document.addEventListener("click", (event) => {
      if (!menu.contains(event.target) && !toggle.contains(event.target)) closeMenu();
    });

    window.addEventListener("resize", () => {
      if (window.innerWidth > 900) closeMenu();
    });
  }

  const year = document.querySelector("[data-year]");
  if (year) year.textContent = String(new Date().getFullYear());

  const publicationMonths = Object.freeze([
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
  ]);

  const safePublicationDate = (value) => {
    if (typeof value !== "string") return null;
    const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
    if (!match) return null;

    const yearValue = Number(match[1]);
    const monthValue = Number(match[2]);
    const dayValue = Number(match[3]);
    if (yearValue < 1 || monthValue < 1 || monthValue > 12 || dayValue < 1) return null;

    const leapYear = yearValue % 4 === 0 && (yearValue % 100 !== 0 || yearValue % 400 === 0);
    const daysInMonth = [31, leapYear ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
    return dayValue <= daysInMonth[monthValue - 1] ? value : null;
  };

  const formatPublicationDate = (value) => {
    const date = safePublicationDate(value);
    if (!date) return null;
    const [yearValue, monthValue, dayValue] = date.split("-");
    return `${publicationMonths[Number(monthValue) - 1]} ${Number(dayValue)}, ${yearValue}`;
  };

  const makePublicationTime = (value, className = "") => {
    const date = safePublicationDate(value);
    const label = date && formatPublicationDate(date);
    if (!date || !label) return null;

    const time = document.createElement("time");
    if (className) time.className = className;
    time.dateTime = date;
    time.textContent = label;
    return time;
  };

  const motionSelector = [
    ".editorial-catalog .catalog-heading",
    ".featured-row",
    ".latest-column",
    ".latest-row",
    ".index-intro > *",
    ".index-route",
    ".index-principles > *",
    ".archive-header > *",
    ".archive-controls",
    ".archive-row",
    ".newsroom-hero__inner > *",
    ".section__head > *",
    ".news-filter",
    ".news-card",
    ".page-hero__inner > *",
    ".about-grid > article",
    ".article__cat",
    ".article__title",
    ".article__meta",
    ".article__hero-media",
    ".article__image",
    ".article__body h2",
    ".article__body blockquote",
    ".article__callout",
    ".article__matrix",
    ".author",
    ".sidebar",
    ".contact-intro",
    ".contact-form"
  ].join(",");

  const motionRoot = document.documentElement;
  if (
    motionRoot?.classList &&
    typeof document.querySelectorAll === "function"
  ) {
    let reduceMotion = false;
    if (typeof window.matchMedia === "function") {
      try {
        reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      } catch (_error) {
        reduceMotion = false;
      }
    }
    let motionObserver = null;

    if (!reduceMotion && typeof window.IntersectionObserver === "function") {
      try {
        motionObserver = new window.IntersectionObserver((entries) => {
          entries.forEach((entry) => {
            if (!entry.isIntersecting && entry.intersectionRatio <= 0) return;
            entry.target.classList.add("is-visible");
            motionObserver?.unobserve(entry.target);
          });
        }, {
          threshold: 0.1,
          rootMargin: "0px 0px -8% 0px"
        });
      } catch (_error) {
        motionObserver = null;
      }
    }

    const registerMotionTargets = () => {
      let delay = 0;
      document.querySelectorAll(motionSelector).forEach((element) => {
        if (!element.classList || element.classList.contains("motion-target")) return;
        element.classList.add("motion-target", `motion-delay-${delay % 6}`);
        delay += 1;
        if (!motionObserver) {
          element.classList.add("is-visible");
          return;
        }
        try {
          motionObserver.observe(element);
        } catch (_error) {
          element.classList.add("is-visible");
        }
      });
    };

    motionRoot.classList.add("motion-ready");
    registerMotionTargets();

    if (typeof window.MutationObserver === "function") {
      let motionFrame = null;
      try {
        new window.MutationObserver(() => {
          if (motionFrame !== null) return;
          if (typeof window.requestAnimationFrame !== "function") {
            registerMotionTargets();
            return;
          }
          motionFrame = window.requestAnimationFrame(() => {
            motionFrame = null;
            registerMotionTargets();
          });
        }).observe(document.body, { childList: true, subtree: true });
      } catch (_error) {
        registerMotionTargets();
      }
    }
  }

  const readingArticle = document.querySelector("main.article-layout > article");
  const articleMeta = readingArticle?.querySelector(".article__meta");
  if (articleMeta && !articleMeta.querySelector("time")) {
    let articleFilename = window.location.pathname.replace(/\/(?:index\.html)?$/, "").split("/").pop() || "";
    try {
      articleFilename = decodeURIComponent(articleFilename);
    } catch (_error) {
      articleFilename = "";
    }

    const filenameDate = /^(\d{4}-\d{2}-\d{2})_[a-z0-9]+(?:-[a-z0-9]+)*(?:\.html)?$/.exec(articleFilename)?.[1];
    const publicationTime = makePublicationTime(filenameDate);
    if (publicationTime) {
      articleMeta.prepend(publicationTime, document.createTextNode(" · "));
    }
  }

  if (readingArticle) {
    const readingProgress = document.createElement("div");
    readingProgress.className = "reading-progress";

    const readingProgressBar = document.createElement("progress");
    readingProgressBar.className = "reading-progress__meter";
    readingProgressBar.max = 100;
    readingProgressBar.value = 0;
    readingProgressBar.setAttribute("role", "progressbar");
    readingProgressBar.setAttribute("aria-label", "Article reading progress");
    readingProgressBar.setAttribute("aria-valuemin", "0");
    readingProgressBar.setAttribute("aria-valuemax", "100");
    readingProgressBar.setAttribute("aria-valuenow", "0");
    readingProgressBar.setAttribute("aria-valuetext", "0% read");

    const readingProgressValue = document.createElement("span");
    readingProgressValue.className = "reading-progress__value";
    readingProgressValue.setAttribute("aria-hidden", "true");
    readingProgressValue.textContent = "0%";
    readingProgress.append(readingProgressBar, readingProgressValue);

    const navigation = document.querySelector(".nav");
    if (navigation) navigation.after(readingProgress);
    else document.body.prepend(readingProgress);

    let readingProgressFrame = null;
    let previousReadingProgress = -1;

    const finiteNumber = (value) => Number.isFinite(Number(value)) ? Number(value) : 0;

    const calculateReadingProgress = () => {
      const bounds = readingArticle.getBoundingClientRect();
      const scrollTop = Math.max(
        0,
        finiteNumber(window.scrollY || document.documentElement.scrollTop)
      );
      const viewportHeight = Math.max(
        0,
        finiteNumber(window.innerHeight || document.documentElement.clientHeight)
      );
      const measuredHeight = finiteNumber(bounds.height) ||
        finiteNumber(bounds.bottom) - finiteNumber(bounds.top);
      const articleHeight = Math.max(
        0,
        measuredHeight,
        finiteNumber(readingArticle.offsetHeight),
        finiteNumber(readingArticle.scrollHeight)
      );
      if (articleHeight === 0) return 0;

      const articleTop = scrollTop + finiteNumber(bounds.top);
      const scrollableArticleHeight = articleHeight - viewportHeight;
      let ratio;

      if (scrollableArticleHeight > 0) {
        ratio = (scrollTop - articleTop) / scrollableArticleHeight;
      } else if (scrollTop >= articleTop) {
        ratio = 1;
      } else {
        ratio = (scrollTop + viewportHeight - articleTop) / articleHeight;
      }

      if (!Number.isFinite(ratio)) return 0;
      return Math.round(Math.min(1, Math.max(0, ratio)) * 100);
    };

    const updateReadingProgress = () => {
      readingProgressFrame = null;
      const value = calculateReadingProgress();
      if (value === previousReadingProgress) return;
      previousReadingProgress = value;
      readingProgressBar.value = value;
      readingProgressBar.setAttribute("aria-valuenow", String(value));
      readingProgressBar.setAttribute("aria-valuetext", `${value}% read`);
      readingProgressValue.textContent = `${value}%`;
    };

    const scheduleReadingProgress = () => {
      if (readingProgressFrame !== null) return;
      readingProgressFrame = window.requestAnimationFrame(updateReadingProgress);
    };

    window.addEventListener("scroll", scheduleReadingProgress, { passive: true });
    window.addEventListener("resize", scheduleReadingProgress, { passive: true });
    window.addEventListener("pageshow", scheduleReadingProgress);
    window.addEventListener("load", scheduleReadingProgress);
    if (typeof window.ResizeObserver === "function") {
      new window.ResizeObserver(scheduleReadingProgress).observe(readingArticle);
    }
    scheduleReadingProgress();
  }

  const cleanText = (value, maximum) => (
    typeof value === "string" &&
    value.length <= maximum &&
    value === value.trim() &&
    !/[\u0000-\u001f\u007f]/.test(value)
      ? value
      : null
  );

  const safeStoryUrl = (value) => (
    typeof value === "string" &&
    /^\/articles\/\d{4}-\d{2}-\d{2}_[a-z0-9]+(?:-[a-z0-9]+)*\/$/.test(value)
      ? value
      : null
  );

  const safeStoryImage = (value) => (
    typeof value === "string" &&
    /^\/assets\/img\/articles\/\d{4}-\d{2}-\d{2}_[a-z0-9]+(?:-[a-z0-9]+)*\/[a-z0-9]+(?:-[a-z0-9]+)*\.(?:avif|jpe?g|png|webp)$/.test(value)
      ? value
      : null
  );

  const safeReadingTime = (value) => {
    const readingTime = cleanText(value, 32);
    const match = readingTime && /^([1-9]\d*) min read$/.exec(readingTime);
    return match && Number.isSafeInteger(Number(match[1])) ? readingTime : null;
  };

  const safeStory = (story) => {
    if (!story || Object.getPrototypeOf(story) !== Object.prototype) return null;
    const title = cleanText(story.title, 300);
    const author = cleanText(story.author ?? "", 300);
    const summary = cleanText(story.summary, 1200);
    const category = cleanText(story.category, 40);
    const type = cleanText(story.type, 100);
    const date = safePublicationDate(cleanText(story.date, 10));
    const readingTime = safeReadingTime(story.readingTime);
    const url = safeStoryUrl(story.url);
    const image = safeStoryImage(story.image);
    const imageAlt = image ? cleanText(story.imageAlt, 300) : null;
    const featuredRank = Number.isSafeInteger(story.featuredRank) &&
      story.featuredRank >= 1 && story.featuredRank <= 100
        ? story.featuredRank
        : null;
    if (!title || author === null || !summary || !category || !type || !date || !readingTime || !url) return null;
    if (!["crypto", "technology", "companies"].includes(category)) return null;
    if (!type.toUpperCase().includes("PRESENCE") && !url.startsWith("/articles/")) return null;
    return Object.freeze({
      ...story,
      title,
      author,
      summary,
      category,
      type,
      date,
      readingTime,
      url,
      image,
      imageAlt,
      featuredRank
    });
  };

  const stories = Array.isArray(window.PRESENCE_NEWS)
    ? window.PRESENCE_NEWS.map(safeStory).filter(Boolean)
    : [];

  const appendText = (parent, tag, className, value) => {
    const element = document.createElement(tag);
    if (className) element.className = className;
    element.textContent = value;
    parent.append(element);
    return element;
  };

  const makeStoryLink = (story) => {
    const link = document.createElement("a");
    link.href = story.url;
    link.textContent = story.title;
    return link;
  };

  const appendStoryMeta = (parent, story) => {
    const meta = document.createElement("p");
    meta.className = "story-author";
    if (story.author) meta.append(document.createTextNode(`${story.author} · `));

    const publicationTime = makePublicationTime(story.date);
    if (publicationTime) meta.append(publicationTime, document.createTextNode(" · "));
    meta.append(document.createTextNode(story.readingTime));
    parent.append(meta);
    return meta;
  };

  const publishedStories = [...stories].sort((left, right) => (
    right.date.localeCompare(left.date) || left.url.localeCompare(right.url)
  ));
  const editorialStories = publishedStories.filter((story) => story.promotable !== false);
  const featuredRoot = document.getElementById("featured-edits");
  const latestRoot = document.getElementById("latest-edits");

  if (featuredRoot && latestRoot && editorialStories.length) {
    const pinnedFeatured = editorialStories
      .filter((story) => story.featuredRank !== null)
      .sort((left, right) => (
        left.featuredRank - right.featuredRank ||
        right.date.localeCompare(left.date) ||
        left.url.localeCompare(right.url)
      ));
    const otherStories = editorialStories.filter((story) => story.featuredRank === null);
    const featured = [...pinnedFeatured, ...otherStories].slice(0, 3);
    const latestStories = editorialStories.slice(0, 4);

    const featuredRows = featured.map((story) => {
      const article = document.createElement("article");
      article.className = "featured-row";
      if (story.image) article.classList.add("featured-row--with-image");

      const main = document.createElement("div");
      main.className = "featured-row__main";
      const heading = document.createElement("h2");
      heading.append(makeStoryLink(story));
      main.append(heading);
      appendStoryMeta(main, story);

      if (story.image) {
        appendText(main, "p", "featured-row__summary", story.summary);

        const media = document.createElement("a");
        media.className = "featured-row__media";
        media.href = story.url;
        media.setAttribute("aria-label", `Read ${story.title}`);

        const image = document.createElement("img");
        image.src = story.image;
        image.alt = story.imageAlt || "";
        image.width = 1280;
        image.height = 720;
        image.decoding = "async";
        image.fetchPriority = "high";
        media.append(image);
        article.append(main, media);
      } else {
        article.append(main);
        appendText(article, "p", "featured-row__summary", story.summary);
      }
      return article;
    });

    const latestRows = latestStories.map((story) => {
      const article = document.createElement("article");
      article.className = "latest-row";
      const heading = document.createElement("h2");
      heading.append(makeStoryLink(story));
      article.append(heading);
      appendStoryMeta(article, story);
      return article;
    });

    featuredRoot.replaceChildren(...featuredRows);
    latestRoot.replaceChildren(...latestRows);
  }

  const ticker = document.querySelector("[data-story-ticker]");
  if (ticker && editorialStories.length) {
    const tickerRegion = ticker.closest(".story-ticker");
    const tickerControl = tickerRegion?.querySelector("[data-ticker-control]");
    const tickerStories = editorialStories.slice(0, 8);
    const makeSequence = (hidden = false) => {
      const sequence = document.createElement("div");
      sequence.className = "story-ticker__sequence";
      if (hidden) sequence.setAttribute("aria-hidden", "true");

      tickerStories.forEach((story, index) => {
        const link = document.createElement(hidden ? "span" : "a");
        link.className = "story-ticker__item";
        if (!hidden) link.href = story.url;
        const label = document.createElement("span");
        label.textContent = index === 0 ? "Latest" : story.category;
        link.append(label, document.createTextNode(story.title));
        sequence.append(link);
      });
      return sequence;
    };

    ticker.replaceChildren(makeSequence(), makeSequence(true));
    tickerRegion?.classList.add("is-ready");
    if (tickerControl) tickerControl.hidden = false;

    tickerControl?.addEventListener("click", () => {
      const paused = tickerRegion.classList.toggle("is-paused");
      tickerControl.textContent = paused ? "Play ticker" : "Pause ticker";
    });
  }

  const archiveRoot = document.querySelector("[data-archive-grid]");
  if (!archiveRoot) return;

  const archiveCount = document.querySelector("[data-archive-count]");
  const archiveStatus = document.querySelector("[data-archive-status]");
  const archiveControls = document.querySelector("[data-archive-controls]");
  const archiveMore = document.querySelector("[data-archive-more]");
  const archiveSearch = document.getElementById("archive-search");
  const archiveCategory = document.getElementById("archive-category");
  const archiveState = { items: [], visible: 24 };

  if (!archiveCount || !archiveStatus || !archiveControls || !archiveMore) return;

  const normalizeArchiveHash = () => {
    if (window.location.hash !== "#future-archive") return;
    const section = document.getElementById("search");
    if (!section) return;
    window.history.replaceState(null, "", window.location.pathname + window.location.search + "#search");
    section.scrollIntoView();
  };

  window.addEventListener("hashchange", normalizeArchiveHash);
  normalizeArchiveHash();

  try {
    if (archiveSearch && window.location && typeof window.location.search === "string") {
      const requestedAuthor = new URLSearchParams(window.location.search).get("author");
      const cleanAuthor = cleanText(requestedAuthor, 300);
      if (cleanAuthor) archiveSearch.value = cleanAuthor;
    }
  } catch (_error) {
    if (archiveSearch) archiveSearch.value = "";
  }

  const normalize = (value) => String(value || "").trim().toLocaleLowerCase("en");
  const categoryLabel = (category) => ({
    crypto: "Crypto",
    technology: "Technology",
    companies: "Companies"
  })[category] || "Technology";

  const makeArchiveRow = (item) => {
    const article = document.createElement("article");
    article.className = "archive-row";

    const meta = document.createElement("p");
    meta.className = "archive-row__meta";
    appendText(meta, "span", "", categoryLabel(item.category));
    const publicationTime = makePublicationTime(item.date);
    if (publicationTime) meta.append(publicationTime);
    const readingTime = safeReadingTime(item.readingTime);
    appendText(meta, "span", "", readingTime || item.source);

    const heading = document.createElement("h3");
    const link = document.createElement("a");
    link.href = item.localUrl;
    link.textContent = item.title;
    heading.append(link);

    const foot = document.createElement("div");
    foot.className = "archive-row__foot";
    if (item.authors) appendText(foot, "p", "story-author", item.authors);
    const sourceLink = document.createElement("a");
    sourceLink.className = "archive-row__source";
    sourceLink.href = item.localUrl;
    sourceLink.textContent = "Read article";
    sourceLink.setAttribute("aria-label", `Open ${item.title} on PRESENCE`);
    foot.append(sourceLink);

    article.append(meta, heading, foot);
    return article;
  };

  const filteredArchiveItems = () => {
    const query = normalize(archiveSearch?.value);
    const category = archiveCategory?.value || "all";
    return archiveState.items.filter((item) => {
      const matchesCategory = category === "all" || item.category === category;
      const haystack = normalize(`${item.title} ${item.authors}`);
      return matchesCategory && (!query || haystack.includes(query));
    });
  };

  const renderArchive = () => {
    const filtered = filteredArchiveItems();
    const visible = filtered.slice(0, archiveState.visible);
    archiveRoot.replaceChildren(...visible.map(makeArchiveRow));
    archiveMore.hidden = visible.length >= filtered.length;
    archiveStatus.textContent = filtered.length
      ? `Showing ${visible.length} of ${filtered.length} articles.`
      : "No articles match this search.";
  };

  const resetAndRenderArchive = () => {
    archiveState.visible = 24;
    renderArchive();
  };

  archiveSearch?.addEventListener("input", resetAndRenderArchive);
  archiveCategory?.addEventListener("change", resetAndRenderArchive);
  archiveMore?.addEventListener("click", () => {
    archiveState.visible += 24;
    renderArchive();
  });

  const localArchiveItems = publishedStories.map((story) => Object.freeze({
    key: `story:${story.url}`,
    title: story.title,
    authors: story.author,
    date: story.date,
    readingTime: story.readingTime,
    source: "PRESENCE",
    category: story.category,
    localUrl: story.url
  }));

  const updateArchive = () => {
    const unique = new Map();
    localArchiveItems.forEach((item) => {
      if (!unique.has(item.key)) unique.set(item.key, item);
    });
    archiveState.items = [...unique.values()].sort((left, right) => (
      right.date.localeCompare(left.date) || left.title.localeCompare(right.title, "en")
    ));
    archiveCount.textContent = String(archiveState.items.length);
    archiveControls.hidden = archiveState.items.length === 0;
    resetAndRenderArchive();
  };

  updateArchive();

})();
