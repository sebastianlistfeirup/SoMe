document.addEventListener("DOMContentLoaded", () => {
  const menuButton = document.querySelector("[data-menu-toggle]");
  const sidebar = document.querySelector(".sidebar");
  if (menuButton && sidebar) {
    menuButton.addEventListener("click", () => {
      const open = sidebar.classList.toggle("is-open");
      menuButton.setAttribute("aria-expanded", String(open));
    });
  }

  const platform = document.querySelector("[data-platform-select]");
  const account = document.querySelector("[data-account-input]");
  const accountName = document.querySelector("[data-account-name]");
  const platformName = document.querySelector("[data-platform-name]");
  const updateAccount = () => {
    if (!platform) return;
    const option = platform.options[platform.selectedIndex];
    const value = option.dataset.account || "";
    if (account) account.value = value;
    if (accountName) accountName.textContent = option.dataset.accountLabel || "Konto vælges ved godkendelse";
    if (platformName) platformName.textContent = option.textContent;
  };
  if (platform) {
    platform.addEventListener("change", updateAccount);
    updateAccount();
  }

  document.querySelectorAll("[data-character-count]").forEach((field) => {
    const output = document.getElementById(field.dataset.characterCount);
    const update = () => { if (output) output.textContent = `${field.value.length} / ${field.maxLength}`; };
    field.addEventListener("input", update);
    update();
  });

  // TikTok Direct Post: privacy is required (no default) only when TikTok is a chosen destination;
  // commercial disclosure needs at least one type, and branded content cannot be private.
  const tiktokPanel = document.querySelector("[data-tiktok-panel]");
  if (tiktokPanel) {
    const destination = document.querySelector("[data-tiktok-destination]");
    const privacy = tiktokPanel.querySelector("[data-tiktok-privacy]");
    const disclose = tiktokPanel.querySelector("[data-tiktok-disclose]");
    const options = tiktokPanel.querySelector("[data-tiktok-commercial-options]");
    const organic = tiktokPanel.querySelector("[data-tiktok-brand-organic]");
    const branded = tiktokPanel.querySelector("[data-tiktok-brand-content]");
    const consent = tiktokPanel.querySelector("[data-tiktok-consent]");
    const consentText = tiktokPanel.querySelector("[data-tiktok-consent-text]");
    const brandedLink = tiktokPanel.querySelector("[data-tiktok-branded-link]");
    const labelPreview = tiktokPanel.querySelector("[data-tiktok-label-preview]");
    const required = tiktokPanel.querySelector("[data-tiktok-commercial-required]");
    const privateWarning = tiktokPanel.querySelector("[data-tiktok-private-warning]");
    const submit = document.querySelector(".approve-button");
    const update = () => {
      const active = Boolean(destination && destination.checked && !destination.disabled);
      tiktokPanel.classList.toggle("is-inactive", !active);
      if (privacy) privacy.required = active;
      const on = Boolean(disclose && disclose.checked);
      if (options) options.hidden = !on;
      if (!on) { if (organic) organic.checked = false; if (branded) branded.checked = false; }
      const isBranded = Boolean(branded && branded.checked);
      const isOrganic = Boolean(organic && organic.checked);
      if (privacy) {
        const onlyMe = privacy.querySelector('option[value="SELF_ONLY"]');
        if (onlyMe) onlyMe.disabled = isBranded;
        if (isBranded && privacy.value === "SELF_ONLY") privacy.value = "";
      }
      if (privateWarning) privateWarning.hidden = !isBranded;
      if (labelPreview) {
        labelPreview.hidden = !(isBranded || isOrganic);
        labelPreview.textContent = isBranded ? "Your photo/video will be labeled as 'Paid partnership'." : "Your photo/video will be labeled as 'Promotional content'.";
      }
      const missingType = on && !isBranded && !isOrganic;
      if (required) required.hidden = !missingType;
      if (consent && consentText) consentText.textContent = isBranded ? consent.dataset.branded : consent.dataset.music;
      if (brandedLink) brandedLink.hidden = !isBranded;
      if (submit) submit.disabled = active && missingType;
    };
    [destination, privacy, disclose, organic, branded].forEach((element) => { if (element) element.addEventListener("change", update); });
    update();
  }

  if (document.querySelector("[data-revision-pending]")) {
    window.setTimeout(() => window.location.reload(), 5000);
  }
});
