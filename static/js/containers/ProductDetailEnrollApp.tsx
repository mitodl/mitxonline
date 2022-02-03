import Cookies from "js-cookie"
import React, { Fragment } from "react"
import { useSelector } from "react-redux"
import { useRequest } from "redux-query-react"
import Loader from "../components/Loader"
import { isWithinEnrollmentPeriod } from "../lib/courseApi"
import { courseRunsQuery, courseRunsSelector } from "../lib/queries/courseRuns"
import { routes } from "../lib/urls"

type Props = {
  courseId: string
}

export default function ProductDetailEnrollApp({ courseId }: Props) {
  const [{ isPending, status }] = useRequest(courseRunsQuery(courseId))
  const courseRuns = useSelector(courseRunsSelector)
  const csrfToken = Cookies.get("csrftoken")
  const run = courseRuns ? courseRuns[0] : null

  return (
    <Loader isLoading={isPending}>
      {run?.is_enrolled ? (
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
              href={routes.login.toString()}
              className="btn btn-primary btn-gradient-red highlight"
            >
              Enroll now
            </a>
          ) : run && isWithinEnrollmentPeriod(run) ? (
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
          ) : null}
        </Fragment>
      )}
    </Loader>
  )
}
