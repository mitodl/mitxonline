import React from "react"

import {
  courseRunsSelector,
  courseRunsQuery,
  courseRunsQueryKey
} from "../../lib/queries/courseRuns"

import {
  programsSelector,
  programsQuery,
  programsQueryKey
} from "../../lib/queries/programs"

import { createStructuredSelector } from "reselect"
import { compose } from "redux"
import { connect } from "react-redux"
import { connectRequest } from "redux-query"
import { pathOr } from "ramda"

type Props = {
  courseRunsIsLoading: ?boolean,
  programsIsLoading: ?boolean,
  courseRuns: ?Array<EnrollmentFlaggedCourseRun>,
  programs: ?Array<Program>
}

export class CatalogPage extends React.Component<Props> {
  state = {
    tabSelected: "courses"
  }

  changeSelectedTab = (btn: string) => {
    this.setState({ tabSelected: btn })
  }

  /**
   * Returns the number of courseRuns or programs based on the selected catalog tab.
   */
  renderNumberOfCatalogItems() {
    const {
      courseRuns,
      programs,
      courseRunsIsLoading,
      programsIsLoading
    } = this.props
    if (this.state.tabSelected === "courses" && !courseRunsIsLoading) {
      return courseRuns.length
    } else if (this.state.tabSelected === "programs" && !programsIsLoading) {
      return programs.length
    }
  }

  /**
   * Renders a single course catalog card.
   * @param {EnrollmentFlaggedCourseRun} courseRun The course run instance used to populate the card.
   */
  renderCourseCatalogCard(courseRun: EnrollmentFlaggedCourseRun) {
    return (
      <a href={courseRun.page.page_url} key={courseRun.id}>
        <div className="col catalog-item">
          {courseRun.page && courseRun.page.feature_image_src && (
            <img src={courseRun.page.feature_image_src} alt="" />
          )}
          <div className="catalog-item-description">
            <div className="start-date-description">
              {courseRun.is_self_paced ? "Start Anytime" : courseRun.start_date}
            </div>
            <div className="item-title">{courseRun.title}</div>
          </div>
        </div>
      </a>
    )
  }

  /**
   * Renders a single program catalog card.
   * @param {Program} program The program instance used to populate the card.
   */
  renderProgramCatalogCard(program: Program) {
    return (
      <a href={program.page.page_url} key={program.id}>
        <div className="col catalog-item">
          <div className="program-image-and-badge">
            {program.page && program.page.feature_image_src && (
              <img src={program.page.feature_image_src} alt="" />
            )}
            <div className="program-type-badge">{program.program_type}</div>
          </div>
          <div className="catalog-item-description">
            <div className="item-title">{program.title}</div>
          </div>
        </div>
      </a>
    )
  }

  /**
   * Dynamically renders all rows of cards in the catalog.  Each row contains 3 course or program cards.
   * @param {Array<EnrollmentFlaggedCourseRun | Program>} itemsInCatalog The items associated with the currently selected catalog page.
   * @param {Function} renderCatalogCardFunction The card render function that will be used for each item on the current catalog page.
   */
  renderCatalogRows(
    itemsInCatalog: Array<EnrollmentFlaggedCourseRun | Program>,
    renderCatalogCardFunction: Function
  ) {
    const numberOfItemsInEachRow = Math.min(itemsInCatalog.length, 3)
    const catalogRows = []
    for (let i = 0; i < itemsInCatalog.length; i += numberOfItemsInEachRow) {
      const itemsInRow = itemsInCatalog.slice(i, i + numberOfItemsInEachRow)
      catalogRows.push(
        <div className="row" id="catalog-grid" key={i}>
          {itemsInRow.map(x => renderCatalogCardFunction(x))}
        </div>
      )
    }
    return catalogRows
  }

  /**
   * Renders the entire catalog of course or program cards based on the catalog tab selected.
   */
  renderCatalog() {
    const {
      courseRuns,
      programs,
      courseRunsIsLoading,
      programsIsLoading
    } = this.props
    if (this.state.tabSelected === "courses" && !courseRunsIsLoading) {
      return this.renderCatalogRows(courseRuns, this.renderCourseCatalogCard)
    } else if (this.state.tabSelected === "programs" && !programsIsLoading) {
      return this.renderCatalogRows(programs, this.renderProgramCatalogCard)
    }
  }

  render() {
    return (
      <div id="catalog-page">
        <div id="catalog-title">
          <h1>MITx Online Catalog</h1>
        </div>
        <div id="course-catalog-navigation">
          <div id="department-sidebar">
            <ul id="department-sidebar-link-list">
              <li className="department-selected-link">All Departments</li>
              <li className="department-link">Tea</li>
              <li className="department-link">Milk</li>
            </ul>
          </div>
          <div className="container">
            <div className="row" id="tab-row">
              <div className="col" id="tabs">
                <div
                  className={
                    this.state.tabSelected === "courses"
                      ? "selected-tab"
                      : "unselected-tab"
                  }
                >
                  <button onClick={() => this.changeSelectedTab("courses")}>
                    Courses
                  </button>
                </div>
                <div
                  className={
                    this.state.tabSelected === "programs"
                      ? "selected-tab"
                      : "unselected-tab"
                  }
                >
                  <button onClick={() => this.changeSelectedTab("programs")}>
                    Programs
                  </button>
                </div>
              </div>
              <div className="col" id="catalog-page-item-count">
                {/* Could add logic to display only "course" if only 1 course is showing. */}
                {this.renderNumberOfCatalogItems()} {this.state.tabSelected}
              </div>
            </div>
            {this.renderCatalog()}
          </div>
        </div>
      </div>
    )
  }
}

const mapPropsToConfig = () => [courseRunsQuery(), programsQuery()]

const mapStateToProps = createStructuredSelector({
  courseRuns:          courseRunsSelector,
  programs:            programsSelector,
  courseRunsIsLoading: pathOr(true, [
    "queries",
    courseRunsQueryKey,
    "isPending"
  ]),
  programsIsLoading: pathOr(true, ["queries", programsQueryKey, "isPending"])
})

export default compose(
  connect(mapStateToProps),
  connectRequest(mapPropsToConfig)
)(CatalogPage)
