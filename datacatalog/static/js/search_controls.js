(() => {
    const query = document.querySelector("#query");
    const sortBy = document.querySelector("#sort_by");
    const order = document.querySelector("#order");

    if (!query || !sortBy || !order) return;

    const triggerChange = (element) => {
        element.dispatchEvent(new Event("change", {bubbles: true}));
    };

    const resetRelevanceOrder = () => {
        if (!sortBy.value && order.value === "asc") {
            order.value = "desc";
            triggerChange(order);
        }
    };

    let queryWasEmpty = !query.value;

    query.addEventListener("input", () => {
        if (queryWasEmpty && query.value) {
            sortBy.value = "";
            triggerChange(sortBy);
        }
        queryWasEmpty = !query.value;
    });

    sortBy.addEventListener("change", resetRelevanceOrder);
})();
