document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-add-exclusion]").forEach((button) => {
    button.addEventListener("click", () => {
      const field = document.createElement("input");
      field.name = "exclude";
      field.type = "text";
      field.placeholder = "another-relative-path";
      document.querySelector("[data-exclusions]").appendChild(field);
      field.focus();
    });
  });

  document.querySelectorAll("[data-submission-form]").forEach((form) => {
    form.addEventListener("submit", () => {
      const button = form.querySelector("button[type='submit']");
      button.disabled = true;
      form.querySelector("[data-working]").hidden = false;
    });
  });
});
