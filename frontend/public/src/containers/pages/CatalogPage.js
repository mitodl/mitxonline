import React from "react"
import { CSSTransition, TransitionGroup } from "react-transition-group"
import moment from "moment"
import { parseDateString, formatPrettyDate } from "../../lib/util"

import {
  coursesSelector,
  coursesQuery,
  coursesQueryKey
} from "../../lib/queries/courses"

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
  coursesIsLoading: ?boolean,
  programsIsLoading: ?boolean,
  courses: ?Array<CourseDetailWithRuns>,
  programs: ?Array<Program>
}

const ALL_DEPARTMENTS = "All Departments"

export class CatalogPage extends React.Component<Props> {
  state = {
    tabSelected:         "courses",
    filteredCourses:     [],
    filterCoursesCalled: false,
    courseTopics:        [],
    selectedTopic:       ALL_DEPARTMENTS
  }

  componentDidUpdate = () => {
    const {
      coursesIsLoading,
    } = this.props
    if (!coursesIsLoading && !this.state.filterCoursesCalled) {
      this.setState({ filterCoursesCalled: true })
      const courses = this.filteredCoursesBasedOnCourseRunCriteria(this.state.selectedTopic)
      this.setState({ filteredCourses: courses })
      this.setState({ courseTopics: this.collectCourseTopicsFromCourses(courses) })
    }
  }

  collectCourseTopicsFromCourses(courses: Array<CourseDetailWithRuns>) {
    const topics = Array.from(courses, course => course.topics)
    return [ALL_DEPARTMENTS, ...topics.flat().map(topic => topic.name)]
  }

  changeSelectedTab = (btn: string) => {
    this.setState({ tabSelected: btn })
  }

  changeSelectedTopic = (selectedTopic: string) => {
    this.setState({ selectedTopic: selectedTopic })
    this.setState({ filteredCourses: this.filteredCoursesBasedOnCourseRunCriteria(selectedTopic) })
  }

  getFutureCourseRunClosestToToday(courseRunA: BaseCourseRun, courseRunB: BaseCourseRun) {
    if (courseRunA.start_date > courseRunB.start_date) {
      return -1
    }
    if (courseRunA.start_date < courseRunB.start_date) {
      return 1
    }
    // CourseRunA and CourseRunB share the same start date.
    return 0
  }

  renderCatalogCardTagForCourse(course: CourseDetailWithRuns) {
    const nonSelfPacedCourseRuns = course.courseruns.filter(courseRun => !courseRun.is_self_paced)
    if (nonSelfPacedCourseRuns.length > 0) {
      const futureStartDateCourseRuns = nonSelfPacedCourseRuns.filter(courseRun => moment(courseRun.start_date).isAfter(moment()))
      if (futureStartDateCourseRuns.length > 0) {
        const startDate = parseDateString(futureStartDateCourseRuns.sort(this.getFutureCourseRunClosestToToday)[0].start_date)
        return `Start Date: ${formatPrettyDate(startDate)}`
      } else {
        return "Start Anytime"
      }
    } else {
      return "Start Anytime"
    }
  }

  validateCoursesCourseRuns(courseRuns: Array<BaseCourseRun>) {
    return courseRuns.filter(courseRun =>
      courseRun.live &&
      courseRun.start_date &&
      moment(courseRun?.enrollment_start).isBefore(moment()) &&
      (!courseRun.enrollment_end || moment(courseRun.enrollment_end).isAfter(moment())))
  }

  filteredCoursesBasedOnCourseRunCriteria(selectedTopic: string) {
    const {
      courses,
    } = this.props
    return courses.filter(course =>
      (
        (selectedTopic === ALL_DEPARTMENTS || course.topics.map(topic => topic.name).includes(selectedTopic)) &&
        course.page.live === true &&
        course.courseruns.length > 0 &&
        this.validateCoursesCourseRuns(course.courseruns).length > 0
      )
    )
  }

  /**
   * Returns the number of courseRuns or programs based on the selected catalog tab.
   */
  renderNumberOfCatalogItems() {
    const {
      programs,
      coursesIsLoading,
      programsIsLoading
    } = this.props
    if (this.state.tabSelected === "courses" && !coursesIsLoading) {
      return this.state.filteredCourses.length
    } else if (this.state.tabSelected === "programs" && !programsIsLoading) {
      return programs.length
    }
  }

  /**
   * Renders a single course catalog card.
   * @param {CourseDetailWithRuns} course The course instance used to populate the card.
   */
  renderCourseCatalogCard(course: CourseDetailWithRuns) {
    return (
      <a href={course.page.page_url} key={course.id}>
        <div className="col catalog-item">
          {
            <img src={course?.page?.feature_image_src} alt="" />
          }
          <div className="catalog-item-description">
            <div className="start-date-description">
              {this.renderCatalogCardTagForCourse(course)}
            </div>
            <div className="item-title">{course.title}</div>
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
            {
              <img src={program?.page?.feature_image_src} alt="" />
            }
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
   * @param {Array<CourseDetailWithRuns | Program>} itemsInCatalog The items associated with the currently selected catalog page.
   * @param {Function} renderCatalogCardFunction The card render function that will be used for each item on the current catalog page.
   */
  renderCatalogRows(
    itemsInCatalog: Array<CourseDetailWithRuns | Program>,
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
      programs,
      programsIsLoading
    } = this.props
    if (this.state.tabSelected === "courses" && this.state.filteredCourses.length > 0) {
      return this.renderCatalogRows(this.state.filteredCourses, this.renderCourseCatalogCard.bind(this))
    } else if (this.state.tabSelected === "programs" && !programsIsLoading) {
      return this.renderCatalogRows(programs, this.renderProgramCatalogCard)
    }
  }

  renderDepartmentSideBarList() {
    const departmentSideBarListItems = []
    this.state.courseTopics.forEach(courseTopic =>
      departmentSideBarListItems.push(
        <li className={this.state.selectedTopic === courseTopic ? "department-selected-link" : "department-link"} key={courseTopic}>
          <button onClick={() => this.changeSelectedTopic(courseTopic)}>
            {courseTopic}
          </button>
        </li>
      )
    )
    return (
      <div id="department-sidebar">
        <ul id="department-sidebar-link-list">
          {departmentSideBarListItems}
        </ul>
      </div>
    )
  }

  render() {
    return (
      <div id="catalog-page">
        <div id="catalog-title">
          <h1>MITx Online Catalog</h1>
        </div>
        <div id="course-catalog-navigation">
          {this.renderDepartmentSideBarList()}
          <div className="container">
            <div className="row" id="tab-row">
              <div className="col catalog-animation">
                <TransitionGroup>
                  <CSSTransition
                    key={this.state.tabSelected}
                    timeout={300}
                    classNames="messageout"
                  >
                    <div id="tabs">
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
                  </CSSTransition>
                </TransitionGroup>
              </div>
              <div className="col catalog-page-item-count">
                <div className="catalog-count-animation">
                  <TransitionGroup>
                    <CSSTransition
                      key={this.state.tabSelected}
                      timeout={300}
                      classNames="test"
                    >
                      <div>
                        {/* Could add logic to display only "course" if only 1 course is showing. */}
                        {this.renderNumberOfCatalogItems()} {this.state.tabSelected}
                      </div>
                    </CSSTransition>
                  </TransitionGroup>
                </div>
              </div>
            </div>
            <div className="catalog-animation">
              <TransitionGroup>
                <CSSTransition
                  key={this.state.tabSelected}
                  timeout={300}
                  classNames="messageout"
                >
                  <div>
                    {this.renderCatalog()}
                  </div>
                </CSSTransition>
              </TransitionGroup>
            </div>
          </div>
        </div>
      </div>
    )
  }
}

const mapPropsToConfig = () => [coursesQuery(), programsQuery()]

const mapStateToProps = createStructuredSelector({
  courses:          coursesSelector,
  programs:         programsSelector,
  coursesIsLoading: pathOr(true, [
    "queries",
    coursesQueryKey,
    "isPending"
  ]),
  programsIsLoading: pathOr(true, ["queries", programsQueryKey, "isPending"])
})

export default compose(
  connect(mapStateToProps),
  connectRequest(mapPropsToConfig)
)(CatalogPage)
