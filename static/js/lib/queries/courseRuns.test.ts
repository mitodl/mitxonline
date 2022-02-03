import { courseRunsSelector } from "./courseRuns"

describe("courseRuns reducers", () => {
  describe("courseRunsSelector", () => {
    it("should return the courseRuns state", () => {
      const courseRuns = [
        {
          key: "value"
        }
      ]
      expect(
        courseRunsSelector({
          entities: {
            courseRuns
          }
        })
      ).toEqual(courseRuns)
    })
  })
})
