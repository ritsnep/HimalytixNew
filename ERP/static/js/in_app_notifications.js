/* Lightweight in-app notification dropdown controller.
 * Fetches current user's notifications, renders into header dropdown, and
 * supports marking items read individually or in bulk.
 */
(function () {
  const dropdownToggle = document.getElementById("page-header-notifications-dropdown");
  const menu = document.getElementById("header-notification-menu");
  const listContainer = document.getElementById("header-notification-list");
  const unreadLabel = document.getElementById("header-notification-unread");
  const badge = document.getElementById("header-notification-badge");
  const markAllBtn = document.getElementById("header-notification-mark-all");

  if (!dropdownToggle || !menu || !listContainer) {
    return;
  }

  const endpoints = {
    list: menu.dataset.endpointList,
    markRead: menu.dataset.endpointMarkRead,
    markAll: menu.dataset.endpointMarkAll,
  };

  const csrftoken = (function getCsrfToken() {
    const metaToken =
      document.querySelector('meta[name="csrf-token"]') ||
      document.querySelector('meta[name="csrfmiddlewaretoken"]');
    if (metaToken) {
      return metaToken.getAttribute("content") || "";
    }
    const cookies = document.cookie ? document.cookie.split(";") : [];
    for (const cookie of cookies) {
      const [rawName, ...rest] = cookie.split("=");
      if (!rawName || rest.length === 0) continue;
      if (rawName.trim().toLowerCase() === "csrftoken") {
        return decodeURIComponent(rest.join("="));
      }
    }
    return "";
  })();

  function setBadge(count) {
    if (!badge) return;
    if (count > 0) {
      badge.textContent = count;
      badge.classList.remove("d-none");
    } else {
      badge.textContent = "";
      badge.classList.add("d-none");
    }
  }

  function setUnreadLabel(count) {
    if (!unreadLabel) return;
    unreadLabel.textContent = `Unread (${count})`;
  }

  function renderItems(items) {
    listContainer.innerHTML = "";
    if (!items.length) {
      listContainer.innerHTML =
        '<div class="p-3 text-center text-muted small">No notifications yet.</div>';
      return;
    }

    for (const item of items) {
      const wrapper = document.createElement("a");
      wrapper.className =
        "text-reset notification-item d-block border-bottom py-2 px-3";
      wrapper.href = "javascript:void(0)";
      wrapper.dataset.id = item.id;

      const unreadDot = item.is_read
        ? ""
        : '<span class="badge bg-danger ms-2 align-self-start">New</span>';

      wrapper.innerHTML = `
        <div class="d-flex">
          <div class="flex-grow-1">
            <div class="d-flex align-items-center mb-1">
              <h6 class="mb-0">${escapeHtml(item.title || "Notification")}</h6>
              ${unreadDot}
            </div>
            <div class="font-size-13 text-muted">
              <p class="mb-1">${escapeHtml(item.body || "")}</p>
              <p class="mb-0"><i class="mdi mdi-clock-outline"></i> <span>${escapeHtml(
                item.created_display || ""
              )}</span></p>
            </div>
          </div>
        </div>`;

      wrapper.addEventListener("click", () => markRead(item.id, wrapper));
      listContainer.appendChild(wrapper);
    }
  }

  function escapeHtml(str) {
    return (str || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function ensureJson(res) {
    const ct = (res.headers.get("content-type") || "").toLowerCase();
    if (!ct.includes("application/json")) {
      throw new Error("Unexpected response format");
    }
    return res.json();
  }

  function fetchList() {
    fetch(endpoints.list, { credentials: "same-origin" })
      .then((res) => {
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }
        return ensureJson(res);
      })
      .then((data) => {
        renderItems(data.items || []);
        setBadge(data.unread_count || 0);
        setUnreadLabel(data.unread_count || 0);
      })
      .catch((err) => {
        console.error("Notification fetch failed", err);
        listContainer.innerHTML =
          '<div class="p-3 text-center text-danger small">Unable to load notifications. Refresh or re-open the menu.</div>';
      });
  }

  function markRead(id, node) {
    const url = endpoints.markRead.replace(/0\/?$/, `${id}/`);
    fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: csrftoken
        ? {
            "X-CSRFToken": csrftoken,
          }
        : {},
    })
      .then((res) => {
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }
        return ensureJson(res);
      })
      .then(() => {
        if (node) {
          node.querySelector(".badge")?.remove();
        }
        fetchList();
      })
      .catch((err) => {
        console.error("Failed to mark notification read", err);
        listContainer.insertAdjacentHTML(
          "afterbegin",
          '<div class="p-2 text-danger small">Could not mark notification read. Please retry.</div>'
        );
      });
  }

  function markAllRead() {
    fetch(endpoints.markAll, {
      method: "POST",
      credentials: "same-origin",
      headers: csrftoken
        ? {
            "X-CSRFToken": csrftoken,
          }
        : {},
    })
      .then((res) => {
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }
        return ensureJson(res);
      })
      .then(() => fetchList())
      .catch((err) => {
        console.error("Failed to mark all notifications read", err);
        listContainer.insertAdjacentHTML(
          "afterbegin",
          '<div class="p-2 text-danger small">Could not mark all as read. Please reopen and retry.</div>'
        );
      });
  }

  dropdownToggle.addEventListener("show.bs.dropdown", fetchList);
  if (markAllBtn) {
    markAllBtn.addEventListener("click", (e) => {
      e.preventDefault();
      markAllRead();
    });
  }

  // Initial fetch to keep badge accurate even before opening dropdown
  fetchList();
})();
