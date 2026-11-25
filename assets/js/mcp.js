if (navigator.clipboard?.writeText) {
  document.querySelectorAll("[data-mcp-copy]").forEach((controls) => {
    const code = document.getElementById(controls.dataset.mcpCopy);
    const button = controls.querySelector("button");
    const status = controls.querySelector('[role="status"]');
    button.addEventListener("click", async () => {
      status.textContent = "";
      try {
        await navigator.clipboard.writeText(code.textContent.trim());
        status.textContent = "Copied.";
      } catch {
        status.textContent = "Select and copy the text above.";
      }
    });
    controls.hidden = false;
  });
}
