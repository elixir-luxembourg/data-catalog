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

    // options such as "Most viewed" carry the only order that makes sense
    const applyOptionOrder = () => {
        const optionOrder = sortBy.selectedOptions[0]?.dataset.order;
        if (optionOrder && order.value !== optionOrder) {
            order.value = optionOrder;
            triggerChange(order);
        }
    };

    sortBy.addEventListener("change", resetRelevanceOrder);
    sortBy.addEventListener("change", applyOptionOrder);
})();
