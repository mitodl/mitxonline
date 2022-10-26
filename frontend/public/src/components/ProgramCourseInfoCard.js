// @flow
import React from "react"

import { generateStartDateText } from "../lib/courseApi"

import type { CourseDetailWithRuns } from "../flow/courseTypes"

type ProgramCourseInfoCardProps = {
  course: CourseDetailWithRuns
}

export class ProgramCourseInfoCard extends React.Component<ProgramCourseInfoCardProps> {
  render() {
    const { course } = this.props

    let startDateDescription = null
    let featuredImage = null
    let courseDetailsPage = null

    if (course.courseruns.length > 0) {
      startDateDescription = generateStartDateText(course.courseruns[0])

      if (course.courseruns[0].page) {
        courseDetailsPage = course.courseruns[0].page.page_url
      }
    }

    if (course.feature_image_src) {
      featuredImage = (
        <div className="col-12 col-md-auto px-0 px-md-3">
          <div className="img-container">
            <img src={course.feature_image_src} alt="Preview image" />
          </div>
        </div>
      )
    }

    return (
      <div
        className="enrolled-item container card mb-4 rounded-0 pb-0 pt-md-3"
        key={course.readable_id}
      >
        <div className="row flex-grow-1">
          {featuredImage}
          <div className="col-12 col-md px-3 py-3 py-md-0 box">
            <div className="d-flex justify-content-between align-content-start flex-nowrap w-100 enrollment-mode-container">
              <h2 className="my-0 mr-3">{course.title}</h2>
            </div>
            <div className="detail pt-1">
              {course.readable_id.split("+")[1] || course.readable_id}
              {startDateDescription !== null && startDateDescription.active ? (
                <span> | Starts - {startDateDescription.datestr}</span>
              ) : (
                <span>
                  {startDateDescription === null ? null : (
                    <span>
                      <strong>Active</strong> from{" "}
                      {startDateDescription.datestr}
                    </span>
                  )}
                </span>
              )}
              <div className="enrollment-extra-links d-flex">
                {courseDetailsPage ? (
                  <a href={courseDetailsPage}>Course details</a>
                ) : null}
              </div>
              <br />
            </div>
          </div>
        </div>
        <div className="row flex-grow-1 pt-3">
          <div className="col pl-0 pr-0">{null}</div>
        </div>
      </div>
    )
  }
}

export default ProgramCourseInfoCard
