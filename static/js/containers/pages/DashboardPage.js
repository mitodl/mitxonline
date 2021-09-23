// @flow
/* global SETTINGS:false */
import React from "react"
import DocumentTitle from "react-document-title"
import { connect } from "react-redux"
import { createStructuredSelector } from "reselect"
import { compose } from "redux"
import { connectRequest } from "redux-query"
import { pathOr } from "ramda"
import moment from "moment"

import Loader from "../../components/Loader"
import { DASHBOARD_PAGE_TITLE } from "../../constants"
import {
  enrollmentsSelector,
  enrollmentsQuery,
  enrollmentsQueryKey
} from "../../lib/queries/enrollment"
import { currentUserSelector } from "../../lib/queries/users"
import { isLinkableCourseRun } from "../../lib/courseApi"
import { formatPrettyDate, parseDateString } from "../../lib/util"
import { routes } from "../../lib/urls"

import type { RunEnrollment } from "../../flow/courseTypes"
import type { CurrentUser } from "../../flow/authTypes"

type DashboardPageProps = {
  enrollments: RunEnrollment[],
  currentUser: CurrentUser,
  isLoading: boolean
}

export class DashboardPage extends React.Component<DashboardPageProps, void> {
  renderEnrolledItemCard(enrollment: RunEnrollment) {
    const { currentUser } = this.props

    let startDate, startDateDescription
    const title = isLinkableCourseRun(enrollment.run, currentUser) ? (
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
        className="enrolled-item container card p-sm-3 mb-4 rounded-0"
        key={enrollment.run.id}
      >
        <div className="row">
          <div className="col-12 col-sm-auto mr-sm-3 px-0 px-sm-3">
            {enrollment.run.course.feature_image_src && (
              <div className="img-container">
                <img
                  src={enrollment.run.course.feature_image_src}
                  alt="Preview image"
                />
              </div>
            )}
          </div>
          <div className="col-12 col-sm p-3 p-sm-0">
            <h2 className="mb-3">{title}</h2>
            <div className="detail">{startDateDescription}</div>
          </div>
        </div>
      </div>
    )
  }

  render() {
    const { enrollments, isLoading } = this.props

    return (
      <DocumentTitle title={`${SETTINGS.site_name} | ${DASHBOARD_PAGE_TITLE}`}>
        <div className="std-page-body dashboard container">
          <Loader isLoading={isLoading}>
            <h1>My Courses</h1>
            <div className="enrolled-items">
              {enrollments && enrollments.length > 0 ? (
                enrollments.map(this.renderEnrolledItemCard.bind(this))
              ) : (
                <div className="card no-enrollments p-3 p-sm-5 rounded-0">
                  <h2>Enroll Now</h2>
                  <p>
                    You are not enrolled in any courses yet. Please{" "}
                    <a href={routes.root}>browse our courses</a>.
                  </p>
                </div>
              )}
            </div>
          </Loader>
        </div>
      </DocumentTitle>
    )
  }
}

const mapStateToProps = createStructuredSelector({
  enrollments: enrollmentsSelector,
  currentUser: currentUserSelector,
  isLoading:   pathOr(true, ["queries", enrollmentsQueryKey, "isPending"])
})

const mapPropsToConfig = () => [enrollmentsQuery()]

export default compose(
  connect(mapStateToProps),
  connectRequest(mapPropsToConfig)
)(DashboardPage)
