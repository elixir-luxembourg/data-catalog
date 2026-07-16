/* eslint-disable react/prop-types */
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
import ReactDOM from "react-dom";
import {ChevronRight} from "lucide-react";
import ReactTable from "./ReactTable.jsx";

let domContainer = document.querySelector("#contacts-datatable");

function parseData(data){
    data = JSON.parse(data);
    data = replaceEmptyProperties(data);
    return data;
}

function replaceEmptyProperties(obj) {
    let result = obj;
    Object.keys(obj).forEach(function(key) {
        let _o = obj[key];
        if (_o !== null && _o !== undefined && _o.length !==0 && typeof(_o) === "object") {
            replaceEmptyProperties(_o);
        }
        else{
            if (_o === null || _o === undefined || _o === "" || _o.length ===0 ){
                result[key] = "-";
            }
        }
    });
    return result;
}

function DisplayTable() {

    const IconCell = ({row}) => {
        const rotation = row.isExpanded ? "rotate-90" : "";
        return(
            <button
                type="button"
                className="inline-flex items-center justify-center text-blue-900 hover:text-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-900 focus:ring-offset-1"
                aria-label={row.isExpanded ? "Collapse row" : "Expand row"}
                {...row.getToggleRowExpandedProps()}
            >
                <ChevronRight className={`h-4 w-4 transition-transform ${rotation}`} aria-hidden="true" />
            </button>
        );
    };

    const LinkEmail = ( cell ) => {
        let mail = true;
        let mailto = "mailto:"+cell.row.original["email"];
        if (cell.row.original["email"] === null) {
            mail = false;
        }
        return (
            <>
                {
                    mail ?
                        <a href={mailto} className="font-medium text-blue-900 hover:underline">
                            {cell.row.original["email"]}
                        </a> : "-"
                }
            </>
        );
    };

    let columns = useMemo(
        () => [
            {
                id: "expander",
                Header: "",
                Cell: IconCell,
            },
            {
                Header: "Name",
                accessor: "full_name",
                width: "25%",
            },
            {
                Header: "Affiliation",
                accessor: "affiliation",
                width: "25%",
            },
            {
                Header: "Email",
                accessor: "email",
                Cell: LinkEmail,
                width: "25%",
            },
            {
                Header: "Role",
                accessor: "roles",
                width: "22%",
            },
        ]
    );

    const data = parseData(domContainer.getAttribute("data-contacts"));
    return (
        <ReactTable
            columns={columns}
            data={data}
        />
    );
}

if (domContainer !== null) {
    ReactDOM.render(<DisplayTable/>, domContainer);
}
