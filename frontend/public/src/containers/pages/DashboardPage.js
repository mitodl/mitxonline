// @flow
/* global SETTINGS:false */
import React from "react"
import DocumentTitle from "react-document-title"
import { connect } from "react-redux"
import { createStructuredSelector } from "reselect"
import { compose } from "redux"
import { connectRequest, mutateAsync } from "redux-query"
import { pathOr } from "ramda"

import Loader from "../../components/Loader"
import { DASHBOARD_PAGE_TITLE } from "../../constants"
import {
  enrollmentsSelector,
  enrollmentsQuery,
  enrollmentsQueryKey,
  programEnrollmentsQuery,
  programEnrollmentsSelector,
  deactivateEnrollmentMutation,
  courseEmailsSubscriptionMutation
} from "../../lib/queries/enrollment"
import { currentUserSelector } from "../../lib/queries/users"
import { addUserNotification } from "../../actions"
import { ProgramEnrollmentDrawer } from "../../components/ProgramEnrollmentDrawer"

import EnrolledCourseList from "../../components/EnrolledCourseList"
import EnrolledProgramList from "../../components/EnrolledProgramList"

import type { RunEnrollment, ProgramEnrollment } from "../../flow/courseTypes"
import type { CurrentUser } from "../../flow/authTypes"

// this needs pretty drastic cleanup but not until the program bits are refactored
// to not depend on the props coming from here
type DashboardPageProps = {
  enrollments: RunEnrollment[],
  programEnrollments: ProgramEnrollment[],
  currentUser: CurrentUser,
  isLoading: boolean,
  deactivateEnrollment: (enrollmentId: number) => Promise<any>,
  courseEmailsSubscription: (
    enrollmentId: number,
    emailsSubscription: string
  ) => Promise<any>,
  addUserNotification: Function,
  closeDrawer: Function
}

const DashboardTab = {
  courses:  "courses",
  programs: "programs"
}

type DashboardPageState = {
  programDrawerVisibility: boolean,
  programDrawerEnrollments: ?(any[]),
  currentTab: string
}

export class DashboardPage extends React.Component<
  DashboardPageProps,
  DashboardPageState
> {
  state = {
    programDrawerVisibility:  false,
    programDrawerEnrollments: null,
    currentTab:               DashboardTab.courses
  }

  toggleDrawer(enrollment: any) {
    this.setState({
      programDrawerEnrollments: enrollment,
      programDrawerVisibility:  !this.state.programDrawerVisibility
    })
  }

  toggleTab(tab: string) {
    if (tab === DashboardTab.courses || tab === DashboardTab.programs) {
      this.setState({ currentTab: tab })
    }
  }

  renderCurrentTab() {
    const { enrollments, programEnrollments } = this.props

    if (this.state.currentTab === DashboardTab.programs) {
      return (
        <div>
          <h1 className="hide-element">Programs</h1>
          <EnrolledProgramList
            key={"enrolled-programs"}
            enrollments={programEnrollments}
            toggleDrawer={this.toggleDrawer.bind(this)}
          ></EnrolledProgramList>
        </div>
      )
    }

    return (
      <div>
        <h1 className="hide-element">My Courses</h1>
        <EnrolledCourseList
          key={"enrolled-courses"}
          enrollments={enrollments}
        ></EnrolledCourseList>
      </div>
    )
  }

  render() {
    const { isLoading, programEnrollments } = this.props

    const myCourseClasses = `dash-tab${
      this.state.currentTab === DashboardTab.courses ? " active" : ""
    }`
    const programsClasses = `dash-tab${
      this.state.currentTab === DashboardTab.programs ? " active" : ""
    }`
    const programEnrollmentsLength = programEnrollments
      ? programEnrollments.length
      : 0

    return (
      <DocumentTitle title={`${SETTINGS.site_name} | ${DASHBOARD_PAGE_TITLE}`}>
        <div className="std-page-body dashboard container">
          <Loader isLoading={isLoading}>
            <nav className="tabs" aria-controls="enrollment-items">
              {programEnrollmentsLength === 0 ? (
                <>
                  <strong style={{ "font-size": "75%" }}>My Courses</strong>
                </>
              ) : (
                <>
                  <button
                    className={myCourseClasses}
                    onClick={() => this.toggleTab(DashboardTab.courses)}
                  >
                    My Courses
                  </button>
                  <button
                    className={programsClasses}
                    onClick={() => this.toggleTab(DashboardTab.programs)}
                  >
                    Programs
                  </button>
                </>
              )}
            </nav>
            <div
              id="enrollment-items"
              className="enrolled-items"
              aria-live="polite"
            >
              {this.renderCurrentTab()}
            </div>

            <ProgramEnrollmentDrawer
              isHidden={this.state.programDrawerVisibility}
              enrollment={this.state.programDrawerEnrollments}
              showDrawer={() =>
                this.setState({ programDrawerVisibility: false })
              }
            ></ProgramEnrollmentDrawer>
          </Loader>
        </div>
      </DocumentTitle>
    )
  }
}

const mapStateToProps = createStructuredSelector({
  enrollments:        enrollmentsSelector,
  programEnrollments: programEnrollmentsSelector,
  currentUser:        currentUserSelector,
  isLoading:          pathOr(true, ["queries", enrollmentsQueryKey, "isPending"])
})

const mapPropsToConfig = () => [enrollmentsQuery(), programEnrollmentsQuery()]

const deactivateEnrollment = (enrollmentId: number) =>
  mutateAsync(deactivateEnrollmentMutation(enrollmentId))

const courseEmailsSubscription = (
  enrollmentId: number,
  emailsSubscription: string
) =>
  mutateAsync(
    courseEmailsSubscriptionMutation(enrollmentId, emailsSubscription)
  )

const mapDispatchToProps = {
  deactivateEnrollment,
  courseEmailsSubscription,
  addUserNotification
}

export default compose(
  connect(mapStateToProps, mapDispatchToProps),
  connectRequest(mapPropsToConfig)
)(DashboardPage)
