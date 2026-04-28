import React from "react";
import PropTypes from "prop-types";

const baseItem =
    "inline-flex h-9 min-w-[2.25rem] items-center justify-center border border-gray-200 px-3 text-sm text-blue-900 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-900 focus:ring-offset-1";
const activeItem =
    "inline-flex h-9 min-w-[2.25rem] items-center justify-center border border-blue-900 bg-blue-900 px-3 text-sm font-semibold text-white";
const disabledItem =
    "inline-flex h-9 min-w-[2.25rem] cursor-not-allowed items-center justify-center border border-gray-200 px-3 text-sm text-gray-400";

export default function Pagination({
    currentPage,
    pageNumber,
    previousPage,
    nextPage,
    gotoPage,
}) {
    const isFirstPage = currentPage === 0;
    const isLastPage = currentPage === pageNumber - 1;

    return (
        <ul className="inline-flex -space-x-px">
            <li>
                {isFirstPage ? (
                    <span className={disabledItem} aria-disabled="true">«</span>
                ) : (
                    <a
                        href="#"
                        className={baseItem}
                        onClick={(e) => {
                            e.preventDefault();
                            previousPage();
                        }}
                    >
                        «
                    </a>
                )}
            </li>
            <li style={currentPage < 2 ? {display: "none"} : {}}>
                <a
                    href="#"
                    className={baseItem}
                    onClick={(e) => {
                        e.preventDefault();
                        gotoPage(currentPage - 2);
                    }}
                >
                    {currentPage - 1}
                </a>
            </li>
            <li style={currentPage < 1 ? {display: "none"} : {}}>
                <a
                    href="#"
                    className={baseItem}
                    onClick={(e) => {
                        e.preventDefault();
                        gotoPage(currentPage - 1);
                    }}
                >
                    {currentPage}
                </a>
            </li>
            <li>
                <span className={activeItem} aria-current="page">{currentPage + 1}</span>
            </li>
            <li style={currentPage >= pageNumber - 1 ? {display: "none"} : {}}>
                <a
                    href="#"
                    className={baseItem}
                    onClick={(e) => {
                        e.preventDefault();
                        gotoPage(currentPage + 1);
                    }}
                >
                    {currentPage + 2}
                </a>
            </li>
            <li style={currentPage >= pageNumber - 2 ? {display: "none"} : {}}>
                <a
                    href="#"
                    className={baseItem}
                    onClick={(e) => {
                        e.preventDefault();
                        gotoPage(currentPage + 2);
                    }}
                >
                    {currentPage + 3}
                </a>
            </li>
            <li>
                {isLastPage ? (
                    <span className={disabledItem} aria-disabled="true">»</span>
                ) : (
                    <a
                        href="#"
                        className={baseItem}
                        onClick={(e) => {
                            e.preventDefault();
                            nextPage();
                        }}
                    >
                        »
                    </a>
                )}
            </li>
        </ul>
    );
}

Pagination.propTypes = {
    currentPage: PropTypes.number.isRequired,
    pageNumber: PropTypes.number.isRequired,
    previousPage: PropTypes.func.isRequired,
    nextPage: PropTypes.func.isRequired,
    gotoPage: PropTypes.func.isRequired
};
