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

import React, {Component} from "react";
import PropTypes from "prop-types";
import ReactDOM from "react-dom";
import {Download, Key, Link, LoaderCircle, Timer, X} from "lucide-react";
import {handleErrors, postData} from "./index.jsx";

let domContainer = document.querySelector(".downloadLinkHolder");
let csrf = document.getElementById("csrf-token").getAttribute("content");

class Alert extends Component {

    constructor(props) {
        super(props);
    }

    render() {
        const {message, removeAlert} = this.props;
        if (!message) return null;
        return <div
            className="relative mt-3 flex items-start gap-3 rounded border border-red-900 bg-red-50 px-4 py-3 text-sm text-red-900"
            role="alert">
            <strong className="flex-1 font-semibold">{message}</strong>
            <button type="button"
                className="text-red-900 hover:text-red-700 focus:outline-none"
                onClick={removeAlert} aria-label="Close">
                <X className="h-4 w-4" aria-hidden="true" />
            </button>
        </div>;
    }
}

Alert.propTypes = {
    message: PropTypes.string.isRequired,
    removeAlert: PropTypes.func.isRequired
};

const Spinner = () => (
    <LoaderCircle className="h-4 w-4 animate-spin text-blue-900" aria-hidden="true" />
);

class DownloadLink extends Component {

    constructor(props) {
        super(props);
        this.state = {
            open: false,
            loading: false,
            link: null,
            error: null,
            hideAlert: false
        };
    }

    onDownloadClicked = (event) => {
        this.setState({loading: true, error: null});
        const {entityId} = this.props;
        event.preventDefault();
        this.getOrCreateLink(entityId).then((link) => this.openModal(link)).catch((error) => {
            if (Object.hasOwn(error, "message")) {
                error = `An error occurred, please reload the page (${error.message})`;
            }
            this.setState({"loading": false, error, hideAlert: false});
        });
    };
    openModal = (link) => {
        document.body.classList.add("overflow-hidden");
        this.setState({link, open: true, loading: false});
    };
    closeModal = () => {
        document.body.classList.remove("overflow-hidden");
        this.setState({open: false});
    };
    getOrCreateLink = () => {
        const {csrf, entityId, downloadLinkApiUrl} = this.props;
        return postData(downloadLinkApiUrl, {entityId}, csrf).then(handleErrors).then((body) => body.data);
    };

    render() {
        const {hideAlert, error, open, link, loading} = this.state;
        return (
            <>
                {open && (
                    <div id="link_modal"
                        className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
                        role="dialog" aria-modal="true" tabIndex="-1">
                        <div className="w-full max-w-lg overflow-hidden rounded bg-white shadow-lg">
                            <div className="flex items-center justify-between border-b border-gray-200 px-5 py-4">
                                <h3 className="font-display text-xl font-semibold text-blue-900">Your Access Link</h3>
                                <button type="button" onClick={this.closeModal.bind(this)}
                                    className="text-gray-600 hover:text-blue-900 focus:outline-none focus:ring-2 focus:ring-blue-900"
                                    aria-label="Close">
                                    <X className="h-5 w-5" aria-hidden="true" />
                                </button>
                            </div>
                            <div className="space-y-4 px-5 py-4 text-sm text-gray-800">
                                <div className="flex items-start gap-2">
                                    <span className="mt-0.5 text-blue-900"><Link className="h-4 w-4" aria-hidden="true" /></span>
                                    <a className="break-all font-medium text-blue-900 hover:underline"
                                        href={link.absolute_url}>{link.absolute_url}</a>
                                </div>
                                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                                    <div>
                                        <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-blue-900">
                                            <Key className="h-4 w-4" aria-hidden="true" />Password
                                        </p>
                                        <p className="mt-1 break-all font-mono text-gray-800">{link.page_password}</p>
                                    </div>
                                    <div>
                                        <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-blue-900">
                                            <Timer className="h-4 w-4" aria-hidden="true" />Valid until
                                        </p>
                                        <p className="mt-1 text-gray-800">{link.expiration_date_string}</p>
                                    </div>
                                </div>
                            </div>
                            <div className="flex justify-end border-t border-gray-200 bg-gray-50 px-5 py-3">
                                <button onClick={this.closeModal.bind(this)}
                                    className="inline-flex items-center rounded border border-blue-900 bg-blue-900 px-4 py-2 text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-2 focus:ring-blue-900 focus:ring-offset-1">
                                    Close
                                </button>
                            </div>
                        </div>
                    </div>
                )}
                <a href="#" onClick={this.onDownloadClicked.bind(this)}
                    className="inline-flex items-center gap-2 rounded border border-blue-900 bg-white px-4 py-2 text-sm font-medium text-blue-900 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-900 focus:ring-offset-1">
                    {loading ? <Spinner /> : <Download className="h-4 w-4" aria-hidden="true" />}
                    Download Data
                </a>
                {!hideAlert && error && <Alert message={error} removeAlert={() => this.setState({hideAlert: true})}/>}
            </>
        );
    }
}

DownloadLink.propTypes = {
    csrf: PropTypes.string.isRequired,
    entityId: PropTypes.string.isRequired,
    downloadLinkApiUrl: PropTypes.string.isRequired,
};

if (domContainer !== null) {
    ReactDOM.render(<DownloadLink csrf={csrf} downloadLinkApiUrl={domContainer.dataset.downloadLinkApiUrl} entityId={domContainer.dataset.entityId}/>, domContainer);
}
