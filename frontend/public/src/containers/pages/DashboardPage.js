// @flow
/* global SETTINGS:false */
import React from "react"
import DocumentTitle from "react-document-title"
import { connect } from "react-redux"
import { createStructuredSelector } from "reselect"
import { compose } from "redux"
import { connectRequest, mutateAsync } from "redux-query"
import { pathOr } from "ramda"
import { checkFeatureFlag } from "../../lib/util"
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
import users, { currentUserSelector } from "../../lib/queries/users"
import { addUserNotification } from "../../actions"
import { ProgramEnrollmentDrawer } from "../../components/ProgramEnrollmentDrawer"
import { Modal, ModalHeader, ModalBody } from "reactstrap"

import EnrolledCourseList from "../../components/EnrolledCourseList"
import EnrolledProgramList from "../../components/EnrolledProgramList"

import AddlProfileFieldsForm from "../../components/forms/AddlProfileFieldsForm"

import type { RunEnrollment, ProgramEnrollment } from "../../flow/courseTypes"
import type { User } from "../../flow/authTypes"

// this needs pretty drastic cleanup but not until the program bits are refactored
// to not depend on the props coming from here
type DashboardPageProps = {
  enrollments: RunEnrollment[],
  programEnrollments: ProgramEnrollment[],
  currentUser: User,
  isLoading: boolean,
  deactivateEnrollment: (enrollmentId: number) => Promise<any>,
  courseEmailsSubscription: (
    enrollmentId: number,
    emailsSubscription: string
  ) => Promise<any>,
  updateAddlFields: (currentUser: User) => Promise<any>,
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
  currentTab: string,
  showAddlProfileFieldsModal: boolean,
  destinationUrl: string
}

export class DashboardPage extends React.Component<
  DashboardPageProps,
  DashboardPageState
> {
  state = {
    programDrawerVisibility:    false,
    programDrawerEnrollments:   null,
    currentTab:                 DashboardTab.courses,
    showAddlProfileFieldsModal: false,
    destinationUrl:             ""
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

  toggleAddlProfileFieldsModal() {
    this.setState({
      showAddlProfileFieldsModal: !this.state.showAddlProfileFieldsModal
    })

    if (
      !this.state.showAddlProfileFieldsModal &&
      this.state.destinationUrl.length > 0
    ) {
      const target = this.state.destinationUrl
      this.setState({
        destinationUrl: ""
      })
      window.open(target, "_blank")
    }
  }

  redirectToCourseHomepage(url: string, ev: any) {
    /*
    If we've got addl_field_flag, then display the extra info modal. Otherwise,
    send the learner directly to the page.
    */

    const { currentUser, updateAddlFields } = this.props

    if (
      !checkFeatureFlag("enable_addl_profile_fields") ||
      (currentUser.user_profile && currentUser.user_profile.addl_field_flag)
    ) {
      return
    }

    ev.preventDefault()

    this.setState({
      destinationUrl:             url,
      showAddlProfileFieldsModal: true
    })

    updateAddlFields(currentUser)
  }

  async saveProfile(profileData: User, { setSubmitting }: Object) {
    const { updateAddlFields } = this.props

    try {
      await updateAddlFields(profileData)
    } finally {
      setSubmitting(false)
      this.toggleAddlProfileFieldsModal()
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
          redirectToCourseHomepage={this.redirectToCourseHomepage.bind(this)}
        ></EnrolledCourseList>
      </div>
    )
  }

  renderAddlProfileFieldsModal() {
    const { currentUser } = this.props
    const { showAddlProfileFieldsModal } = this.state

    return (
      <Modal
        id={`upgrade-enrollment-dialog`}
        className="upgrade-enrollment-modal"
        isOpen={showAddlProfileFieldsModal}
        toggle={() => this.toggleAddlProfileFieldsModal()}
      >
        <ModalHeader
          id={`more-info-modal-${currentUser.id}`}
          toggle={() => this.toggleAddlProfileFieldsModal()}
        >
          Provide More Info
        </ModalHeader>
        <ModalBody>
          <div className="row">
            <div className="col-12">
              <p>
                To help us with our education research missions, please tell us
                more about yourself. If you do not want to supply this
                information, simply click the Close button - we won't ask you
                again.
              </p>
            </div>
          </div>

          <AddlProfileFieldsForm
            onSubmit={this.saveProfile.bind(this)}
            onCancel={() => this.toggleAddlProfileFieldsModal()}
            user={currentUser}
          ></AddlProfileFieldsForm>
        </ModalBody>
      </Modal>
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
                  <strong style={{ fontSize: "75%" }}>My Courses</strong>
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
                    My Programs
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
              redirectToCourseHomepage={this.redirectToCourseHomepage}
            ></ProgramEnrollmentDrawer>

            {this.renderAddlProfileFieldsModal()}
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

const updateAddlFields = (currentUser: User) => {
  const updatedUser = {
    name:          currentUser.name,
    email:         currentUser.email,
    legal_address: currentUser.legal_address,
    user_profile:  {
      ...currentUser.user_profile,
      addl_field_flag: true
    }
  }

  return mutateAsync(users.editProfileMutation(updatedUser))
}

const mapDispatchToProps = {
  deactivateEnrollment,
  courseEmailsSubscription,
  updateAddlFields,
  addUserNotification
}

export default compose(
  connect(mapStateToProps, mapDispatchToProps),
  connectRequest(mapPropsToConfig)
)(DashboardPage)
