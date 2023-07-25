import React from "react"

import {
  courseRunsSelector,
  courseRunsQuery,
  courseRunsQueryKey
} from "../../lib/queries/courseRuns"

import { createStructuredSelector } from "reselect"
import { compose } from "redux"
import { connect } from "react-redux"
import { connectRequest } from "redux-query"
import { pathOr } from "ramda"


type Props = {
  isLoading: ?boolean,
  courseRuns: ?Array<EnrollmentFlaggedCourseRun>,
}


export class CatalogPage extends React.Component<Props> {
  state = {
    tabSelected: "courses"
  }

  changeSelectedTab = (btn: string) => {
    this.setState({ tabSelected: btn })
  };

  renderCourseCatalogCard(courseRun: EnrollmentFlaggedCourseRun) {
    return (
      <div className="catalog-item">
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

  renderCatalogItems() {
    const { courseRuns, isLoading} = this.props
    let catalogItems = []
    console.log(isLoading)
    console.log(courseRuns)
    if (!isLoading) {
      if (this.state.tabSelected === "courses") {
        console.log("in")
        catalogItems = courseRuns.map(x => this.renderCourseCatalogCard(x))
        console.log(catalogItems)
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
                18 courses
              </div>
            </div>
            <div className="row" id="catalog-grid">
              {this.renderCatalogItems()}
            </div>
          </div>
        </div>
      </div>
    )
  }
}

const mapPropsToConfig = () => [
  courseRunsQuery(),
]

const mapStateToProps = createStructuredSelector({
  courseRuns:  courseRunsSelector,
  isLoading:   pathOr(true, ["queries", courseRunsQueryKey, "isPending"]),
})

export default compose(
  connect(mapStateToProps),
  connectRequest(mapPropsToConfig)
)(CatalogPage)
