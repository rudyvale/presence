(() => {
  const stories = Array.isArray(window.PRESENCE_NEWS) ? window.PRESENCE_NEWS : null;
  const grid = document.getElementById("news-grid");
  const empty = document.getElementById("news-empty");
  const filters = Array.from(document.querySelectorAll("[data-news-filter]"));
  const search = document.querySelector("[data-news-search]");
  const results = document.querySelector("[data-news-results]");
  const categories = new Set(["all", "crypto", "technology", "companies"]);

  if (!stories || !stories.length || !grid || !empty || !filters.length || !(search instanceof HTMLInputElement)) return;

  const categoryLabel = (category) => ({
    crypto: "Crypto",
    technology: "Technology",
    companies: "Companies"
  })[category] || category;

  const appendText = (parent, tag, className, value) => {
    const element = document.createElement(tag);
    if (className) element.className = className;
    element.textContent = value;
    parent.append(element);
    return element;
  };

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

  const makePublicationTime = (value) => {
    const date = safePublicationDate(value);
    if (!date) return null;

    const [yearValue, monthValue, dayValue] = date.split("-");
    const time = document.createElement("time");
    time.className = "news-card__date";
    time.dateTime = date;
    time.textContent = `${publicationMonths[Number(monthValue) - 1]} ${Number(dayValue)}, ${yearValue}`;
    return time;
  };

  const safeReadingTime = (value) => {
    if (typeof value !== "string" || value.length > 32 || value !== value.trim()) return null;
    const match = /^([1-9]\d*) min read$/.exec(value);
    return match && Number.isSafeInteger(Number(match[1])) ? value : null;
  };

  const listingDate = (story) => safePublicationDate(story.republishedDate) || story.date;

  const makeCard = (story) => {
    const article = document.createElement("article");
    article.className = `news-card news-card--${story.category}`;

    if (story.image) {
      article.classList.add("news-card--with-image");
      const media = document.createElement("a");
      media.className = "news-card__media";
      media.href = story.url;
      media.setAttribute("aria-label", `Read ${story.title}`);

      const image = document.createElement("img");
      image.src = story.image;
      image.alt = story.imageAlt || "";
      image.width = 1280;
      image.height = 720;
      image.loading = "lazy";
      image.decoding = "async";
      media.append(image);
      article.append(media);
    }

    const meta = document.createElement("div");
    meta.className = "news-card__meta";
    appendText(meta, "span", "news-card__category", categoryLabel(story.category));
    appendText(meta, "span", "news-card__type", story.type);
    const publicationTime = makePublicationTime(listingDate(story));
    if (publicationTime && safePublicationDate(story.republishedDate)) publicationTime.prepend("Republished ");
    if (publicationTime) meta.append(publicationTime);
    article.append(meta);

    const heading = document.createElement("h2");
    const link = document.createElement("a");
    link.href = story.url;
    link.textContent = story.title;
    heading.append(link);
    article.append(heading);

    appendText(article, "p", "news-card__summary", story.summary);

    const foot = document.createElement("div");
    foot.className = "news-card__foot";
    if (story.author) appendText(foot, "span", "", story.author);
    const readingTime = safeReadingTime(story.readingTime);
    if (readingTime) appendText(foot, "span", "", readingTime);
    article.append(foot);

    return article;
  };

  const orderedStories = [...stories].sort((left, right) => (
    listingDate(right).localeCompare(listingDate(left)) ||
    left.url.localeCompare(right.url)
  ));

  const updateCounts = () => {
    document.querySelectorAll("[data-news-count]").forEach((node) => {
      const category = node.dataset.newsCount;
      node.textContent = String(category === "all"
        ? stories.length
        : stories.filter((story) => story.category === category).length);
    });
  };

  const normalizeSearch = (value) => value.trim().toLocaleLowerCase();

  const render = (requestedCategory) => {
    const category = categories.has(requestedCategory) ? requestedCategory : "all";
    const categoryStories = category === "all"
      ? orderedStories
      : orderedStories.filter((story) => story.category === category);
    const query = normalizeSearch(search.value);
    const visibleStories = query
      ? categoryStories.filter((story) => [story.title, story.author, story.summary]
        .some((value) => normalizeSearch(String(value || "")).includes(query)))
      : categoryStories;

    grid.replaceChildren(...visibleStories.map(makeCard));
    empty.hidden = visibleStories.length > 0;
    empty.textContent = query
      ? "No stories match this search."
      : "No stories in this section yet.";
    if (results) {
      results.textContent = `${visibleStories.length} ${visibleStories.length === 1 ? "story" : "stories"}`;
    }

    filters.forEach((button) => {
      const active = button.dataset.newsFilter === category;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-pressed", String(active));
    });
  };

  const categoryFromHash = () => window.location.hash.slice(1).toLowerCase() || "all";

  filters.forEach((button) => {
    button.addEventListener("click", () => {
      const category = button.dataset.newsFilter;
      window.history.replaceState(null, "", category === "all" ? "#all" : `#${category}`);
      render(category);
    });
  });

  window.addEventListener("hashchange", () => render(categoryFromHash()));
  search.addEventListener("input", () => render(categoryFromHash()));
  updateCounts();
  render(categoryFromHash());
})();
