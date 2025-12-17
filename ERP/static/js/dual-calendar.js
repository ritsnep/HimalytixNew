(function (window, document) {
  "use strict";

  const toIso = (value) => {
    if (!value) return "";
    if (typeof value === "string") return value;
    if (typeof value === "object" && value.year && value.month && value.day) {
      const pad = (n) => String(n).padStart(2, "0");
      return `${value.year}-${pad(value.month)}-${pad(value.day)}`;
    }
    return "";
  };

  const hasNepaliFns = () =>
    typeof window.NepaliFunctions !== "undefined" &&
    window.NepaliFunctions !== null;

  const convertBsToAd = (bsVal) => {
    if (!bsVal) return "";
    if (hasNepaliFns() && typeof window.NepaliFunctions.BS2AD === "function") {
      try {
        return toIso(window.NepaliFunctions.BS2AD(bsVal)) || "";
      } catch (err) {
        console.warn("[DualCalendar] BS2AD failed", err);
      }
    }
    // Fallback: assume BS input is already AD if conversion not available.
    return toIso(bsVal) || "";
  };

  const convertAdToBs = (adVal) => {
    if (!adVal) return "";
    if (hasNepaliFns() && typeof window.NepaliFunctions.AD2BS === "function") {
      try {
        return toIso(window.NepaliFunctions.AD2BS(adVal)) || "";
      } catch (err) {
        console.warn("[DualCalendar] AD2BS failed", err);
      }
    }
    // Fallback: show AD value as-is when conversion is unavailable.
    return toIso(adVal) || "";
  };

  const isHidden = (el) => el.classList.contains("d-none") || el.hidden;

  const DualCalendar = {
    initAll(root) {
      const scope = root && root.querySelectorAll ? root : document;
      scope.querySelectorAll("[data-dual-calendar]").forEach((node) => {
        DualCalendar.mount(node);
      });
    },

    mount(container) {
      if (!container || container.dataset.dualCalendarMounted === "1") return;

      const adInput = container.querySelector("[data-role='ad-input']");
      const bsInput = container.querySelector("[data-role='bs-input']");
      const toggle = container.querySelector("[data-role='toggle']");

      // Defensive: if the container markup is incomplete, skip attaching listeners.
      if (!adInput || !bsInput) {
        console.warn("[DualCalendar] Missing AD/BS input in", container);
        container.dataset.dualCalendarMounted = "1";
        return;
      }

      const mode =
        (container.dataset.calendarMode || window.CALENDAR_MODE || "AD").toUpperCase();
      const allowToggle = mode === "DUAL";
      let currentView = (
        container.dataset.initialView ||
        (mode === "DUAL" ? "BS" : mode)
      ).toUpperCase();
      if (!["AD", "BS"].includes(currentView)) currentView = "AD";

      const setView = (view) => {
        currentView = view === "BS" ? "BS" : "AD";
        const showBs = currentView === "BS";
        bsInput.hidden = !showBs;
        adInput.hidden = showBs;
        bsInput.classList.toggle("d-none", !showBs);
        adInput.classList.toggle("d-none", showBs);
        if (toggle) {
          toggle.textContent = showBs ? "AD" : "BS";
        }
        // Do not auto-focus on toggle or mount to avoid stealing focus from other fields.
      };

      const syncFromBs = () => {
        const bsVal = bsInput.value;
        if (!bsVal) {
          adInput.value = "";
      return;
    }
    const adVal = convertBsToAd(bsVal);
    if (adVal) {
      adInput.value = adVal;
      adInput.dispatchEvent(new Event("input", { bubbles: true }));
    }
  };

  const syncFromAd = () => {
    const adVal = adInput.value;
    if (!adVal) {
      bsInput.value = "";
      bsInput.dispatchEvent(new Event("input", { bubbles: true }));
      return;
    }
    const bsVal = convertAdToBs(adVal);
    if (bsVal) {
      bsInput.value = bsVal;
      bsInput.dispatchEvent(new Event("input", { bubbles: true }));
    }
  };

      const initNepaliPicker = () => {
        if (typeof bsInput.nepaliDatePicker === "function") {
          const opts = adInput.id
            ? { ndpEnglishInput: adInput.id }
            : {};
          try {
            bsInput.nepaliDatePicker(opts);
          } catch (err) {
            console.warn("[DualCalendar] nepaliDatePicker init failed", err);
          }
        } else if (!container.dataset.nepaliPickerWarned) {
          console.warn(
            "[DualCalendar] Nepali datepicker script not found. BS popup disabled."
          );
          container.dataset.nepaliPickerWarned = "1";
        }
      };

      bsInput.addEventListener("change", syncFromBs);
      bsInput.addEventListener("blur", syncFromBs);
      adInput.addEventListener("change", syncFromAd);
      adInput.addEventListener("blur", syncFromAd);

      if (toggle) {
        toggle.addEventListener("click", () => {
          if (!allowToggle) return;
          if (currentView === "BS") {
            syncFromBs();
            setView("AD");
          } else {
            syncFromAd();
            setView("BS");
          }
        });
      }

      if (!allowToggle && toggle) {
        toggle.classList.add("d-none");
        toggle.setAttribute("aria-hidden", "true");
      }

      // Initialize picker and sync both inputs before showing.
      initNepaliPicker();
      if (currentView === "BS") {
        if (!bsInput.value && adInput.value) {
          syncFromAd();
        }
      } else if (!adInput.value && bsInput.value) {
        syncFromBs();
      }
      setView(currentView);

      container.dataset.dualCalendarMounted = "1";
    },
  };

  window.DualCalendar = DualCalendar;

  document.addEventListener("DOMContentLoaded", function () {
    DualCalendar.initAll();
  });

  document.body.addEventListener("htmx:afterSwap", function (evt) {
    DualCalendar.initAll(evt.target);
  });
})(window, document);
