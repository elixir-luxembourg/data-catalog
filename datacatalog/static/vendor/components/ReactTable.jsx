import React, {useState} from "react";
import {useGlobalFilter, usePagination, useSortBy, useTable, useExpanded} from "react-table";
import {ChevronDown, ChevronRight, ChevronUp} from "lucide-react";
import Pagination from "./Pagination.jsx";
import PropTypes from "prop-types";

const SortIcon = ({ direction }) => {
    if (direction === "desc") {
        return <ChevronDown className="ml-1 inline-block h-3 w-3 text-blue-900" aria-hidden="true" />;
    }
    if (direction === "asc") {
        return <ChevronUp className="ml-1 inline-block h-3 w-3 text-blue-900" aria-hidden="true" />;
    }
    if (direction === "none") {
        return <ChevronRight className="ml-1 inline-block h-3 w-3 text-gray-400" aria-hidden="true" />;
    }
    return null;
};

SortIcon.propTypes = {
    direction: PropTypes.oneOf(["asc", "desc", "none", null]),
};

export default function ReactTable({
    columns,
    data,
    defaultSortColumnId,
    defaultSortOrder,
    defaultSearchPlaceHolder,
    search,
    pagination,
    sort,
}) {
    /* React component to display a sortable, filterable, paginated table.
    * Attributes:
    *   columns: Array
    *       List of columns objects. See 'https://react-table.tanstack.com/docs/api/useTable'
    *       for more info about column properties
    *   data: Array
    *       List of objects to display in the table. Each object should be of the format
    *       { column1Header: value1, column2Header: value2, ... }
    *   defaultSortColumnId: String (Optional)
    *       The header of the column with which data will be sorted by default
    *       Default: ""
    *   defaultSortOrder: String (Optional)
    *       The order in which data will be sorted by default. Anything other than
    *        "desc" will be treated as "asc"
    *        Default: "desc"
    *
    *  Returns:
    *    A React component containing the table, search bar and page buttons
    */

    defaultSortColumnId = defaultSortColumnId || "";
    defaultSortOrder = defaultSortOrder || "desc";
    defaultSearchPlaceHolder = defaultSearchPlaceHolder || "";
    search = search || false;
    pagination = pagination || false;
    sort = sort || false;

    function ReactRow({row}){
        return (
            <tr>
                <td colSpan={visibleColumns.length} className="bg-gray-50 px-3 py-3">
                    <dl className="grid grid-cols-1 gap-x-4 gap-y-2 text-sm sm:grid-cols-[10rem,1fr]">
                        <dt className="font-semibold text-blue-900">Name</dt>
                        <dd className="text-gray-800">{row.original["full_name"] || "-"}</dd>
                        <dt className="font-semibold text-blue-900">Address</dt>
                        <dd className="text-gray-800">{row.original["business_address"] || "-"}</dd>
                        <dt className="font-semibold text-blue-900">Phone Number</dt>
                        <dd className="text-gray-800">-</dd>
                    </dl>
                </td>
            </tr>
        );
    }
    ReactRow.propTypes = {
        row: PropTypes.shape({
            original: PropTypes.shape({
                "full_name": PropTypes.string.isRequired,
                "business_address": PropTypes.string.isRequired,
            }),
        }),
    };


    const PAGE_SIZE_OPTIONS = [5, 10, 25, 50, 100];
    // Check if column width is defined. If not, the displayed table will keep
    // react-table default behavior in regards to column width.
    // Note that if any column.width is defined, all undefined values
    // will default to 150.
    const columnWidthIsDefault = columns.map(c => !c.width).every(Boolean);

    const [filterInput, setFilterInput] = useState("");

    const {
        //      Basic options
        getTableProps,
        getTableBodyProps,
        headerGroups,
        prepareRow,
        rows,
        visibleColumns,
        //      Filtering options
        setGlobalFilter,
        //      Pagination options
        page,
        state: {pageIndex, pageSize, expanded},
        gotoPage,
        previousPage,
        nextPage,
        setPageSize,
        pageCount,
    } = useTable(
        {
            columns,
            data,
            initialState: {
                sortBy: [
                    {
                        id: defaultSortColumnId,
                        desc: defaultSortOrder === "desc",
                    }
                ],
            },
        },
        useGlobalFilter,
        sort && useSortBy,
        useExpanded,
        pagination && usePagination,
    );

    const handleFilterChange = e => {
        const value = e.target.value;
        setGlobalFilter(value);
        setFilterInput(value);
    };

    const displayedRowsString = pagination ? `Showing  ${page.length} of ${data.length} entries: ` : "";
    const selectClass =
        "ml-1 rounded border border-gray-200 bg-white px-2 py-1 text-sm text-blue-900 focus:border-blue-900 focus:outline-none focus:ring-1 focus:ring-blue-900";
    const filterInputClass =
        "ml-1 rounded border border-gray-200 bg-white px-2 py-1 text-sm text-blue-900 placeholder-gray-400 focus:border-blue-900 focus:outline-none focus:ring-1 focus:ring-blue-900";
    return (
        <>
            {pagination &&
                    <div className="mb-2 flex items-center justify-between gap-3 text-sm text-gray-800">
                        <div>
                            <span>
                                {"Show "}
                                <select
                                    value={pageSize}
                                    onChange={e => {
                                        setPageSize(Number(e.target.value));
                                    }}
                                    className={selectClass}
                                >
                                    {PAGE_SIZE_OPTIONS.map(pageSize => (
                                        <option key={pageSize} value={pageSize}>
                                            {pageSize}
                                        </option>
                                    ))}
                                </select>
                                {" entries."}
                            </span>
                        </div>
                        {search &&
                                <div>
                                    {"Filter: "}
                                    <input value={filterInput} onChange={handleFilterChange} type="text"
                                        placeholder={defaultSearchPlaceHolder}
                                        className={filterInputClass}/>
                                </div>
                        }
                    </div>
            }
            <div className="overflow-x-auto rounded border border-gray-200">
                <table className="min-w-full divide-y divide-gray-200 text-sm" {...getTableProps({style: {width: "100%"}})}>
                    <thead className="bg-gray-50">
                        {headerGroups.map((headerGroup, index) => (
                            <tr key={index} {...headerGroup.getHeaderGroupProps()}>
                                {headerGroup.headers.map((column, index) => {
                                    let direction = null;
                                    if (sort && column.canSort) {
                                        if (column.isSorted) {
                                            direction = column.isSortedDesc ? "desc" : "asc";
                                        } else {
                                            direction = "none";
                                        }
                                    }
                                    return (
                                        <th key={index} width={columnWidthIsDefault ? "" : column.width}
                                            className="px-3 py-2 text-left font-semibold text-blue-900"
                                            {...column.getHeaderProps(sort && column.getSortByToggleProps())}
                                        >
                                            {column.render("Header")}
                                            <SortIcon direction={direction} />
                                        </th>
                                    );
                                })}
                            </tr>
                        ))}
                    </thead>
                    <tbody className="divide-y divide-gray-200 bg-white" {...getTableBodyProps()}>
                        { pagination ?
                            page.map((row, i) => {
                                prepareRow(row);
                                return (
                                    <tr key={i} className="hover:bg-gray-50" {...row.getRowProps()}>
                                        {row.cells.map((cell, index) => {
                                            return <td key={index} className="px-3 py-2 align-top text-gray-800" {...cell.getCellProps()}>{cell.render("Cell")}</td>;
                                        })}
                                    </tr>
                                );
                            }) :
                            rows.map((row, i) => {
                                prepareRow(row);
                                return (
                                    <React.Fragment key={i}>
                                        <tr key={i} className="hover:bg-gray-50" {...row.getRowProps()}>
                                            {row.cells.map((cell, index) => {
                                                return <td key={index} className="px-3 py-2 align-top text-gray-800" {...cell.getCellProps()}>{cell.render("Cell")}</td>;
                                            })}
                                        </tr>
                                        {expanded && row.isExpanded ? (
                                            <ReactRow row={row} />
                                        ) : null}
                                    </React.Fragment>
                                );
                            })
                        }
                    </tbody>
                </table>
            </div>
            {pagination &&
                <div className="mt-2 flex items-center justify-between gap-3 text-sm text-gray-800">
                    <span>{displayedRowsString}</span>
                    <Pagination
                        currentPage={pageIndex}
                        pageNumber={pageCount}
                        previousPage={previousPage}
                        nextPage={nextPage}
                        gotoPage={gotoPage}
                    />
                </div>
            }
        </>
    );
}

ReactTable.propTypes = {
    columns: PropTypes.array.isRequired,
    data: PropTypes.array.isRequired,
    defaultSortColumnId: PropTypes.string,
    defaultSortOrder: PropTypes.string,
    defaultSearchPlaceHolder: PropTypes.string,
    search: PropTypes.bool,
    pagination: PropTypes.bool,
    sort: PropTypes.bool,
};
