(() => {
  "use strict";

  const target = document.documentElement.dataset.presenceRedirect;
  if (typeof target === "string" && /^\/(?!\/)/.test(target)) {
    window.location.replace(target + window.location.search + window.location.hash);
  }
})();
