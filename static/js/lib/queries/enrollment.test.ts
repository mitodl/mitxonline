import { assert } from "chai"
import { enrollmentsSelector } from "./enrollment"

describe("enrollment reducers", () => {
  describe("enrollmentsSelector", () => {
    it("should return the enrollments state", () => {
      const enrollments = {
        key: "value"
      }
      assert.equal(
        enrollmentsSelector({
          entities: {
            enrollments
          }
        }),
        enrollments
      )
    })
  })
})
