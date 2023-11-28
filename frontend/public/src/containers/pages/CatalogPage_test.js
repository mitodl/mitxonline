// @flow
/* global SETTINGS: false */
import { expect } from "chai"
import moment from "moment-timezone"
import IntegrationTestHelper from "../../util/integration_test_helper"
import CatalogPage, { CatalogPage as InnerCatalogPage } from "./CatalogPage"
import sinon from "sinon"

const displayedCourse = {
  id:          2,
  title:       "E2E Test Course",
  readable_id: "course-v1:edX+E2E-101",
  courseruns:  [
    {
      title:            "E2E Test Course",
      start_date:       moment(),
      end_date:         moment().add(2, "M"),
      enrollment_start: moment(),
      enrollment_end:   null,
      expiration_date:  null,
      courseware_url:
        "http://edx.odl.local:18000/courses/course-v1:edX+E2E-101+course/",
      courseware_id:    "course-v1:edX+E2E-101+course",
      upgrade_deadline: null,
      is_upgradable:    true,
      is_self_paced:    false,
      run_tag:          "course",
      id:               2,
      live:             true,
      products:         [
        {
          id:                     1,
          price:                  "999.00",
          description:            "course-v1:edX+E2E-101+course",
          is_active:              true,
          product_flexible_price: {
            amount:          null,
            automatic:       false,
            discount_type:   null,
            redemption_type: null,
            max_redemptions: null,
            discount_code:   "",
            payment_type:    null,
            activation_date: null,
            expiration_date: null
          }
        }
      ],
      page: {
        feature_image_src:             "/static/images/mit-dome.png",
        page_url:                      "/courses/course-v1:edX+E2E-101/",
        financial_assistance_form_url: "",
        description:                   "E2E Test Course",
        current_price:                 999.0,
        instructors:                   [],
        live:                          true
      },
      approved_flexible_price_exists: false
    }
  ],
  next_run_id: 2,
  departments: [
    {
      name: "Science"
    }
  ],
  page: {
    feature_image_src:             "/static/images/mit-dome.png",
    page_url:                      "/courses/course-v1:edX+E2E-101/",
    financial_assistance_form_url: "",
    description:                   "E2E Test Course",
    current_price:                 999.0,
    instructors:                   [],
    live:                          true
  }
}

const displayedProgram = {
  title:        "P2",
  readable_id:  "P2",
  id:           2,
  requirements: {
    required:  [1],
    electives: []
  },
  courses:  [1],
  req_tree: [
    {
      data: {
        node_type:      "program_root",
        operator:       null,
        operator_value: null,
        program:        2,
        course:         null,
        title:          "",
        elective_flag:  false
      },
      id:       4,
      children: [
        {
          data: {
            node_type:      "operator",
            operator:       "all_of",
            operator_value: null,
            program:        2,
            course:         null,
            title:          "Required Courses",
            elective_flag:  false
          },
          id:       5,
          children: [
            {
              data: {
                node_type:      "course",
                operator:       null,
                operator_value: null,
                program:        2,
                course:         1,
                title:          null,
                elective_flag:  false
              },
              id: 6
            }
          ]
        }
      ]
    }
  ],
  page: {
    feature_image_src:
      "http://mitxonline.odl.local:8013/static/images/mit-dome.png"
  },
  program_type: "Series",
  departments:  ["Science"],
  live:         true
}

describe("CatalogPage", function() {
  const mockIntersectionObserver = class {
    constructor() {}
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  let helper, courses, programs, renderPage

  this.timeout(50000)

  beforeEach(() => {
    // Mock the intersection observer.
    helper = new IntegrationTestHelper()
    window.IntersectionObserver = mockIntersectionObserver

    renderPage = helper.configureHOCRenderer(CatalogPage, InnerCatalogPage)

    SETTINGS.features = {
      "mitxonline-new-product-page": true
    }
  })

  afterEach(() => {
    helper.cleanup()
  })

  it("default state is set when catalog renders", async () => {
    courses = [displayedCourse]
    const { inner } = await renderPage(
      {
        queries: {
          courses: {
            isPending: false,
            status:    200
          }
        },
        entities: {
          courses: {
            count:   1,
            results: courses
          }
        }
      },
      {}
    )
    inner.instance().componentDidUpdate({}, {})
    expect(inner.state().selectedDepartment).equals("All Departments")
    expect(inner.state().tabSelected).equals("courses")
    expect(JSON.stringify(inner.state().filteredCourses)).equals(
      JSON.stringify(courses)
    )
    expect(JSON.stringify(inner.state().allCoursesRetrieved)).equals(
      JSON.stringify(courses)
    )
    expect(inner.instance().renderNumberOfCatalogItems()).equals(1)
  })

  it("updates state from changeSelectedTab when selecting program tab", async () => {
    courses = [displayedCourse]
    programs = Array(5).fill(displayedProgram)
    const { inner } = await renderPage(
      {
        queries: {
          courses: {
            isPending: false,
            status:    200
          },
          programs: {
            isPending: false,
            status:    200
          },
          departments: {
            isPending: false,
            status:    200
          }
        },
        entities: {
          courses: {
            count:   1,
            results: courses
          },
          programs: {
            count:   5,
            results: programs
          },
          departments: [
            {
              name:     "History",
              courses:  0,
              programs: 5
            },
            {
              name:     "Science",
              courses:  1,
              programs: 0
            }
          ]
        }
      },
      {}
    )
    inner.instance().componentDidUpdate({}, {})
    inner.instance().changeSelectedTab("programs")
    expect(inner.state().selectedDepartment).equals("All Departments")
    expect(inner.state().tabSelected).equals("programs")
    expect(JSON.stringify(inner.state().filteredPrograms)).equals(
      JSON.stringify(programs)
    )
    expect(JSON.stringify(inner.state().allProgramsRetrieved)).equals(
      JSON.stringify(programs)
    )
    expect(inner.instance().renderNumberOfCatalogItems()).equals(5)
  })

  it("renders catalog department filter for courses and programs tabs", async () => {
    const { inner } = await renderPage(
      {
        queries: {
          departments: {
            isPending: false,
            status:    200
          }
        },
        entities: {
          departments: [
            {
              name:     "department1",
              courses:  1,
              programs: 0
            },
            {
              name:     "department2",
              courses:  1,
              programs: 1
            },
            {
              name:     "department3",
              courses:  0,
              programs: 1
            },
            {
              name:     "department4",
              courses:  0,
              programs: 0
            }
          ]
        }
      },
      {}
    )
    let filteredDepartments = inner
      .instance()
      .filterDepartmentsByTabName("courses")
    expect(JSON.stringify(filteredDepartments)).equals(
      JSON.stringify(["All Departments", "department1", "department2"])
    )
    filteredDepartments = inner
      .instance()
      .filterDepartmentsByTabName("programs")
    expect(JSON.stringify(filteredDepartments)).equals(
      JSON.stringify(["All Departments", "department2", "department3"])
    )
  })

  it("renders catalog courses when filtered by department", async () => {
    const course1 = JSON.parse(JSON.stringify(displayedCourse))
    course1.departments = [{ name: "Math" }]
    const course2 = JSON.parse(JSON.stringify(displayedCourse))
    course2.departments = [{ name: "Science" }]
    const course3 = JSON.parse(JSON.stringify(displayedCourse))
    course3.departments = [{ name: "Science" }]
    courses = [course1, course2, course3]
    const { inner } = await renderPage()
    let coursesFilteredByCriteriaAndDepartment = inner
      .instance()
      .filteredCoursesBasedOnCourseRunCriteria("Math", courses)
    expect(coursesFilteredByCriteriaAndDepartment.length).equals(1)
    coursesFilteredByCriteriaAndDepartment = inner
      .instance()
      .filteredCoursesBasedOnCourseRunCriteria("Science", courses)
    expect(coursesFilteredByCriteriaAndDepartment.length).equals(2)
    coursesFilteredByCriteriaAndDepartment = inner
      .instance()
      .filteredCoursesBasedOnCourseRunCriteria("All Departments", courses)
    expect(coursesFilteredByCriteriaAndDepartment.length).equals(3)
  })

  it("renders no catalog courses if the course's pages are not live", async () => {
    const course = JSON.parse(JSON.stringify(displayedCourse))
    course.page.live = false
    const { inner } = await renderPage()
    const coursesFilteredByCriteriaAndDepartment = inner
      .instance()
      .filteredCoursesBasedOnCourseRunCriteria("All Departments", [course])
    expect(coursesFilteredByCriteriaAndDepartment.length).equals(0)
  })

  it("renders no catalog courses if the course has no page", async () => {
    const course = JSON.parse(JSON.stringify(displayedCourse))
    delete course.page
    const { inner } = await renderPage()
    const coursesFilteredByCriteriaAndDepartment = inner
      .instance()
      .filteredCoursesBasedOnCourseRunCriteria("All Departments", [course])
    expect(coursesFilteredByCriteriaAndDepartment.length).equals(0)
  })

  it("renders no catalog courses if the course has no associated course runs", async () => {
    const course = JSON.parse(JSON.stringify(displayedCourse))
    course.courseruns = []
    const { inner } = await renderPage()
    const coursesFilteredByCriteriaAndDepartment = inner
      .instance()
      .filteredCoursesBasedOnCourseRunCriteria("All Departments", [course])
    expect(coursesFilteredByCriteriaAndDepartment.length).equals(0)
  })

  it("renders catalog programs when filtered by department", async () => {
    const program1 = JSON.parse(JSON.stringify(displayedProgram))
    program1.departments = ["Math"]
    const program2 = JSON.parse(JSON.stringify(displayedProgram))
    program2.departments = ["History"]
    const program3 = JSON.parse(JSON.stringify(displayedProgram))
    program3.departments = ["History"]
    const { inner } = await renderPage()
    programs = [program1, program2, program3]
    let programsFilteredByCriteriaAndDepartment = inner
      .instance()
      .filteredProgramsByDepartmentAndCriteria("Math", programs)
    expect(programsFilteredByCriteriaAndDepartment.length).equals(1)
    programsFilteredByCriteriaAndDepartment = inner
      .instance()
      .filteredProgramsByDepartmentAndCriteria("History", programs)
    expect(programsFilteredByCriteriaAndDepartment.length).equals(2)
    programsFilteredByCriteriaAndDepartment = inner
      .instance()
      .filteredProgramsByDepartmentAndCriteria("All Departments", programs)
    expect(programsFilteredByCriteriaAndDepartment.length).equals(3)
  })

  it("renders no catalog courses if the course's associated course run is not live", async () => {
    const courseRuns = JSON.parse(JSON.stringify(displayedCourse.courseruns))
    const { inner } = await renderPage()
    let coursesFilteredByCriteriaAndDepartment = inner
      .instance()
      .validateCoursesCourseRuns(courseRuns)
    expect(coursesFilteredByCriteriaAndDepartment.length).equals(1)
    courseRuns[0].live = false
    coursesFilteredByCriteriaAndDepartment = inner
      .instance()
      .validateCoursesCourseRuns(courseRuns)
    expect(coursesFilteredByCriteriaAndDepartment.length).equals(0)
  })

  it("renders no catalog courses if the course's associated course run has no start date", async () => {
    const courseRuns = JSON.parse(JSON.stringify(displayedCourse.courseruns))
    const { inner } = await renderPage()
    let coursesFilteredByCriteriaAndDepartment = inner
      .instance()
      .validateCoursesCourseRuns(courseRuns)
    expect(coursesFilteredByCriteriaAndDepartment.length).equals(1)
    delete courseRuns[0].start_date
    coursesFilteredByCriteriaAndDepartment = inner
      .instance()
      .validateCoursesCourseRuns(courseRuns)
    expect(coursesFilteredByCriteriaAndDepartment.length).equals(0)
  })

  it("renders no catalog courses if the course's associated course run has no enrollment start date", async () => {
    const courseRuns = JSON.parse(JSON.stringify(displayedCourse.courseruns))
    const { inner } = await renderPage()
    let coursesFilteredByCriteriaAndDepartment = inner
      .instance()
      .validateCoursesCourseRuns(courseRuns)
    expect(coursesFilteredByCriteriaAndDepartment.length).equals(1)
    delete courseRuns[0].enrollment_start
    coursesFilteredByCriteriaAndDepartment = inner
      .instance()
      .validateCoursesCourseRuns(courseRuns)
    expect(coursesFilteredByCriteriaAndDepartment.length).equals(0)
  })

  it("renders no catalog courses if the course's associated course run has an enrollment start date in the future", async () => {
    const courseRuns = JSON.parse(JSON.stringify(displayedCourse.courseruns))
    const { inner } = await renderPage()
    let coursesFilteredByCriteriaAndDepartment = inner
      .instance()
      .validateCoursesCourseRuns(courseRuns)
    expect(coursesFilteredByCriteriaAndDepartment.length).equals(1)
    courseRuns[0].enrollment_start = moment().add(2, "M")
    coursesFilteredByCriteriaAndDepartment = inner
      .instance()
      .validateCoursesCourseRuns(courseRuns)
    expect(coursesFilteredByCriteriaAndDepartment.length).equals(0)
  })

  it("renders no catalog courses if the course's associated course run has an enrollment end date in the past", async () => {
    const courseRuns = JSON.parse(JSON.stringify(displayedCourse.courseruns))
    const { inner } = await renderPage()
    let coursesFilteredByCriteriaAndDepartment = inner
      .instance()
      .validateCoursesCourseRuns(courseRuns)
    expect(coursesFilteredByCriteriaAndDepartment.length).equals(1)
    courseRuns[0].enrollment_end = moment().subtract(2, "M")
    coursesFilteredByCriteriaAndDepartment = inner
      .instance()
      .validateCoursesCourseRuns(courseRuns)
    expect(coursesFilteredByCriteriaAndDepartment.length).equals(0)
  })

  it("renders catalog courses if the course's associated course run has no enrollment end date", async () => {
    const courseRuns = JSON.parse(JSON.stringify(displayedCourse.courseruns))
    const { inner } = await renderPage()
    let coursesFilteredByCriteriaAndDepartment = inner
      .instance()
      .validateCoursesCourseRuns(courseRuns)
    expect(coursesFilteredByCriteriaAndDepartment.length).equals(1)
    delete courseRuns[0].enrollment_end
    coursesFilteredByCriteriaAndDepartment = inner
      .instance()
      .validateCoursesCourseRuns(courseRuns)
    expect(coursesFilteredByCriteriaAndDepartment.length).equals(1)
  })

  it("renders catalog courses if the course's associated course run has an enrollment end date in the future", async () => {
    const courseRuns = JSON.parse(JSON.stringify(displayedCourse.courseruns))
    const { inner } = await renderPage()
    let coursesFilteredByCriteriaAndDepartment = inner
      .instance()
      .validateCoursesCourseRuns(courseRuns)
    expect(coursesFilteredByCriteriaAndDepartment.length).equals(1)
    courseRuns[0].enrollment_end = moment().add(2, "M")
    coursesFilteredByCriteriaAndDepartment = inner
      .instance()
      .validateCoursesCourseRuns(courseRuns)
    expect(coursesFilteredByCriteriaAndDepartment.length).equals(1)
  })

  it("renders catalog courses if the course's associated course run has an enrollment start date in the past", async () => {
    const courseRuns = JSON.parse(JSON.stringify(displayedCourse.courseruns))
    const { inner } = await renderPage()
    let coursesFilteredByCriteriaAndDepartment = inner
      .instance()
      .validateCoursesCourseRuns(courseRuns)
    expect(coursesFilteredByCriteriaAndDepartment.length).equals(1)
    courseRuns[0].enrollment_start = moment().subtract(2, "M")
    coursesFilteredByCriteriaAndDepartment = inner
      .instance()
      .validateCoursesCourseRuns(courseRuns)
    expect(coursesFilteredByCriteriaAndDepartment.length).equals(1)
  })

  it("renders catalog courses based on selected department", async () => {
    const course1 = JSON.parse(JSON.stringify(displayedCourse))
    course1.departments = [{ name: "Math" }]
    const course2 = JSON.parse(JSON.stringify(displayedCourse))
    course2.departments = [{ name: "Math" }, { name: "History" }]
    const course3 = JSON.parse(JSON.stringify(displayedCourse))
    course3.departments = [{ name: "Math" }, { name: "History" }]
    courses = [course1, course2, course3]
    const { inner } = await renderPage(
      {
        queries: {
          courses: {
            isPending: false,
            status:    200
          },
          programs: {
            isPending: false,
            status:    200
          },
          departments: {
            isPending: false,
            status:    200
          }
        },
        entities: {
          courses: {
            count:   3,
            results: courses
          },
          programs: {
            results: [displayedProgram]
          },
          departments: [
            {
              name:     "History",
              courses:  2,
              programs: 1
            },
            {
              name:     "Math",
              courses:  3,
              programs: 0
            },
            {
              name:     "department4",
              courses:  0,
              programs: 0
            }
          ]
        }
      },
      {}
    )
    inner.instance().componentDidUpdate({}, {})
    // Default selected department is All Departments.
    expect(inner.state().selectedDepartment).equals("All Departments")
    // Default tab selected is courses.
    expect(inner.state().tabSelected).equals("courses")
    // All of the courses should be visible.
    expect(JSON.stringify(inner.state().filteredCourses)).equals(
      JSON.stringify(courses)
    )
    expect(JSON.stringify(inner.state().allCoursesRetrieved)).equals(
      JSON.stringify(courses)
    )
    // Number of catalog items should match the number of visible courses.
    expect(inner.instance().renderNumberOfCatalogItems()).equals(3)

    // Select a department to filter by.
    inner.instance().changeSelectedDepartment("History", "courses")
    // Confirm the state updated to reflect the selected department.
    expect(inner.state().selectedDepartment).equals("History")
    // Confirm the number of catalog items updated to reflect the items filtered by department.
    expect(inner.instance().renderNumberOfCatalogItems()).equals(2)
    // Confirm the courses filtered are those which have a department name matching the selected department.
    expect(JSON.stringify(inner.state().filteredCourses)).equals(
      JSON.stringify([course2, course3])
    )
    expect(JSON.stringify(inner.state().allCoursesRetrieved)).equals(
      JSON.stringify(courses)
    )

    // Change to the programs tab.
    inner.instance().changeSelectedTab("programs")
    // Confirm that the selected department is the same as before.
    expect(inner.state().selectedDepartment).equals("History")

    // Change back to the courses tab.
    inner.instance().changeSelectedTab("courses")
    // Confirm the courses filtered are those which have a department name matching the selected department.
    expect(JSON.stringify(inner.state().filteredCourses)).equals(
      JSON.stringify([course2, course3])
    )
  })

  it("load more at the bottom of the courses catalog page, all departments filter", async () => {
    courses = [displayedCourse]
    programs = [displayedProgram]
    const { inner } = await renderPage(
      {
        queries: {
          courses: {
            isPending: false,
            status:    200
          },
          programs: {
            isPending: false,
            status:    200
          }
        },
        entities: {
          courses: {
            count:   2,
            results: courses,
            next:    "http://fake.com/api/courses/?page=2"
          },
          programs: {
            count:   2,
            results: programs
          }
        }
      },
      {}
    )
    inner.instance().componentDidUpdate({}, {})
    expect(inner.state().selectedDepartment).equals("All Departments")
    expect(inner.state().tabSelected).equals("courses")
    expect(JSON.stringify(inner.state().filteredCourses)).equals(
      JSON.stringify(courses)
    )
    expect(JSON.stringify(inner.state().allCoursesRetrieved)).equals(
      JSON.stringify(courses)
    )
    // one shows visually, but the total is 2
    expect(inner.instance().renderNumberOfCatalogItems()).equals(2)
    expect(inner.state().courseQueryPage).equals(1)

    // Mock the second page of course API results.
    helper.handleRequestStub.returns({
      body: {
        next:    null,
        results: courses
      }
    })

    // Simulate the user reaching the bottom of the catalog page.
    const entry = [{ isIntersecting: true }]
    await inner.instance().bottomOfLoadedCatalogCallback(entry)

    sinon.assert.calledWith(
      helper.handleRequestStub,
      "/api/v2/courses/?page=2&live=true&page__live=true&courserun_is_enrollable=true",
      "GET"
    )

    // Should expect 2 courses to be visually displayed in the catalog now. Total count should stay 2.
    expect(inner.state().courseQueryPage).equals(2)
    expect(JSON.stringify(inner.state().allCoursesRetrieved)).equals(
      JSON.stringify([displayedCourse, displayedCourse])
    )
    expect(JSON.stringify(inner.state().filteredCourses)).equals(
      JSON.stringify([displayedCourse, displayedCourse])
    )
    expect(inner.instance().renderNumberOfCatalogItems()).equals(2)
  })

  it("do not load more at the bottom of the courses catalog page if next page is null", async () => {
    courses = [displayedCourse]
    programs = [displayedProgram]
    const { inner } = await renderPage(
      {
        queries: {
          courses: {
            isPending: false,
            status:    200
          },
          programs: {
            isPending: false,
            status:    200
          }
        },
        entities: {
          courses: {
            count:   1,
            results: courses,
            next:    null
          },
          programs: {
            count:   1,
            results: programs
          }
        }
      },
      {}
    )
    inner.instance().componentDidUpdate({}, {})
    expect(inner.state().selectedDepartment).equals("All Departments")
    expect(inner.state().tabSelected).equals("courses")
    expect(JSON.stringify(inner.state().filteredCourses)).equals(
      JSON.stringify(courses)
    )
    expect(JSON.stringify(inner.state().allCoursesRetrieved)).equals(
      JSON.stringify(courses)
    )
    expect(inner.instance().renderNumberOfCatalogItems()).equals(1)
    expect(inner.state().courseQueryPage).equals(1)

    // Simulate the user reaching the bottom of the catalog page.
    const entry = [{ isIntersecting: true }]
    await inner.instance().bottomOfLoadedCatalogCallback(entry)

    // Should not expect any additional courses.
    expect(inner.state().courseQueryPage).equals(1)
    expect(JSON.stringify(inner.state().allCoursesRetrieved)).equals(
      JSON.stringify(courses)
    )
    expect(JSON.stringify(inner.state().filteredCourses)).equals(
      JSON.stringify(courses)
    )
    expect(inner.instance().renderNumberOfCatalogItems()).equals(1)
  })

  it("do not load more at the bottom of the courses catalog page if isLoadingMoreItems is true", async () => {
    courses = [displayedCourse]
    programs = [displayedProgram]
    const { inner } = await renderPage(
      {
        queries: {
          courses: {
            isPending: false,
            status:    200
          },
          programs: {
            isPending: false,
            status:    200
          }
        },
        entities: {
          courses: {
            count:   1,
            results: courses,
            next:    "http://fake.com/api/courses/?page=2"
          },
          programs: {
            count:   1,
            results: programs
          }
        }
      },
      {}
    )
    inner.instance().componentDidUpdate({}, {})
    expect(inner.state().selectedDepartment).equals("All Departments")
    expect(inner.state().tabSelected).equals("courses")
    expect(JSON.stringify(inner.state().filteredCourses)).equals(
      JSON.stringify(courses)
    )
    expect(inner.instance().renderNumberOfCatalogItems()).equals(1)
    expect(inner.state().courseQueryPage).equals(1)

    // Simulate the user reaching the bottom of the catalog page.
    const entry = [{ isIntersecting: true }]

    // Set isLoadingMoreItems to true which simualtes that the next page
    // request is already in progress.
    inner.instance().setState({ isLoadingMoreItems: true })
    await inner.instance().bottomOfLoadedCatalogCallback(entry)

    // Should not expect any additional courses.
    expect(inner.state().courseQueryPage).equals(1)
    expect(JSON.stringify(inner.state().allCoursesRetrieved)).equals(
      JSON.stringify(courses)
    )
    expect(JSON.stringify(inner.state().filteredCourses)).equals(
      JSON.stringify(courses)
    )
    expect(inner.instance().renderNumberOfCatalogItems()).equals(1)
  })

  it("load more at the bottom of the programs catalog page, all departments filter", async () => {
    courses = [displayedCourse]
    programs = [displayedProgram]
    const { inner } = await renderPage(
      {
        queries: {
          courses: {
            isPending: false,
            status:    200
          },
          programs: {
            isPending: false,
            status:    200
          },
          departments: {
            isPending: false,
            status:    200
          }
        },
        entities: {
          courses: {
            count:   1,
            results: courses,
            next:    "http://fake.com/api/courses/?page=2"
          },
          programs: {
            count:   2,
            results: programs,
            next:    "http://fake.com/api/courses/?page=2"
          },
          departments: [
            {
              name:     "History",
              courses:  1,
              programs: 1
            }
          ]
        }
      },
      {}
    )
    inner.instance().componentDidUpdate({}, {})
    expect(inner.state().allProgramsRetrieved.length).equals(1)
    expect(inner.state().filteredPrograms.length).equals(1)
    inner.instance().changeSelectedTab("programs")
    expect(inner.state().selectedDepartment).equals("All Departments")
    expect(inner.state().tabSelected).equals("programs")
    expect(JSON.stringify(inner.state().filteredPrograms)).equals(
      JSON.stringify(programs)
    )
    expect(JSON.stringify(inner.state().allProgramsRetrieved)).equals(
      JSON.stringify(programs)
    )
    // While there is only one showing, there are still 2 total. The total should be shown.
    expect(inner.instance().renderNumberOfCatalogItems()).equals(2)
    expect(inner.state().programQueryPage).equals(1)

    // Mock the second page of program API results.
    helper.handleRequestStub.returns({
      body: {
        next:    null,
        results: programs,
        count:   2,
      }
    })

    // Simulate the user reaching the bottom of the catalog page.
    const entry = [{ isIntersecting: true }]
    await inner.instance().bottomOfLoadedCatalogCallback(entry)

    sinon.assert.calledWith(
      helper.handleRequestStub,
      "/api/v2/programs/?page=2&live=true&page__live=true",
      "GET"
    )

    // Should expect 2 courses to be displayed in the catalog now.
    expect(inner.state().programQueryPage).equals(2)
    expect(JSON.stringify(inner.state().allProgramsRetrieved)).equals(
      JSON.stringify([displayedProgram, displayedProgram])
    )
    expect(JSON.stringify(inner.state().filteredPrograms)).equals(
      JSON.stringify([displayedProgram, displayedProgram])
    )
    // This should still be 2 because we haven't changed the filter - no matter if one or two have loaded, there are 2
    expect(inner.instance().renderNumberOfCatalogItems()).equals(2)
  })
})
