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

  if (document.querySelector("[data-revision-pending]")) {
    window.setTimeout(() => window.location.reload(), 5000);
  }
});
