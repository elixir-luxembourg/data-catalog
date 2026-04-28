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
import ReactDOM from "react-dom";
import PropTypes from "prop-types";
import {Search} from "lucide-react";


let domContainer = document.querySelector("#autocomplete_input");

const itemBase = "block cursor-pointer px-3 py-2 text-sm text-gray-800 hover:bg-gray-100";
const itemActive = "block cursor-pointer px-3 py-2 text-sm bg-blue-900 text-white";
const headerClass = "px-3 pt-2 pb-1 text-xs font-semibold uppercase tracking-wide text-blue-900";

class Autocomplete extends Component {
    constructor(props) {
        super(props);
        this.inputRef = React.createRef();
        this.btnRef = React.createRef();
        const {query, totalEntityTitle, totalTerms, titlesSearchLink, secondaryLabel} = props;
        //Number of suggested items to appear during entering input query,
        //Total is divided in 2 between search terms and entity titles to appear
        let totalEntityTitleState = totalEntityTitle;
        let totalTermsState = totalTerms;
        if (totalEntityTitle > 0 || totalTerms > 0) {
            if (!totalEntityTitle)
                totalEntityTitleState = 0;
            if (!totalTerms)
                totalTermsState = 0;

        } else {
            totalEntityTitleState = 3;
            totalTermsState = 3;
        }

        this.state = {
            active: 0,
            filtered: [],
            isShow: false,
            inputText: query,
            suggestions: [],
            suggestionsTerms: [],
            totalTermsState,
            totalEntityTitleState
        };

        // Get complete list of entity titles and acronyms (if it exists)
        fetch(titlesSearchLink)
            .then((res) => res.json())
            .then((json) => {
                const entityTitles = [];
                for (const entryIndex in json.data) {
                    entityTitles.push({
                        "title": json.data[entryIndex].title,
                        "acronym": secondaryLabel ? json.data[entryIndex][secondaryLabel] : "",
                        "id": json.data[entryIndex].id
                    });
                }
                this.setState({
                    suggestions: entityTitles,
                });
            });
    }

    onInputChange = (e) => {
        const {suggestions, totalTermsState} = this.state;
        const {termsSearchLink, entityName} = this.props;
        const suggestionsList = suggestions.filter(x => x.title !== null);
        const input = e.currentTarget.value;

        // Keep only titles and acronyms that contains the input query
        const newFilteredSuggestions = suggestionsList.filter(
            suggestion =>
                suggestion.title.toLowerCase().indexOf(input.toLowerCase()) > -1
                || (suggestion.acronym && suggestion.acronym.toLowerCase().indexOf(input.toLowerCase()) > -1)
                || (suggestion.id.toLowerCase().indexOf(input.toLowerCase()) > -1)
        );

        // Get search term suggestions
        let currLink = termsSearchLink + input.toLowerCase().trim();
        if (input.trim() && totalTermsState > 0) {
            fetch(currLink)
                .then((res) => res.json())
                .then((json) => {
                    let suggestionsList = [];
                    if (json.data.raw_response.suggest["suggest_" + entityName][input.toLowerCase().trim()].numFound > 0) {
                        suggestionsList = json.data.raw_response.suggest["suggest_" + entityName][input.toLowerCase().trim()].suggestions;
                    } else {
                        console.log("no suggested terms found");
                    }
                    const terms = [];
                    const suggestionLowerCase = [];
                    const acronymsSuggestionsLowerCase = [];
                    newFilteredSuggestions.forEach(function (s) {
                        suggestionLowerCase.push(s.title.toLowerCase());
                        if (s.acronym) {
                            acronymsSuggestionsLowerCase.push(s.acronym.toLowerCase());
                        }
                        suggestionLowerCase.push(s.id.toLowerCase());
                    });
                    for (const suggestedTermIndex in suggestionsList) {
                        const term = suggestionsList[suggestedTermIndex].term;
                        if (
                            !suggestionLowerCase.includes(term.toLowerCase()) &&
                            !acronymsSuggestionsLowerCase.includes(term.toLowerCase())
                        ) {
                            terms.push(term);
                        }
                    }

                    this.setState({
                        suggestionsTerms: terms
                    });

                });
        }

        this.setState({
            active: 0,
            filtered: newFilteredSuggestions,
            isShow: true,
            inputText: e.currentTarget.value
        });
    };

    onItemClick(e) {
        if (e.title) {
            this.inputRef.current.value = e.title;
        } else {
            this.inputRef.current.value = e;
            this.btnRef.current.click();
        }
    }

    onInputKeyDown = (e) => {
        const {filtered, suggestionsTerms, totalTermsState, totalEntityTitleState} = this.state;
        const {entityLinkPattern} = this.props;
        if (e.keyCode === 13) { // enter key
            e.preventDefault();
            const suggestionsCombined = suggestionsTerms.slice(0, totalTermsState).concat(filtered.slice(0, totalEntityTitleState));
            if (suggestionsCombined.length > 0) {
                this.inputRef.current.value = suggestionsCombined[this.state.active].title;
                if (suggestionsCombined[this.state.active].title) {
                    this.inputRef.current.value = suggestionsCombined[this.state.active].title;
                    window.location.href = entityLinkPattern + suggestionsCombined[this.state.active].id;
                } else {
                    this.inputRef.current.value = suggestionsCombined[this.state.active];
                    this.btnRef.current.click();
                }
            }

        } else if (e.keyCode === 38 && this.state.active !== 0) { // up arrow
            this.setState({active: this.state.active - 1});
        } else if (e.keyCode === 40) { // down arrow
            const {filtered, suggestionsTerms} = this.state;
            const suggestionsCombined = suggestionsTerms.slice(0, totalTermsState).concat(filtered.slice(0, totalEntityTitleState));
            (this.state.active + 1 === suggestionsCombined.length) ? this.setState({active: 0}) : this.setState({active: this.state.active + 1});
        }
    };

    renderAutocomplete() {
        const {filtered, suggestionsTerms, isShow, inputText, totalTermsState, totalEntityTitleState} = this.state;
        const {entityName, entityLinkPattern} = this.props;
        let divider;
        let autocompleteHeaderKeyword;
        let autocompleteHeaderEntity;

        // Create dropdown divider if there are both suggested terms and entity titles
        if (filtered.length > 0 && totalTermsState > 0 && suggestionsTerms.length > 0 && totalEntityTitleState > 0) {
            divider = <div className="my-1 border-t border-gray-200"></div>;
        }

        // Create entity header if there are entities left after filtering
        if (filtered.length > 0 && totalEntityTitleState > 0) {
            autocompleteHeaderEntity = <div className={headerClass}>{entityName + "s"}</div>;
        }

        // Create keywords header if there are suggested terms
        if (suggestionsTerms.length > 0 && totalTermsState > 0) {
            autocompleteHeaderKeyword = <div className={headerClass}>Keywords</div>;
        }

        if (isShow && inputText &&
                ((filtered.length > 0 && totalEntityTitleState > 0)
                        || (suggestionsTerms.length > 0 && totalTermsState > 0))) {
            return (
                <div className="absolute left-0 right-0 top-full z-30 mt-1 max-h-96 overflow-auto rounded border border-gray-200 bg-white py-1 shadow-lg">
                    {autocompleteHeaderKeyword}
                    {
                        // List of suggested terms for search
                        suggestionsTerms.slice(0, totalTermsState).map((suggestion, index) => {
                            const className = index === this.state.active ? itemActive : itemBase;

                            return (
                                <div className={className} key={index} onClick={() => this.onItemClick(suggestion)}>
                                    {suggestion}
                                </div>
                            );
                        })
                    }
                    {divider}
                    {autocompleteHeaderEntity}
                    {
                        // List of entities with acronym or title containing the input
                        filtered.slice(0, totalEntityTitleState).map((suggestion, index) => {
                            const isActive = suggestionsTerms.slice(0, totalTermsState).length + index === this.state.active;
                            const className = isActive ? itemActive : itemBase;
                            return (
                                <a href={entityLinkPattern + suggestion.id} id={suggestion.id}
                                    key={suggestion.id}
                                    className="block no-underline">
                                    <div className={className}
                                        key={suggestionsTerms.slice(0, totalTermsState).length + index}
                                        data-entity-id={suggestion.id}
                                        onClick={() => this.onItemClick(suggestion)}>
                                        {suggestion.acronym ? `${suggestion.acronym} - ${suggestion.title}` : suggestion.title}
                                        <small className={isActive ? "ml-2 text-white/80" : "ml-2 text-gray-500"}>({suggestion.id})</small>
                                    </div>
                                </a>
                            );
                        })
                    }
                </div>
            );

        }
        return <></>;
    }

    render() {

        const {inputText} = this.state;


        return (
            <div className="relative flex w-full">
                <input
                    title="query"
                    placeholder="enter your query here"
                    type="text"
                    name="query"
                    id="query"
                    value={inputText}
                    onChange={this.onInputChange}
                    onKeyDown={this.onInputKeyDown}
                    ref={this.inputRef}
                    autoComplete="off"
                    className="block w-full flex-1 rounded-l border border-gray-200 bg-white px-3 py-2 text-sm text-blue-900 placeholder-gray-400 focus:border-blue-900 focus:outline-none focus:ring-1 focus:ring-blue-900"
                />
                <button
                    type="submit"
                    id="search-button"
                    ref={this.btnRef}
                    className="inline-flex items-center justify-center rounded-r border border-l-0 border-blue-900 bg-blue-900 px-4 py-2 text-white hover:bg-blue-800 focus:outline-none focus:ring-2 focus:ring-blue-900 focus:ring-offset-1"
                    aria-label="Search"
                >
                    <Search className="h-5 w-5" aria-hidden="true" />
                </button>
                {this.renderAutocomplete()}
            </div>
        );
    }

}

Autocomplete.propTypes = {
    query: PropTypes.string.isRequired,
    titlesSearchLink: PropTypes.string.isRequired,
    secondaryLabel: PropTypes.string,
    termsSearchLink: PropTypes.string.isRequired,
    entityLinkPattern: PropTypes.string.isRequired,
    entityName: PropTypes.string.isRequired,
    totalEntityTitle: PropTypes.string.isRequired,
    totalTerms: PropTypes.string.isRequired,
};

if (domContainer !== null) {
    const query = domContainer.getAttribute("data-query");
    const titlesSearchLink = domContainer.getAttribute("data-api-entities-link");
    const termsSearchLink = domContainer.getAttribute("data-api-search-autocomplete-entities-link");
    const entityLinkPattern = domContainer.getAttribute("data-entity-link");
    const totalEntityTitle = domContainer.getAttribute("data-total-entity-titles");
    const totalTerms = domContainer.getAttribute("data-total-terms");
    const entityName = domContainer.getAttribute("data-entity-name");
    const secondaryLabel = entityName === "project" ? "project_name" : undefined;

    ReactDOM.render(<Autocomplete entityName={entityName} totalTerms={totalTerms} totalEntityTitle={totalEntityTitle}
        query={query} secondaryLabel={secondaryLabel}
        entityLinkPattern={entityLinkPattern} titlesSearchLink={titlesSearchLink}
        termsSearchLink={termsSearchLink}
    />, domContainer);
}
