import React from "react"
import { CSSTransition, TransitionGroup } from "react-transition-group"
import moment from "moment"
import { getStartDateText } from "../../lib/util"

import {
  coursesCountSelector,
  coursesSelector,
  coursesNextPageSelector,
  coursesQuery,
  coursesQueryKey
} from "../../lib/queries/catalogCourses"

import {
  programsCountSelector,
  programsSelector,
  programsNextPageSelector,
  programsQuery,
  programsQueryKey
} from "../../lib/queries/programs"

import {
  departmentsSelector,
  departmentsQuery,
  departmentsQueryKey
} from "../../lib/queries/departments"

import { createStructuredSelector } from "reselect"
import { compose } from "redux"
import { connect } from "react-redux"
import { requestAsync } from "redux-query"
import { connectRequest } from "redux-query-react"
import {mergeDeepRight, pathOr} from "ramda"
import CourseLoader from "../../components/CourseLoader"

type Props = {
  coursesIsLoading: ?boolean,
  programsIsLoading: ?boolean,
  courses: ?Array<CourseDetailWithRuns>,
  programs: ?Array<Program>,
  forceRequest: () => Promise<*>,
  coursesNextPage: ?string,
  programsNextPage: ?string,
  programsCount: number,
  coursesCount: number,
  departments: ?Array<Department>
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
    filterProgramsCalled:       false,
    filterCoursesCalled:        false,
    filteredDepartments:        [],
    filterDepartmentsCalled:    false,
    selectedDepartment:         ALL_DEPARTMENTS,
    mobileFilterWindowExpanded: false,
    items_per_row:              3,
    courseQueryPage:            1,
    programQueryPage:           1,
    isLoadingMoreItems:         false,
    queryIDListString:          ""
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
  }

  componentDidMount() {}

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
          const response = await getNextCoursePage(
            this.state.courseQueryPage,
            this.state.queryIDListString
          )
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
        if (programsNextPage && !this.state.isLoadingMoreItems) {
          this.setState({ isLoadingMoreItems: true })
          const response = await getNextProgramPage(
            this.state.programQueryPage + 1,
            this.state.queryIDListString
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
   * Updates the filteredCourses state variable
   * once coursesIsLoading is false..  Adds an observer to detect when
   * the learner has scrolled to the bottom of the visible catalog items.
   * Updates the filteredDepartments state variable once departmentsIsLoading
   * is false.
   */
  componentDidUpdate = prevState => {
    const {
      courses,
      coursesIsLoading,
      programsIsLoading,
      programs,
      departments,
      departmentsIsLoading
    } = this.props
    if (!departmentsIsLoading && !this.state.filterDepartmentsCalled) {
      this.setState({filterDepartmentsCalled: true})
      this.setState({
        filteredDepartments: this.filterDepartmentsByTabName(
          this.state.tabSelected
        )
      })
    }
    if (!departmentsIsLoading && departments.length > 0) {
      if (!coursesIsLoading && this.state.filteredCoursesCalled) {
        if (this.state.selectedDepartment !== prevState.selectedDepartment) {
          this.setState({courseQueryPage: 1})
          this.setState({queryIDListString: ""})
          this.setState({filteredCoursesCalled: false})
        }
      }
      if (!coursesIsLoading && !this.state.filterCoursesCalled) {
        this.setState({filterCoursesCalled: true})
        this.setState({allCoursesRetrieved: courses})
        const filteredCourses = this.filteredCoursesBasedOnCourseRunCriteria(
          this.state.selectedDepartment,
          courses
        )
        this.setState({filteredCourses: filteredCourses})
        if (this.state.selectedDepartment !== ALL_DEPARTMENTS && this.state.selectedDepartment !== "") {
          // If the number of courses is equal to the number of expected courses on filter, no need to grab more data
          if (this.state.selectedDepartment !== ALL_DEPARTMENTS) {
            const newDepartment = departments.find(
              department => department.name === this.state.selectedDepartment
            )
            if (filteredCourses.length !== newDepartment.course_ids.length) {
              const remainingIDs = newDepartment.course_ids.filter(
                id => !this.state.queryIDListString.includes(id)
              )
              this.setState({courseQueryPage: 0})
              this.setState({queryIDListString: remainingIDs.toString()})
              console.log(this.state.queryIDListString)
              this.props.getNextCoursePage(this.state.courseQueryPage, this.state.queryIDListString)
            }
          }
        }
        this.io = new window.IntersectionObserver(
          this.bottomOfLoadedCatalogCallback,
          {threshold: 1.0}
        )
        this.io.observe(this.container.current)
      }
      if (!programsIsLoading && !this.state.filterProgramsCalled) {
        this.setState({filterProgramsCalled: true})
        this.setState({allProgramsRetrieved: programs})
        const filteredPrograms = this.filteredProgramsByDepartmentAndCriteria(
          this.state.selectedDepartment,
          programs
        )
        this.setState({
          filteredPrograms: filteredPrograms
        })
        if (this.state.selectedDepartment !== ALL_DEPARTMENTS) {
          const newDepartment = departments.find(
            department => department.name === this.state.selectedDepartment
          )
          if (filteredPrograms.length !== newDepartment.program_ids.length) {
            const remainingIDs = newDepartment.program_ids.filter(
              id => !this.state.queryIDListString.includes(id)
            )
            this.setState({programQueryPage: 1})
            this.setState({queryIDListString: remainingIDs.toString()})
            this.props.getNextProgramPage(this.state.programQueryPage, this.state.queryIDListString)
          }
          // Detect when the bottom of the catalog page has been reached and display more catalog items.
          this.io = new window.IntersectionObserver(
            this.bottomOfLoadedCatalogCallback,
            {threshold: 1.0}
          )
          this.io.observe(this.container.current)
        }
      }
    }
  }

  /**
   * Returns an array of departments names which have one or more course(s) or program(s)
   * related to them depending on the currently selected tab.
   * @param {string} selectedTabName the name of the currently selected tab.
   */
  filterDepartmentsByTabName(selectedTabName: string) {
    if (!this.props.departmentsIsLoading) {
      const { departments } = this.props
      if (selectedTabName === COURSES_TAB) {
        return [
          ...new Set([
            ALL_DEPARTMENTS,
            ...departments.flatMap(department =>
              department.course_ids.length > 0 ? department.name : []
            )
          ])
        ]
      } else {
        return [
          ...new Set([
            ALL_DEPARTMENTS,
            ...departments.flatMap(department =>
              department.program_ids.length > 0 ? department.name : []
            )
          ])
        ]
      }
    }
  }

  /**
   * Updates this.state.selectedDepartment to {ALL_DEPARTMENTS},
   * updates this.state.tabSelected to the parameter,
   * updates this.state.filteredDepartments
   * names from the catalog items in the selected tab,
   * updates this.state.filteredPrograms to equal the programs
   * which meet the criteria to be displayed in the catalog.
   * @param {string} selectTabName The name of the tab that was selected.
   */
  changeSelectedTab = (selectTabName: string) => {
    this.setState({ tabSelected: selectTabName })

    if (selectTabName === PROGRAMS_TAB) {
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
      }
    }
    this.setState({
      filteredDepartments: this.filterDepartmentsByTabName(selectTabName)
    })
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
  changeSelectedDepartment = (selectedDepartment: string) => {
    console.log("this fires")
    const {departments} = this.props
    if (selectedDepartment === ALL_DEPARTMENTS) {
      this.setState({courseQueryPage: 1})
      this.setState({programQueryPage: 1})
      this.setState({queryIDListString: ""})
    }
    this.setState({ selectedDepartment: selectedDepartment })
    const filteredCourses = this.filteredCoursesBasedOnCourseRunCriteria(selectedDepartment, this.state.allCoursesRetrieved)
    this.setState({
      filteredCourses: filteredCourses
    })
    this.setState({
      filteredPrograms: this.filteredProgramsByDepartmentAndCriteria(
        selectedDepartment,
        this.state.allProgramsRetrieved
      )
    })
    this.toggleMobileFilterWindowExpanded(false)
    if (selectedDepartment !== ALL_DEPARTMENTS) {
      console.log(selectedDepartment, "selectedDepartment")
      const newDepartment = departments.find(
        department => department.name === selectedDepartment
      )
      if (filteredCourses.length !== newDepartment.course_ids.length) {
        console.log("we don't have enoguh")
        const remainingIDs = newDepartment.course_ids.filter(
          id => !this.state.queryIDListString.includes(id)
        )
        this.setState({courseQueryPage: 0})
        this.setState({queryIDListString: remainingIDs.toString()})
        console.log("getnextcoursepage")
        this.setState({isLoadingMoreItems: true})
        this.props.getNextCoursePage(1, remainingIDs.toString()).then(
          response => {
            this.setState({isLoadingMoreItems: false})
            const allCourses = [...response.body.results, ...this.state.allCoursesRetrieved]
            this.setState({allCoursesRetrieved: allCourses})
            this.setState({filterProgramsCalled: true})
            const filteredCourses = this.filteredCoursesBasedOnCourseRunCriteria(
              this.state.selectedDepartment,
              allCourses
            )
            this.setState({filteredCourses: filteredCourses})
          }
        )
      }
    }
  }

  /**
   * Returns a filtered array of Course Runs which are live and:
   * - Have a start_date before the current date and time
   * - Have an enrollment_start_date that is before the current date and time
   * - Has an enrollment_end_date that is not defined or is after the current date and time.
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
    console.log(courses, "whyyyy")
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
   * Returns an array of Programs which have page.live = true and a department name which
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
        selectedDepartment === ALL_DEPARTMENTS ||
        program.departments
          .map(department => department)
          .includes(selectedDepartment)
    )
  }

  /**
   * Returns the number of courseRuns or programs based on the selected catalog tab.
   */
  renderNumberOfCatalogCourses() {
    const { coursesCount, departments } = this.props
    if (this.state.selectedDepartment === ALL_DEPARTMENTS) {
      return coursesCount
    } else if (this.state.selectedDepartment !== ALL_DEPARTMENTS) {
      return departments.find(
        department => department.name === this.state.selectedDepartment
      ).course_ids.length
    }
  }

  renderNumberOfCatalogPrograms() {
    const { programsCount, departments } = this.props
    if (this.state.selectedDepartment === ALL_DEPARTMENTS) {
      return programsCount
    } else if (this.state.selectedDepartment !== ALL_DEPARTMENTS) {
      return departments.find(
        department => department.name === this.state.selectedDepartment
      ).program_ids.length
    } else return 0
  }

  /**
   * Renders a single course catalog card.
   * @param {CourseDetailWithRuns} course The course instance used to populate the card.
   */
  renderCourseCatalogCard(course: CourseDetailWithRuns) {
    return (
      <li key={`course-card-${course.id}`}>
        <a href={course.page.page_url} key={course.id}>
          <div className="col catalog-item">
            <img
              src={course?.page?.feature_image_src}
              key={course.id + course?.page?.feature_image_src}
              alt=""
            />
            <div className="catalog-item-description">
              <div className="start-date-description">
                {getStartDateText(course)}
              </div>
              <div className="item-title">{course.title}</div>
            </div>
          </div>
        </a>
      </li>
    )
  }

  /**
   * Renders a single program catalog card.
   * @param {Program} program The program instance used to populate the card.
   */
  renderProgramCatalogCard(program: Program) {
    return (
      <li key={`program-card-${program.id}`}>
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
      </li>
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
    return (
      <ul id="catalog-grid">
        {itemsInCatalog.map(x => renderCatalogCardFunction(x))}
      </ul>
    )
  }

  /**
   * Renders the entire catalog of course or program cards based on the catalog tab selected.
   */
  renderCatalog() {
    const { filteredCourses, filteredPrograms, tabSelected } = this.state

    if (
      filteredCourses.length === 0 &&
      (this.props.coursesIsLoading || this.props.programsIsLoading)
    ) {
      return courseLoaderGrid
    }
    if (tabSelected === COURSES_TAB && filteredCourses.length > 0) {
      return this.renderCatalogRows(
        filteredCourses,
        this.renderCourseCatalogCard.bind(this)
      )
    } else if (tabSelected === PROGRAMS_TAB) {
      return this.renderCatalogRows(
        filteredPrograms,
        this.renderProgramCatalogCard.bind(this)
      )
    }
  }

  /**
   * Returns the rendering of the Department sidebar.
   */
  renderDepartmentSideBarList() {
    const departmentSideBarListItems = []
    this.state.filteredDepartments.forEach(department =>
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
      <nav
        className="sticky-top"
        id="department-sidebar"
        aria-label="department filters"
      >
        <ul id="department-sidebar-link-list">{departmentSideBarListItems}</ul>
      </nav>
    )
  }

  render() {
    return (
      <div>
        <div id="catalog-page">
          <div id="catalog-title">
            {/* Hidden on small screens. */}
            <h1 className="d-none d-md-block">MITx Online Catalog</h1>
            {/* Visible on small screens. */}
            <div className="d-block d-md-none" id="mobile-catalog-title">
              <button
                onClick={() =>
                  this.toggleMobileFilterWindowExpanded(
                    !this.state.mobileFilterWindowExpanded
                  )
                }
              />
              <h1>
                Catalog
                <small>
                  {this.state.selectedDepartment === ALL_DEPARTMENTS
                    ? ""
                    : this.state.selectedDepartment}
                </small>
              </h1>
            </div>
          </div>
          <div className="container">
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
                    <TransitionGroup id="tab-animation-grid">
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
                              onClick={() =>
                                this.changeSelectedTab(COURSES_TAB)
                              }
                              tabIndex="0"
                            >
                              Courses{" "}
                              <div className="product-number d-inline-block d-sm-none">
                                ({this.renderNumberOfCatalogCourses()})
                              </div>
                            </button>
                          </div>
                          <div
                            className={`col ${
                              this.state.tabSelected === PROGRAMS_TAB
                                ? "selected-tab"
                                : "unselected-tab"
                            } ${
                              this.props.programsCount ? "" : "display-none"
                            }`}
                          >
                            <button
                              onClick={() =>
                                this.changeSelectedTab(PROGRAMS_TAB)
                              }
                            >
                              Programs{" "}
                              <div className="product-number d-inline-block d-sm-none">
                                ({this.renderNumberOfCatalogPrograms()})
                              </div>
                            </button>
                          </div>
                        </div>
                      </CSSTransition>
                    </TransitionGroup>
                  </div>
                  <div className="col catalog-page-item-count d-none d-sm-block">
                    <div
                      className="catalog-count-animation"
                      role="status"
                      aria-atomic="true"
                    >
                      <TransitionGroup id="count-animation-grid">
                        <CSSTransition
                          key={this.state.tabSelected}
                          timeout={300}
                          classNames="count"
                        >
                          <h2>
                            {/* Hidden on small screens. */}
                            {/* Could add logic to display only "course" if only 1 course is showing. */}
                            {this.state.tabSelected === PROGRAMS_TAB
                              ? this.renderNumberOfCatalogPrograms()
                              : this.renderNumberOfCatalogCourses()}{" "}
                            {this.state.tabSelected}
                          </h2>
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
                {this.state.isLoadingMoreItems ? courseLoaderGrid : null}
                {/* span is used to detect when the learner has scrolled to the bottom of the catalog page. */}
                <span ref={this.container}></span>
              </div>
            </div>
          </div>
        </div>
      </div>
    )
  }
}
const courseLoaderGrid = (
  <div id="catalog-grid">
    <CourseLoader />
    <CourseLoader />
    <CourseLoader />
  </div>
)

const getNextCoursePage = (page, ids) =>
  requestAsync({
    ...coursesQuery(page, ids),
    force: true
  })

const getNextProgramPage = (page, ids) =>
  requestAsync({
    ...programsQuery(page, ids),
    force: true
  })

const mapPropsToConfig = () => [
  coursesQuery(1, ""),
  programsQuery(1, ""),
  departmentsQuery(1, "")
]

const mapDispatchToProps = {
  getNextCoursePage:  getNextCoursePage,
  getNextProgramPage: getNextProgramPage
}

const mapStateToProps = createStructuredSelector({
  courses:              coursesSelector,
  coursesCount:         coursesCountSelector,
  coursesNextPage:      coursesNextPageSelector,
  programs:             programsSelector,
  programsCount:        programsCountSelector,
  programsNextPage:     programsNextPageSelector,
  departments:          departmentsSelector,
  coursesIsLoading:     pathOr(true, ["queries", coursesQueryKey, "isPending"]),
  programsIsLoading:    pathOr(true, ["queries", programsQueryKey, "isPending"]),
  departmentsIsLoading: pathOr(true, [
    "queries",
    departmentsQueryKey,
    "isPending"
  ])
})

export default compose(
  connect(mapStateToProps, mapDispatchToProps),
  connectRequest(mapPropsToConfig)
)(CatalogPage)
