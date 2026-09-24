(() => {
  const form = document.getElementById("contact-form");
  const status = document.querySelector("[data-contact-status]");
  const fallback = document.querySelector("[data-contact-fallback]");
  const preview = document.querySelector("[data-contact-preview]");
  const copyButton = document.querySelector("[data-contact-copy]");
  const telegramUrl = "https://t.me/presencemedia";
  if (!(form instanceof HTMLFormElement) || !status || !fallback || !(preview instanceof HTMLTextAreaElement) || !copyButton) return;

  const submitButton = form.querySelector('[type="submit"]');
  const fields = ["name", "email", "reason", "subject", "message"].map((name) => form.elements.namedItem(name));
  let submissionVersion = 0;

  const clearFeedback = () => {
    submissionVersion += 1;
    fields.forEach((field) => field.setCustomValidity(""));
    status.textContent = "";
    fallback.hidden = true;
    preview.value = "";
    if (submitButton) submitButton.disabled = false;
  };

  form.addEventListener("input", clearFeedback);
  form.addEventListener("change", clearFeedback);
  form.addEventListener("reset", clearFeedback);

  const copyText = async (value) => {
    if (navigator.clipboard && window.isSecureContext) {
      try {
        await navigator.clipboard.writeText(value);
        return true;
      } catch (_) {
        return false;
      }
    }

    const previousFocus = document.activeElement;
    const helper = document.createElement("textarea");
    helper.value = value;
    helper.setAttribute("readonly", "");
    helper.className = "visually-hidden";
    document.body.append(helper);
    try {
      helper.select();
      return document.execCommand("copy");
    } catch (_) {
      return false;
    } finally {
      helper.remove();
      if (previousFocus instanceof HTMLElement) previousFocus.focus({ preventScroll: true });
    }
  };

  copyButton.addEventListener("click", async () => {
    const version = submissionVersion;
    const copied = await copyText(preview.value);
    if (version !== submissionVersion) return;
    if (copied) {
      status.textContent = "Message copied. Open Telegram below, paste it into the chat and press Send.";
    } else {
      preview.focus();
      preview.select();
      status.textContent = "Copy the selected text, then open Telegram below and paste it into the chat.";
    }
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearFeedback();

    fields.forEach((field) => {
      if (field instanceof HTMLInputElement || field instanceof HTMLTextAreaElement) field.value = field.value.trim();
    });
    const [nameField, emailField, reasonField, , messageField] = fields;
    if (!nameField.value) nameField.setCustomValidity("Enter your name.");
    if (emailField.validity.typeMismatch) emailField.setCustomValidity("Enter a valid reply email or leave it blank.");
    if (!reasonField.value) reasonField.setCustomValidity("Choose a reason for contacting us.");
    if (messageField.value.length < 10) messageField.setCustomValidity("Write a message of at least 10 characters, excluding spaces at the beginning and end.");

    if (!form.checkValidity()) {
      const invalidField = fields.find((field) => !field.validity.valid);
      status.textContent = invalidField?.validationMessage || "Check the highlighted field.";
      form.reportValidity();
      return;
    }

    const data = new FormData(form);
    const name = String(data.get("name") || "").trim();
    const email = String(data.get("email") || "").trim();
    const reason = String(data.get("reason") || "General question").trim();
    const subject = String(data.get("subject") || "").trim() || "Website enquiry";
    const message = String(data.get("message") || "").trim();
    const telegramMessage = [
      "PRESENCE website message",
      "",
      `Name: ${name}`,
      ...(email ? [`Reply email: ${email}`] : []),
      `Reason: ${reason}`,
      `Subject: ${subject}`,
      "",
      message
    ].join("\n");

    const version = submissionVersion;
    if (submitButton) submitButton.disabled = true;
    const copyPromise = copyText(telegramMessage);
    let telegramWindow = null;
    try {
      telegramWindow = window.open(telegramUrl, "_blank");
      if (telegramWindow) telegramWindow.opener = null;
    } catch (_) {
      telegramWindow = null;
    }

    const copied = await copyPromise;
    if (version !== submissionVersion) return;
    if (submitButton) submitButton.disabled = false;
    if (copied && telegramWindow) {
      status.textContent = "Message copied. Paste it into the Telegram chat and press Send.";
      return;
    }

    preview.value = telegramMessage;
    fallback.hidden = false;
    status.textContent = copied
      ? "Message copied, but Telegram could not open automatically. Open it using the link below and paste your message."
      : "Your message has not been sent. Copy the prepared text below, then open Telegram and paste it into the chat.";
  });
})();
