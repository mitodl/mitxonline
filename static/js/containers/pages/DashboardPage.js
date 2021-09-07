// @flow
/* global SETTINGS:false */
import React from "react"
import DocumentTitle from "react-document-title"
import { connect } from "react-redux"
import { createStructuredSelector } from "reselect"
import { compose } from "redux"
import { connectRequest } from "redux-query"
import moment from "moment"
import { isLinkableCourseRun } from "../../lib/courseApi"
import { DASHBOARD_PAGE_TITLE } from "../../constants"
import {
  enrollmentsSelector,
  enrollmentsQuery
} from "../../lib/queries/enrollment"
import { formatPrettyDate, parseDateString } from "../../lib/util"

import { RunEnrollment } from "../../flow/courseTypes"

type DashboardPageProps = {
  enrollments: RunEnrollment[]
}

export class DashboardPage extends React.Component<DashboardPageProps, void> {
  renderEnrolledItemCard(enrollment: RunEnrollment) {
    let startDate, startDateDescription
    const title = isLinkableCourseRun(enrollment.run) ? (
      <a
        href={enrollment.run.courseware_url}
        target="_blank"
        rel="noopener noreferrer"
      >
        {enrollment.run.course.title}
      </a>
    ) : (
      enrollment.run.course.title
    )
    if (enrollment.run.start_date) {
      const now = moment()
      startDate = parseDateString(enrollment.run.start_date)
      const formattedStartDate = formatPrettyDate(startDate)
      startDateDescription = now.isBefore(startDate) ? (
        <span>Starts - {formattedStartDate}</span>
      ) : (
        <span>
          <strong>Active</strong> from {formattedStartDate}
        </span>
      )
    }

    return (
      <div
        className="enrolled-item row card p-sm-3 mb-4 rounded-0"
        key={enrollment.run.id}
      >
        <div className="img-col col-12 col-sm-2 p-0 mr-sm-3">
          {enrollment.run.course.feature_image_src && (
            <img
              src={enrollment.run.course.feature_image_src}
              alt="Preview image"
            />
          )}
        </div>
        <div className="col-12 col-sm p-3 p-sm-0">
          <h4 className="mb-3">{title}</h4>
          <div className="detail">{startDateDescription}</div>
        </div>
      </div>
    )
  }

  render() {
    const { enrollments } = this.props

    return (
      <DocumentTitle title={`${SETTINGS.site_name} | ${DASHBOARD_PAGE_TITLE}`}>
        <div className="dashboard container">
          <h1>My Courses</h1>
          <div className="enrolled-items container">
            {enrollments && enrollments.length > 0 ? (
              enrollments.map(this.renderEnrolledItemCard)
            ) : (
              <div className="enrolled-item row card p-3 p-sm-5 rounded-0">
                Once you enroll in a course, you can find it listed here.
              </div>
            )}
          </div>
        </div>
      </DocumentTitle>
    )
  }
}

const mapStateToProps = createStructuredSelector({
  enrollments: enrollmentsSelector
})

const mapPropsToConfig = () => [enrollmentsQuery()]

export default compose(
  connect(mapStateToProps),
  connectRequest(mapPropsToConfig)
)(DashboardPage)
