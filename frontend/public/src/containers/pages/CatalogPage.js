import React from "react"
import { CSSTransition, TransitionGroup } from "react-transition-group"
import moment from "moment"
import { parseDateString, formatPrettyDate } from "../../lib/util"

import {
  coursesSelector,
  coursesNextPageSelector,
  coursesQuery,
  coursesQueryKey
} from "../../lib/queries/courses"

import {
  programsSelector,
  programsNextPageSelector,
  programsQuery,
  programsQueryKey
} from "../../lib/queries/programs"

import { createStructuredSelector } from "reselect"
import { compose } from "redux"
import { connect } from "react-redux"
import { connectRequest, requestAsync } from "redux-query"
import { pathOr } from "ramda"

type Props = {
  coursesIsLoading: ?boolean,
  programsIsLoading: ?boolean,
  courses: ?Array<CourseDetailWithRuns>,
  programs: ?Array<Program>,
  forceRequest: () => Promise<*>,
  coursesNextPage: ?string,
  programsNextPage: ?string
}

// Department filter name for all items.
const ALL_DEPARTMENTS = "All Departments"

// Program tab name.
const PROGRAMS_TAB = "programs"

// Course tab name.
const COURSES_TAB = "courses"

export class CatalogPage extends React.Component<Props> {
  state = {
    tabSelected:                COURSES_TAB,
    allCoursesRetrieved:        [],
    allProgramsRetrieved:       [],
    filteredCourses:            [],
    filteredPrograms:           [],
    filterCoursesCalled:        false,
    departments:                [],
    selectedDepartment:         ALL_DEPARTMENTS,
    mobileFilterWindowExpanded: false,
    items_per_row:              3,
    courseQueryPage:            1,
    programQueryPage:           1,
    isLoadingMoreItems:         false
  }

  constructor(props) {
    super(props)
    this.io = null
    this.container = React.createRef(null)
  }

  componentWillUnmount() {
    if (this.io) {
      this.io.disconnect()
    }
    window.removeEventListener("resize", this.resize.bind(this))
  }

  componentDidMount() {
    window.addEventListener("resize", this.resize.bind(this))
    this.resize()
  }

  /**
   * Changes the items_per_row state variable when the screen size changes.
   * If the screen is less than 1404px wide, then the max items per row is 2.
   * If the screen is larger or equal to 1404px wide, then the max items per row is 3.
   */
  resize() {
    if (window.innerWidth < 1404 && this.state.items_per_row !== 2) {
      this.setState({ items_per_row: 2 })
    }
    if (window.innerWidth >= 1404 && this.state.items_per_row !== 3) {
      this.setState({ items_per_row: 3 })
    }
  }

  /**
   * Makes another API call to the courses or programs endpoint if there is
   * a next page defined in the prior request.
   * Appends the courses or programs from the API call to the current allCoursesRetrieved
   * or allProgramsRetrieved state variable.  Increments the courseQueryPage or programQueryPage
   * state variable.  Updates the filteredCourses or filteredPrograms state variable using the
   * updated allCoursesRetrieved or allProgramsRetrieved state variable.
   */
  bottomOfLoadedCatalogCallback = async entries => {
    const [entry] = entries
    if (entry.isIntersecting) {
      if (this.state.tabSelected === COURSES_TAB) {
        const { getNextCoursePage, coursesNextPage } = this.props

        // Only request the next page if a next page exists (coursesNextPage)
        // and if we aren't already requesting the next page (isLoadingMoreItems).
        if (coursesNextPage && !this.state.isLoadingMoreItems) {
          this.setState({ isLoadingMoreItems: true })
          this.setState({ courseQueryPage: this.state.courseQueryPage + 1 })
          const response = await getNextCoursePage(this.state.courseQueryPage)
          this.setState({ isLoadingMoreItems: false })
          if (response.body.results) {
            const filteredCourses = this.filteredCoursesBasedOnCourseRunCriteria(
              this.state.selectedDepartment,
              [...this.state.allCoursesRetrieved, ...response.body.results]
            )
            this.setState({ filteredCourses: filteredCourses })
            this.setState({
              allCoursesRetrieved: [
                ...this.state.allCoursesRetrieved,
                ...response.body.results
              ]
            })
          }
        }
      } else {
        const { getNextProgramPage, programsNextPage } = this.props
        if (programsNextPage) {
          this.setState({ isLoadingMoreItems: true })
          const response = await getNextProgramPage(
            this.state.programQueryPage + 1
          )
          this.setState({ isLoadingMoreItems: false })
          this.setState({ programQueryPage: this.state.programQueryPage + 1 })
          if (response.body.results) {
            const filteredPrograms = this.filteredProgramsByDepartmentAndCriteria(
              this.state.selectedDepartment,
              [...this.state.allProgramsRetrieved, ...response.body.results]
            )
            this.setState({ filteredPrograms: filteredPrograms })
            this.setState({
              allProgramsRetrieved: [
                ...this.state.allProgramsRetrieved,
                ...response.body.results
              ]
            })
          }
        }
      }
    }
  }

  /**
   * Updates the filteredCourses and courseDepartments state variables
   * once coursesIsLoading is False.  Adds an observer to detect when
   * the learner has scrolled to the bottom of the visible catalog items.
   */
  componentDidUpdate = () => {
    const { courses, coursesIsLoading } = this.props
    if (!coursesIsLoading && !this.state.filterCoursesCalled) {
      this.setState({ filterCoursesCalled: true })
      this.setState({ allCoursesRetrieved: courses })
      const filteredCourses = this.filteredCoursesBasedOnCourseRunCriteria(
        this.state.selectedDepartment,
        courses
      )
      this.setState({ filteredCourses: filteredCourses })
      this.setState({
        departments: this.collectDepartmentsFromCatalogItems(filteredCourses)
      })

      // Detect when the bottom of the catalog page has been reached and display more catalog items.
      this.io = new window.IntersectionObserver(
        this.bottomOfLoadedCatalogCallback,
        { threshold: 1.0 }
      )
      this.io.observe(this.container.current)
    }
  }

  /**
   * Returns an array of unique Department names that are associated with the Courses or Programs in the
   * parameter and also includes an entry for "All Departments".
   * @param {Array<CourseDetailWithRuns | Program>} catalogItems Array of Courses or Programs to collect Department names from.
   */
  collectDepartmentsFromCatalogItems(
    catalogItems: Array<CourseDetailWithRuns | Program>
  ) {
    const departments = Array.from(catalogItems, item => item.departments)
    return [
      ...new Set([
        ALL_DEPARTMENTS,
        ...departments.flat().map(department => department.name)
      ])
    ]
  }

  /**
   * Updates this.state.selectedDepartment to {ALL_DEPARTMENTS},
   * updates this.state.tabSelected to the parameter,
   * updates this.state.numberCatalogRowsToDisplay to {DEFAULT_MIN_CATALOG_ROWS_RENDERED},
   * updates this.state.departments to equal the unique department
   * names from the catalog items in the selected tab,
   * updates this.state.filteredPrograms to equal the programs
   * which meet the criteria to be displayed in the catalog.
   * @param {string} selectTabName The name of the tab that was selected.
   */
  changeSelectedTab = (selectTabName: string) => {
    this.setState({ tabSelected: selectTabName })
    this.changeSelectedDepartment(ALL_DEPARTMENTS, selectTabName)

    if (selectTabName === COURSES_TAB) {
      const { coursesIsLoading } = this.props
      if (!coursesIsLoading) {
        this.setState({
          departments: this.collectDepartmentsFromCatalogItems(
            this.state.allCoursesRetrieved
          )
        })
      }
    } else {
      const { programs, programsIsLoading } = this.props
      if (!programsIsLoading) {
        const programsToFilter = []
        // The first time that a user switches to the programs tab, allProgramsRetrieved will be
        // empty and should be populated with the results from the first programs API call.
        if (this.state.allProgramsRetrieved.length === 0) {
          this.setState({ allProgramsRetrieved: programs })
          programsToFilter.push(...programs)
        } else {
          programsToFilter.push(...this.state.allProgramsRetrieved)
        }

        const filteredPrograms = this.filteredProgramsByDepartmentAndCriteria(
          this.state.selectedDepartment,
          programsToFilter
        )
        this.setState({
          filteredPrograms: filteredPrograms
        })
        this.setState({
          departments: this.collectDepartmentsFromCatalogItems(programsToFilter)
        })
      }
    }
  }

  /**
   * Set the value of this.state.mobileFilterWindowExpanded.
   * @param {boolean} expanded The value that this.state.mobileFilterWindowExpanded will be set to.
   */
  toggleMobileFilterWindowExpanded = (expanded: boolean) => {
    this.setState({ mobileFilterWindowExpanded: expanded })
  }

  /**
   * Changes the selectedDepartment state variable and, depending on the value of tabSelected, updates either
   * the filteredCourses or filteredPrograms state variable.
   * @param {string} selectedDepartment The department name to set selectedDepartment to and filter courses by.
   */
  changeSelectedDepartment = (
    selectedDepartment: string,
    tabSelected: string
  ) => {
    this.setState({ selectedDepartment: selectedDepartment })
    if (tabSelected === COURSES_TAB) {
      this.setState({
        filteredCourses: this.filteredCoursesBasedOnCourseRunCriteria(
          selectedDepartment,
          this.state.allCoursesRetrieved
        )
      })
    } else {
      this.setState({
        filteredPrograms: this.filteredProgramsByDepartmentAndCriteria(
          selectedDepartment,
          this.state.allProgramsRetrieved
        )
      })
    }
  }

  /**
   * This is a comparision method used to sort an array of Course Runs
   * from earliest start date to latest start date.
   * @param {BaseCourseRun} courseRunA The first Course Run to compare.
   * @param {BaseCourseRun} courseRunB The second Course Run to compare.
   */
  compareCourseRunStartDates(
    courseRunA: BaseCourseRun,
    courseRunB: BaseCourseRun
  ) {
    if (moment(courseRunA.start_date).isBefore(courseRunB.start_date)) {
      return -1
    }
    if (moment(courseRunA.start_date).isAfter(courseRunB.start_date)) {
      return 1
    }
    // CourseRunA and CourseRunB share the same start date.
    return 0
  }

  /**
   * Returns the text to be displayed on a course catalog card's tag.
   * This text will either be "Start Anytime" or "Start Date: <most recent, future, start date for the course>".
   * If the Course has at least one associated Course Run which is not self-paced, and
   * Course Run start date is in the future, then return "Start Date: <most recent, future, start date for the course>".
   * If the Course has at least one associated Course Run which is not self-paced, and
   * Course Run start date is in the past, then return "Start Anytime".
   * If the course only has Course Runs which are self-paced, display "Start Anytime".
   * @param {CourseDetailWithRuns} course The course being evaluated.
   */
  renderCatalogCardTagForCourse(course: CourseDetailWithRuns) {
    const nonSelfPacedCourseRuns = course.courseruns.filter(
      courseRun => !courseRun.is_self_paced
    )
    if (nonSelfPacedCourseRuns.length > 0) {
      const futureStartDateCourseRuns = nonSelfPacedCourseRuns.filter(
        courseRun => moment(courseRun.start_date).isAfter(moment())
      )
      if (futureStartDateCourseRuns.length > 0) {
        const startDate = parseDateString(
          futureStartDateCourseRuns.sort(this.compareCourseRunStartDates)[0]
            .start_date
        )
        return `Start Date: ${formatPrettyDate(startDate)}`
      } else {
        return "Start Anytime"
      }
    } else {
      return "Start Anytime"
    }
  }

  /**
   * Returns a filtered array of Course Runs which are live, define a start date,
   * enrollment start date is before the current date and time, and
   * enrollment end date is not defined or is after the current date and time.
   * @param {Array<BaseCourseRun>} courseRuns The array of Course Runs apply the filter to.
   */
  validateCoursesCourseRuns(courseRuns: Array<BaseCourseRun>) {
    return courseRuns.filter(
      courseRun =>
        courseRun.live &&
        courseRun.start_date &&
        moment(courseRun?.enrollment_start).isBefore(moment()) &&
        (!courseRun.enrollment_end ||
          moment(courseRun.enrollment_end).isAfter(moment()))
    )
  }

  /**
   * Returns a filtered array of courses which have: an associated Department name matching the selectedDepartment
   * if the selectedDepartment does not equal "All Departments",
   * an associated page which is live, and at least 1 associated Course Run.
   * @param {Array<CourseDetailWithRuns>} courses An array of courses which will be filtered by Department.
   * @param {string} selectedDepartment The Department name used to compare against the courses in the array.
   */
  filteredCoursesBasedOnCourseRunCriteria(
    selectedDepartment: string,
    courses: Array<CourseDetailWithRuns>
  ) {
    return courses.filter(
      course =>
        (selectedDepartment === ALL_DEPARTMENTS ||
          course.departments
            .map(department => department.name)
            .includes(selectedDepartment)) &&
        course?.page?.live &&
        course.courseruns.length > 0 &&
        this.validateCoursesCourseRuns(course.courseruns).length > 0
    )
  }

  /**
   * Returns an array of Programs which have live = true, page.live = true, and a department name which
   * matches the currently selected department.
   * @param {Array<Program>} programs An array of Programs which will be filtered by Department and other criteria.
   * @param {string} selectedDepartment The Department name used to compare against the courses in the array.
   */
  filteredProgramsByDepartmentAndCriteria(
    selectedDepartment: string,
    programs: Array<Program>
  ) {
    return programs.filter(
      program =>
        (selectedDepartment === ALL_DEPARTMENTS ||
          program.departments
            .map(department => department.name)
            .includes(selectedDepartment)) &&
        program.live
    )
  }

  /**
   * Returns the number of courseRuns or programs based on the selected catalog tab.
   */
  renderNumberOfCatalogItems() {
    const { coursesIsLoading, programsIsLoading } = this.props
    if (this.state.tabSelected === COURSES_TAB && !coursesIsLoading) {
      return this.state.filteredCourses.length
    } else if (this.state.tabSelected === PROGRAMS_TAB && !programsIsLoading) {
      return this.state.filteredPrograms.length
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
          <img
            src={course?.page?.feature_image_src}
            key={course.id + course?.page?.feature_image_src}
            alt=""
          />
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
            <img
              src={program?.page?.feature_image_src}
              key={program.id + program?.page?.feature_image_src}
              alt=""
            />
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
   * Dynamically renders rows of cards in the catalog.  Each row can contain up to {ITEMS_PER_ROW} course or program cards.
   * @param {Array<CourseDetailWithRuns | Program>} itemsInCatalog The items associated with the currently selected catalog page.
   * @param {Function} renderCatalogCardFunction The card render function that will be used for each item on the current catalog page.
   */
  renderCatalogRows(
    itemsInCatalog: Array<CourseDetailWithRuns | Program>,
    renderCatalogCardFunction: Function
  ) {
    const numberOfItemsInEachRow = Math.min(
      itemsInCatalog.length,
      this.state.items_per_row
    )
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
    if (
      this.state.tabSelected === COURSES_TAB &&
      this.state.filteredCourses.length > 0
    ) {
      return this.renderCatalogRows(
        this.state.filteredCourses,
        this.renderCourseCatalogCard.bind(this)
      )
    } else if (this.state.tabSelected === PROGRAMS_TAB) {
      return this.renderCatalogRows(
        this.state.filteredPrograms,
        this.renderProgramCatalogCard.bind(this)
      )
    }
  }

  /**
   * Returns the rendering of the Department sidebar.
   */
  renderDepartmentSideBarList() {
    const departmentSideBarListItems = []
    this.state.departments.forEach(department =>
      departmentSideBarListItems.push(
        <li
          className={`sidebar-link ${
            this.state.selectedDepartment === department
              ? "department-selected-link"
              : "department-link"
          }`}
          key={this.state.tabSelected + department}
        >
          <button
            onClick={() =>
              this.changeSelectedDepartment(department, this.state.tabSelected)
            }
          >
            {department}
          </button>
        </li>
      )
    )
    return (
      <div id="department-sidebar">
        <ul id="department-sidebar-link-list">{departmentSideBarListItems}</ul>
      </div>
    )
  }

  render() {
    return (
      <div>
        <div id="catalog-page">
          <div id="catalog-title">
            {/* Hidden on small screens. */}
            <h2 className="d-none d-md-block">MITx Online Catalog</h2>
            {/* Visible on small screens. */}
            <div className="d-block d-md-none" id="mobile-catalog-title">
              <button
                onClick={() =>
                  this.toggleMobileFilterWindowExpanded(
                    !this.state.mobileFilterWindowExpanded
                  )
                }
              />
              <h2>Catalog</h2>
            </div>
          </div>
          <div id="course-catalog-navigation">
            {/* Only visible on small screen when mobileFilterWindowExpanded is true. */}
            <div
              className={`mobile-filter-overlay ${
                this.state.mobileFilterWindowExpanded
                  ? "slide-mobile-filter-overlay"
                  : "hidden-mobile-filter-overlay"
              }`}
            >
              {this.renderDepartmentSideBarList()}
            </div>
            <div className="container-fluid">
              <div className="row" id="tab-row">
                <div className="col catalog-animation d-sm-flex d-md-inline-flex">
                  <TransitionGroup>
                    <CSSTransition
                      key={this.state.tabSelected}
                      timeout={300}
                      classNames="messageout"
                    >
                      <div className="row" id="tabs">
                        <div
                          className={`col ${
                            this.state.tabSelected === COURSES_TAB
                              ? "selected-tab"
                              : "unselected-tab"
                          }`}
                        >
                          <button
                            onClick={() => this.changeSelectedTab(COURSES_TAB)}
                            tabIndex="0"
                          >
                            Courses
                          </button>
                        </div>
                        <div
                          className={`col ${
                            this.state.tabSelected === PROGRAMS_TAB
                              ? "selected-tab"
                              : "unselected-tab"
                          }`}
                        >
                          <button
                            onClick={() => this.changeSelectedTab(PROGRAMS_TAB)}
                          >
                            Programs
                          </button>
                        </div>
                      </div>
                    </CSSTransition>
                  </TransitionGroup>
                </div>
                <div className="col catalog-page-item-count">
                  <div className="catalog-count-animation">
                    <TransitionGroup id="count-animation-grid">
                      <CSSTransition
                        key={this.state.tabSelected}
                        timeout={300}
                        classNames="count"
                      >
                        <div>
                          {/* Hidden on small screens. */}
                          {/* Could add logic to display only "course" if only 1 course is showing. */}
                          {this.renderNumberOfCatalogItems()}{" "}
                          {this.state.tabSelected}
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
                    <div>{this.renderCatalog()}</div>
                  </CSSTransition>
                </TransitionGroup>
              </div>
              <div
                className={`${
                  this.state.isLoadingMoreItems ? "lds-ring" : "d-none"
                }`}
              >
                <div></div>
                <div></div>
                <div></div>
                <div></div>
              </div>
              {/* span is used to detect when the learner has scrolled to the bottom of the catalog page. */}
              <span ref={this.container}></span>
            </div>
          </div>
        </div>
      </div>
    )
  }
}

const getNextCoursePage = page =>
  requestAsync({
    ...coursesQuery(page),
    force: true
  })

const getNextProgramPage = page =>
  requestAsync({
    ...programsQuery(page),
    force: true
  })

const mapPropsToConfig = () => [coursesQuery(1), programsQuery(1)]

const mapDispatchToProps = {
  getNextCoursePage:  getNextCoursePage,
  getNextProgramPage: getNextProgramPage
}

const mapStateToProps = createStructuredSelector({
  courses:           coursesSelector,
  coursesNextPage:   coursesNextPageSelector,
  programs:          programsSelector,
  programsNextPage:  programsNextPageSelector,
  coursesIsLoading:  pathOr(true, ["queries", coursesQueryKey, "isPending"]),
  programsIsLoading: pathOr(true, ["queries", programsQueryKey, "isPending"])
})

export default compose(
  connect(mapStateToProps, mapDispatchToProps),
  connectRequest(mapPropsToConfig)
)(CatalogPage)
