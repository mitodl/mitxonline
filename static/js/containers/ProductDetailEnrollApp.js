// @flow
import React, { Fragment } from "react"
import { createStructuredSelector } from "reselect"
import { pathOr } from "ramda"
import { compose } from "redux"
import { connect } from "react-redux"
import { connectRequest } from "redux-query"

import Loader from "../components/Loader"
import { routes } from "../lib/urls"
import { EnrollmentFlaggedCourseRun } from "../flow/courseTypes"
import {
  courseRunsSelector,
  courseRunsQuery,
  courseRunsQueryKey
} from "../lib/queries/courseRuns"

import { getCookie } from "../lib/api"

type Props = {
  courseId: string,
  isLoading: ?boolean,
  courseRuns: ?Array<EnrollmentFlaggedCourseRun>,
  status: ?number
}
export class ProductDetailEnrollApp extends React.Component<Props> {
  render() {
    const { courseRuns, isLoading, status } = this.props
    const csrfToken = getCookie("csrftoken")
    const run = courseRuns ? courseRuns[0] : null

    return (
      // $FlowFixMe: isLoading null or undefined
      <Loader isLoading={isLoading}>
        {run && run.is_enrolled ? (
          <Fragment>
            {run.courseware_url ? (
              <a
                href={run.courseware_url}
                className="btn btn-primary btn-gradient-red highlight outline"
                target="_blank"
                rel="noopener noreferrer"
              >
                Enrolled &#10003;
              </a>
            ) : (
              <div className="btn btn-primary btn-gradient-red highlight outline">
                Enrolled &#10003;
              </div>
            )}
          </Fragment>
        ) : (
          <Fragment>
            {status === 403 ? (
              <a
                href={routes.login}
                className="btn btn-primary btn-gradient-red highlight"
              >
                Enroll now
              </a>
            ) : (
              <Fragment>
                <form action="/enrollments/" method="post">
                  <input
                    type="hidden"
                    name="csrfmiddlewaretoken"
                    value={csrfToken}
                  />
                  <input type="hidden" name="run" value={run ? run.id : ""} />
                  <button
                    type="submit"
                    className="btn btn-primary btn-gradient-red highlight"
                  >
                    Enroll now
                  </button>
                </form>
              </Fragment>
            )}
          </Fragment>
        )}
      </Loader>
    )
  }
}

const mapStateToProps = createStructuredSelector({
  courseRuns: courseRunsSelector,
  isLoading:  pathOr(true, ["queries", courseRunsQueryKey, "isPending"]),
  status:     pathOr(null, ["queries", courseRunsQueryKey, "status"])
})

const mapPropsToConfig = props => [courseRunsQuery(props.courseId)]

export default compose(
  connect(mapStateToProps),
  connectRequest(mapPropsToConfig)
)(ProductDetailEnrollApp)
