// coding=utf-8
// DataCatalog
// Copyright (C) 2020  University of Luxembourg
//
// This program is free software: you can redistribute it and/or modify
//  it under the terms of the GNU Affero General Public License as
// published by the Free Software Foundation, either version 3 of the
// License, or (at your option) any later version.
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU Affero General Public License for more details.
// You should have received a copy of the GNU Affero General Public License
// along with this program.  If not, see <https://www.gnu.org/licenses/>.

import React, {useMemo} from "react";
import PropTypes from "prop-types";
import ReactDOM from "react-dom";
import {CircleCheck, CircleX, Hourglass, TriangleAlert, X} from "lucide-react";
import ReactTable from "./ReactTable.jsx";

let domContainer = document.querySelector("#applications-datatable");

function parseData(data){
    data = JSON.parse(data);
    data.map(entry => {
        entry.creationDate = new Date(entry["creation_date_string"]);
    });
    return data;
}

function DisplayTable() {
    const IconCell = ({value}) => {
        const Component = {
            "submitted": Hourglass,
            "approved": CircleCheck,
            "rejected": CircleX,
            "closed": CircleX,
            "revoked": CircleX,
            "returned": TriangleAlert,
        }[value];
        const color = {
            "submitted": "text-blue-900",
            "approved": "text-blue-900",
            "rejected": "text-red-900",
            "closed": "text-red-900",
            "revoked": "text-red-900",
            "returned": "text-red-900",
        }[value] || "text-gray-600";

        if (!Component) return value;
        return (
            <span title={value} className="inline-flex items-center">
                <Component className={`h-5 w-5 ${color}`} aria-hidden="true" />
            </span>
        );
    };
    IconCell.propTypes = {
        value: PropTypes.string.IsRequired,
    };

    const LinkCell = ( cell ) => {
        return (
            <a href={cell.row.original["entity_url"]} className="font-medium text-blue-900 hover:underline">
                {cell.value}
            </a>
        );
    };

    let columns = useMemo(
        () => [
            {
                Header: "Id",
                accessor: "ext_id",
                width: "20%",
            },
            {
                Header: "Dataset",
                accessor: "dataset",
                width: "60%",
                Cell: LinkCell,
            },
            {
                Header: "State",
                accessor: "state",
                Cell: IconCell,
                disableGlobalFilter: true,
                disableSortBy: true,
                width: "5%",
            },
            {
                Header: "Created on",
                accessor: "creationDate",
                disableGlobalFilter: true,
                sortType: "datetime",
                Cell: ({value}) => value.toLocaleDateString(),
                width: "15%",
            },
        ]
    );

    const data = parseData(domContainer.getAttribute("data-applications"));

    const userActions = domContainer.getAttribute("data-actions-allowed");
    const closeUrlTemplate = domContainer.getAttribute("data-close-url-template");

    if (userActions && closeUrlTemplate) {
        const csrfToken = document.getElementById("csrf-token").getAttribute("content");
        const onCancelClick = (applicationId) => (e) => {
            e.preventDefault();
            const url = closeUrlTemplate.replace("__APP_ID__", encodeURIComponent(applicationId));
            fetch(url, {
                method: "POST",
                headers: {"X-CSRFToken": csrfToken},
                credentials: "same-origin",
            }).finally(() => location.reload());
        };
        columns.push({
            Header: "Actions",
            accessor: "actions",
            disableGlobalFilter: true,
            disableSortBy: true,
            Cell: (cell) => {
                const applicationId = cell.row.original.id;
                return (
                    <a
                        className="inline-flex items-center text-red-900 hover:text-red-700"
                        href="#"
                        title="cancel my application"
                        onClick={onCancelClick(applicationId)}
                    >
                        <X className="h-5 w-5" aria-hidden="true" />
                    </a>
                );
            },
        });
    }

    return (
        <ReactTable
            columns={columns}
            data={data}
            defaultSortColumnId={"creationDate"}
            search={true}
            pagination={true}
            sort={true}
        />
    );
}

if (domContainer !== null) {
    ReactDOM.render(<DisplayTable/>, domContainer);
}
