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
  programs: ?Array<Program>,
}

export class CatalogPage extends React.Component<Props> {
  state = {
    tabSelected: "courses",
  }

  changeSelectedTab = (btn: string) => {
    this.setState({ tabSelected: btn })
  };

  renderNumberOfCatalogItems() {
    const { courseRuns, programs, courseRunsIsLoading, programsIsLoading} = this.props
    if (this.state.tabSelected === "courses" && !courseRunsIsLoading) {
      return (
        courseRuns.length
      )
    } else if (this.state.tabSelected === "programs" && !programsIsLoading) {
      return (
        programs.length
      )
    }
  }

  renderCourseCatalogCard(courseRun: EnrollmentFlaggedCourseRun) {
    return (
      <div className="col catalog-item">
        {
          courseRun.page &&
          courseRun.page.feature_image_src && (
            <img src={courseRun.page.feature_image_src} alt="" />
          )
        }
        <div className="catalog-item-description">
          <div className="start-date-description">
            Start Anytime
          </div>
          <div className="item-title">
            {courseRun.title}
          </div>
        </div>
      </div>
    )
  }

  renderProgramCatalogCard(program: Program) {
    return (
      <div className="col catalog-item">
        <div className="program-image-and-badge">
          {
            program.page &&
            program.page.feature_image_src && (
              <img src={program.page.feature_image_src} alt="" />
            )
          }
          <div className="program-type-badge">
            {program.program_type}
          </div>
        </div>
        <div className="catalog-item-description">
          <div className="item-title">
            {program.title}
          </div>
        </div>
      </div>
    )
  }

  renderCatalogRow(itemsInRow: Array<EnrollmentFlaggedCourseRun | Program>, renderCatalogCardFunction: Function) {
    return itemsInRow.map(x => renderCatalogCardFunction(x))
  }

  renderCatalogItems() {
    const { courseRuns, programs, courseRunsIsLoading, programsIsLoading} = this.props
    const catalogItems = []
    if (this.state.tabSelected === "courses" && !courseRunsIsLoading) {
      const itemsInEachRow = Math.min(courseRuns.length, 3)
      for (let i = 0; i < courseRuns.length; i += itemsInEachRow) {
        catalogItems.push(
          <div className="row" id="catalog-grid">
            {this.renderCatalogRow(courseRuns.slice(i, i + itemsInEachRow), this.renderCourseCatalogCard)}
          </div>
        )
      }
    } else if (this.state.tabSelected === "programs" && !programsIsLoading) {
      const itemsInEachRow = Math.min(programs.length, 3)
      for (let i = 0; i < programs.length; i += itemsInEachRow) {
        catalogItems.push(
          <div className="row" id="catalog-grid">
            {this.renderCatalogRow(programs.slice(i, i + itemsInEachRow), this.renderProgramCatalogCard)}
          </div>
        )
      }
    }

    return catalogItems
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
                <div className={this.state.tabSelected === "courses" ? "selected-tab" : "unselected-tab"}>
                  <button onClick={() => this.changeSelectedTab("courses")}>Courses</button>
                </div>
                <div className={this.state.tabSelected === "programs" ? "selected-tab" : "unselected-tab"}>
                  <button onClick={() => this.changeSelectedTab("programs")}>Programs</button>
                </div>
              </div>
              <div className="col" id="catalog-page-item-count">
                {/* Could add logic to display only "course" if only 1 course is showing. */}
                {this.renderNumberOfCatalogItems()} {this.state.tabSelected}
              </div>
            </div>
            {this.renderCatalogItems()}
          </div>
        </div>
      </div>
    )
  }
}

const mapPropsToConfig = () => [
  courseRunsQuery(),
  programsQuery(),
]

const mapStateToProps = createStructuredSelector({
  courseRuns:            courseRunsSelector,
  programs:              programsSelector,
  courseRunsIsLoading:   pathOr(true, ["queries", courseRunsQueryKey, "isPending"]),
  programsIsLoading:     pathOr(true, ["queries", programsQueryKey, "isPending"]),
})

export default compose(
  connect(mapStateToProps),
  connectRequest(mapPropsToConfig)
)(CatalogPage)
