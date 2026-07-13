const DEFAULT_PAGE_SIZE = 10;
const LEFT_EDGE = 2;
const LEFT_CURRENT = 2;
const RIGHT_CURRENT = 5;
const RIGHT_EDGE = 2;

const NUM_BTN = "inline-flex h-8 min-w-8 items-center justify-center rounded-sm border border-gray-300 bg-white px-2 font-display text-xs font-semibold tabular-nums text-blue-900 hover:border-blue-900 hover:bg-blue-900 hover:text-white";
const NUM_BTN_CURRENT = "inline-flex h-8 min-w-8 items-center justify-center rounded-sm border border-blue-900 bg-blue-900 px-2 font-display text-xs font-semibold tabular-nums text-white";
const ELLIPSIS = "px-1 font-display text-xs text-gray-400";

const computeVisiblePages = (current, totalPages) => {
  const pages = [];
  let last = 0;
  for (let n = 1; n <= totalPages; n++) {
    const inLeftEdge = n <= LEFT_EDGE;
    const inWindow = current - LEFT_CURRENT - 1 < n && n < current + RIGHT_CURRENT;
    const inRightEdge = n > totalPages - RIGHT_EDGE;
    if (inLeftEdge || inWindow || inRightEdge) {
      if (last + 1 !== n) pages.push(null);
      pages.push(n);
      last = n;
    }
  }
  return pages;
};

const createPageItem = (page, current) => {
  const li = document.createElement("li");
  if (page === null) {
    li.textContent = "…";
    li.className = ELLIPSIS;
    li.setAttribute("aria-hidden", "true");
    return li;
  }
  const btn = document.createElement("button");
  btn.type = "button";
  btn.textContent = page;
  btn.dataset.page = page;
  btn.className = page === current ? NUM_BTN_CURRENT : NUM_BTN;
  if (page === current) btn.setAttribute("aria-current", "page");
  li.append(btn);
  return li;
};

const initApplicationsTable = () => {
  const table = document.querySelector("[data-paginated-table]");
  const nav = document.querySelector("[data-pagination]");
  if (!table || !nav) return;

  const rows = Array.from(table.tBodies[0]?.rows ?? []);
  const pageSize = Number(table.dataset.pageSize) || DEFAULT_PAGE_SIZE;
  const search = document.querySelector("[data-applications-search]");
  const empty = document.querySelector("[data-applications-empty]");
  const status = nav.querySelector("[data-pagination-status]");
  const prevBtn = nav.querySelector("[data-pagination-prev]");
  const nextBtn = nav.querySelector("[data-pagination-next]");
  const pageList = nav.querySelector("[data-pagination-pages]");

  let filtered = rows;
  let current = 1;

  const render = () => {
    const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
    if (current > totalPages) current = totalPages;

    const start = (current - 1) * pageSize;
    const end = start + pageSize;

    rows.forEach((row) => { row.hidden = true; });
    filtered.slice(start, end).forEach((row) => { row.hidden = false; });

    empty.hidden = filtered.length > 0;
    table.hidden = filtered.length === 0;
    nav.hidden = filtered.length <= pageSize;
    if (nav.hidden) return;

    status.textContent = `Showing ${start + 1}–${Math.min(end, filtered.length)} of ${filtered.length}`;
    prevBtn.disabled = current === 1;
    nextBtn.disabled = current === totalPages;

    pageList.replaceChildren(
      ...computeVisiblePages(current, totalPages).map((p) => createPageItem(p, current)),
    );
  };

  const goTo = (page) => {
    current = Math.max(1, page);
    render();
  };

  prevBtn.addEventListener("click", () => goTo(current - 1));
  nextBtn.addEventListener("click", () => goTo(current + 1));
  pageList.addEventListener("click", (event) => {
    const btn = event.target.closest("button[data-page]");
    if (btn) goTo(Number(btn.dataset.page));
  });
  search?.addEventListener("input", () => {
    const query = search.value.trim().toLowerCase();
    filtered = query
      ? rows.filter((row) => row.textContent.toLowerCase().includes(query))
      : rows;
    current = 1;
    render();
  });

  render();
};

const initCloseApplicationForms = () => {
  document.querySelectorAll("[data-close-application-form]").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = form.querySelector("button[type='submit']");
      if (button) button.disabled = true;

      try {
        const response = await fetch(form.action, {
          method: "POST",
          body: new FormData(form),
          credentials: "same-origin",
        });
        if (!response.ok) throw new Error(`close failed: ${response.status}`);
        window.location.reload();
      } catch (_error) {
        if (button) button.disabled = false;
      }
    });
  });
};

initApplicationsTable();
initCloseApplicationForms();
